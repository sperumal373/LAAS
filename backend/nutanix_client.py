"""
nutanix_client.py — Nutanix Prism Central integration
Live data via Prism Central v3 / v2.0 REST API.
Auth: username + password (Basic Auth over HTTPS:9440)
"""
import logging
from pathlib import Path
from datetime import datetime

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("caas.nutanix")

# ── DB helpers ────────────────────────────────────────────────────────
def _get_db():
    import sqlite3
    db_path = Path(__file__).parent / "caas.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def init_nutanix_db():
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS nutanix_prism_centrals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            host        TEXT NOT NULL,
            username    TEXT DEFAULT '',
            password    TEXT DEFAULT '',
            site        TEXT DEFAULT 'DC',
            description TEXT DEFAULT '',
            status      TEXT DEFAULT 'unknown',
            created_by  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    log.info("Nutanix DB tables initialized")

# ── CRUD ──────────────────────────────────────────────────────────────
def _safe_pc(d):
    d2 = dict(d)
    d2.pop("password", None)
    return d2

def list_prism_centrals():
    conn = _get_db()
    rows = conn.execute(
        "SELECT * FROM nutanix_prism_centrals ORDER BY site, name"
    ).fetchall()
    conn.close()
    return [_safe_pc(dict(r)) for r in rows]

def get_prism_central(pc_id: int):
    conn = _get_db()
    row = conn.execute(
        "SELECT * FROM nutanix_prism_centrals WHERE id=?", (pc_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def create_prism_central(data: dict) -> dict:
    conn = _get_db()
    now = _now()
    try:
        cur = conn.execute(
            """INSERT INTO nutanix_prism_centrals
               (name, host, username, password, site, description,
                status, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["host"],
             data.get("username", ""), data.get("password", ""),
             data.get("site", "DC"), data.get("description", ""),
             "unknown", data["created_by"], now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM nutanix_prism_centrals WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return _safe_pc(dict(row))
    except Exception as e:
        raise ValueError(str(e))
    finally:
        conn.close()

def update_prism_central(pc_id: int, data: dict) -> dict:
    conn = _get_db()
    now  = _now()
    fields, vals = [], []
    for k in ("name", "host", "username", "password", "site",
              "description", "status"):
        if k in data:
            fields.append(f"{k}=?")
            vals.append(data[k])
    if not fields:
        conn.close()
        return _safe_pc(get_prism_central(pc_id) or {})
    fields.append("updated_at=?")
    vals += [now, pc_id]
    conn.execute(
        f"UPDATE nutanix_prism_centrals SET {','.join(fields)} WHERE id=?",
        vals,
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM nutanix_prism_centrals WHERE id=?", (pc_id,)
    ).fetchone()
    conn.close()
    return _safe_pc(dict(row)) if row else None

def delete_prism_central(pc_id: int) -> bool:
    conn = _get_db()
    r = conn.execute(
        "DELETE FROM nutanix_prism_centrals WHERE id=?", (pc_id,)
    )
    conn.commit()
    conn.close()
    return r.rowcount > 0

# ── API transport helpers ─────────────────────────────────────────────
def _base_url(pc: dict) -> str:
    host = pc["host"].strip().rstrip("/")
    if not host.startswith("http"):
        host = f"https://{host}:9440"
    return host

def _auth(pc: dict):
    return (pc["username"], pc["password"])

def _headers():
    return {"Content-Type": "application/json", "Accept": "application/json"}

def _api_get(pc: dict, path: str, params: dict = None):
    r = requests.get(
        f"{_base_url(pc)}{path}",
        auth=_auth(pc), verify=False, timeout=90,
        headers=_headers(), params=params,
    )
    r.raise_for_status()
    return r.json()

def _api_post(pc: dict, path: str, body: dict = None):
    r = requests.post(
        f"{_base_url(pc)}{path}",
        auth=_auth(pc), verify=False, timeout=90,
        headers=_headers(), json=body or {},
    )
    r.raise_for_status()
    return r.json()

def _api_put(pc: dict, path: str, body: dict):
    r = requests.put(
        f"{_base_url(pc)}{path}",
        auth=_auth(pc), verify=False, timeout=90,
        headers=_headers(), json=body,
    )
    r.raise_for_status()
    return r.json()

# ── Connectivity test ─────────────────────────────────────────────────
def test_pc_connection(pc: dict) -> dict:
    try:
        data  = _api_post(pc, "/api/nutanix/v3/clusters/list",
                          {"kind": "cluster", "length": 1})
        count = data.get("metadata", {}).get("total_matches", 0)
        return {"reachable": True,
                "message": f"Connected \u2014 {count} cluster(s) found",
                "clusters": count}
    except Exception as e:
        return {"reachable": False, "message": str(e)}

# ── v3 list helper ────────────────────────────────────────────────────
def _list_all(pc: dict, path: str, kind: str, length: int = 500) -> list:
    """Fetch all entities with automatic pagination.
    Raises on connection / auth errors so callers can surface them."""
    offset: int = 0
    all_entities: list = []
    while True:
        body = {"kind": kind, "length": length, "offset": offset}
        data = _api_post(pc, path, body)              # raises on HTTP/network error
        entities = data.get("entities") or []
        all_entities.extend(entities)
        total = data.get("metadata", {}).get("total_matches", len(all_entities))
        offset += len(entities)
        if not entities or offset >= total:
            break
    log.debug("_list_all %s → %d entities (total_matches=%d)", path, len(all_entities), offset)
    return all_entities

# ── Clusters ──────────────────────────────────────────────────────────
def get_pc_clusters(pc: dict) -> list:
    entities = _list_all(pc, "/api/nutanix/v3/clusters/list", "cluster")
    items = []
    for e in entities:
        meta   = e.get("metadata", {})
        spec   = e.get("spec", {})
        status = e.get("status", {})
        res    = status.get("resources", {})
        cfg    = res.get("config", {})
        net    = res.get("network", {})
        sw     = cfg.get("software_map", {})
        nodes  = res.get("nodes", {}).get("hypervisor_server_list", [])
        items.append({
            "uuid":          meta.get("uuid", ""),
            "name":          spec.get("name", "") or status.get("name", ""),
            "state":         status.get("state", "UNKNOWN"),
            "aos_version":   sw.get("NOS", {}).get("version", ""),
            "ncc_version":   sw.get("NCC", {}).get("version", ""),
            "hypervisor":    (cfg.get("hypervisor_types") or ["AHV"])[0],
            "num_nodes":     len(nodes) or res.get("num_nodes", 0),
            "cluster_type":  cfg.get("cluster_type", ""),
            "external_ip":   net.get("external_ip", ""),
            "data_services_ip": net.get("external_data_services_ip", ""),
            "timezone":      cfg.get("timezone", "UTC"),
            "redundancy":    res.get("redundancy_factor", 2),
        })
    return items

# ── VMs ───────────────────────────────────────────────────────────────
def get_pc_vms(pc: dict) -> list:
    entities = _list_all(pc, "/api/nutanix/v3/vms/list", "vm")
    items = []
    for e in entities:
        meta   = e.get("metadata", {})
        spec   = e.get("spec", {})
        status = e.get("status", {})
        res    = status.get("resources", spec.get("resources", {}))
        nics   = res.get("nic_list", [])
        ips    = [ep["ip"] for nic in nics
                  for ep in nic.get("ip_endpoint_list", [])
                  if ep.get("ip")]
        items.append({
            "uuid":        meta.get("uuid", ""),
            "name":        spec.get("name", "") or status.get("name", ""),
            "power_state": res.get("power_state", "UNKNOWN"),
            "num_vcpus":   res.get("num_vcpus_per_socket", 1) * res.get("num_sockets", 1),
            "num_sockets": res.get("num_sockets", 1),
            "cores_per_socket": res.get("num_vcpus_per_socket", 1),
            "memory_mib":  res.get("memory_size_mib", 0),
            "memory_gib":  round(res.get("memory_size_mib", 0) / 1024, 1),
            "ips":         ips,
            "ip_display":  ", ".join(ips) if ips else "\u2014",
            "disk_count":  len(res.get("disk_list", [])),
            "nic_count":   len(nics),
            "cluster_name": spec.get("cluster_reference", {}).get("name", ""),
            "project":     meta.get("project_reference", {}).get("name", ""),
            "hypervisor":  res.get("hypervisor_type", "AHV"),
            "guest_os":    res.get("guest_os_id", ""),
            "created_at":  meta.get("creation_time", ""),
            "description": spec.get("description", ""),
        })
    return items

# ── Hosts ─────────────────────────────────────────────────────────────
def get_pc_hosts(pc: dict) -> list:
    entities = _list_all(pc, "/api/nutanix/v3/hosts/list", "host")
    items = []
    for e in entities:
        meta   = e.get("metadata", {})
        spec   = e.get("spec", {})
        status = e.get("status", {})
        res    = status.get("resources", spec.get("resources", {}))
        hv     = res.get("hypervisor", {})
        cvm    = res.get("controller_vm", {})
        items.append({
            "uuid":          meta.get("uuid", ""),
            "name":          spec.get("name", "") or status.get("name", ""),
            "state":         status.get("state", "UNKNOWN"),
            "cpu_model":     res.get("cpu_model", ""),
            "num_cpu_cores": res.get("num_cpu_cores", 0),
            "num_cpu_sockets": res.get("num_cpu_sockets", 0),
            "total_vcpus":   res.get("num_cpu_cores", 0) * res.get("num_cpu_sockets", 0),
            "memory_gib":    round(res.get("memory_capacity_mib", 0) / 1024, 1),
            "hypervisor_type": hv.get("hypervisor_type", "AHV"),
            "hypervisor_version": hv.get("hypervisor_full_name", ""),
            "hypervisor_ip": hv.get("ip", ""),
            "cvm_ip":        cvm.get("ip", ""),
            "ipmi_ip":       res.get("ipmi", {}).get("ip", ""),
            "cluster_name":  res.get("cluster", {}).get("name", ""),
            "serial":        res.get("serial_number", ""),
            "maintenance":   res.get("maintenance_state", "NORMAL") != "NORMAL",
            "num_vms":       res.get("num_vms", 0),
        })
    return items

# ── Storage containers ────────────────────────────────────────────────
def get_pc_storage_containers(pc: dict) -> list:
    try:
        data     = _api_get(pc,
                            "/PrismGateway/services/rest/v2.0/storage_containers/",
                            params={"count": 500})
        entities = data.get("entities", [])
    except Exception as e:
        log.warning("Storage containers error: %s", e)
        return [{"error": str(e)}]
    items = []
    for sc in entities:
        usage    = sc.get("usage", 0) or 0
        cap      = sc.get("max_capacity", 0) or 0
        items.append({
            "id":             sc.get("id", ""),
            "name":           sc.get("name", ""),
            "cluster_name":   sc.get("cluster_name", ""),
            "usage_bytes":    usage,
            "capacity_bytes": cap,
            "free_bytes":     cap - usage,
            "used_pct":       round(usage / cap * 100, 1) if cap else 0,
            "compression":    sc.get("compression_enabled", False),
            "dedup":          sc.get("dedup_enabled", False) or sc.get("fingerprint_on_write", "OFF") != "OFF",
            "erasure_code":   sc.get("erasure_code", "OFF"),
            "replication_factor": sc.get("replication_factor", 1),
            "on_disk_dedup":  sc.get("on_disk_dedup", "OFF"),
        })
    return items

# ── Alerts ────────────────────────────────────────────────────────────
def get_pc_alerts(pc: dict) -> list:
    try:
        body = {"kind": "alert", "length": 300, "offset": 0}
        data = _api_post(pc, "/api/nutanix/v3/alerts/list", body)
        entities = data.get("entities", [])
    except Exception as e:
        log.warning("Alerts error: %s", e)
        return [{"error": str(e)}]
    sev_map = {"CRITICAL": "critical", "WARNING": "warning",
               "2": "critical", "1": "warning", "0": "info"}
    items = []
    for e in entities:
        meta = e.get("metadata", {})
        res  = e.get("status", {}).get("resources", {})
        affected = res.get("affected_entity_list", [])
        sev_raw  = res.get("severity", "INFO")
        items.append({
            "uuid":         meta.get("uuid", ""),
            "title":        res.get("title", ""),
            "message":      res.get("default_message", ""),
            "severity":     sev_map.get(sev_raw, "info"),
            "severity_raw": sev_raw,
            "alert_type":   res.get("alert_type", ""),
            "entity_name":  affected[0].get("name", "") if affected else "",
            "entity_type":  affected[0].get("type", "") if affected else "",
            "resolved":     res.get("resolved", False),
            "acknowledged": res.get("acknowledged", False),
            "created_at":   meta.get("creation_time", ""),
        })
    return items

# ── Networks / Subnets ────────────────────────────────────────────────
def get_pc_networks(pc: dict) -> list:
    entities = _list_all(pc, "/api/nutanix/v3/subnets/list", "subnet")
    items = []
    for e in entities:
        meta   = e.get("metadata", {})
        spec   = e.get("spec", {})
        status = e.get("status", {})
        res    = status.get("resources", spec.get("resources", {}))
        ip_cfg = res.get("ip_config", {})
        prefix = ip_cfg.get("prefix_length", "")
        items.append({
            "uuid":         meta.get("uuid", ""),
            "name":         spec.get("name", "") or status.get("name", ""),
            "subnet_type":  res.get("subnet_type", "VLAN"),
            "vlan_id":      res.get("vlan_id", 0),
            "cidr":         (ip_cfg.get("subnet_ip", "") +
                             (f"/{prefix}" if prefix else "")),
            "gateway":      ip_cfg.get("default_gateway_ip", ""),
            "dhcp_enabled": bool(ip_cfg.get("dhcp_options")),
            "pool_list":    [p.get("range", "") for p in ip_cfg.get("pool_list", [])],
            "cluster_name": spec.get("cluster_reference", {}).get("name", ""),
            "managed":      res.get("is_external", False),
        })
    return items

# ── VM power action ───────────────────────────────────────────────────
def vm_power_action(pc: dict, vm_uuid: str, action: str) -> dict:
    """
    action: ON | OFF | REBOOT
    Fetches current VM spec then PUTs with updated power_state.
    """
    power_map = {"ON": "ON", "OFF": "OFF",
                 "REBOOT": "CYCLED",   # Nutanix uses CYCLED for soft reboot
                 "RESET": "RESET"}
    target_state = power_map.get(action.upper(), action.upper())
    try:
        vm = _api_get(pc, f"/api/nutanix/v3/vms/{vm_uuid}")
        # Keep only spec + metadata; strip status
        spec = vm.get("spec", {})
        spec.setdefault("resources", {})["power_state"] = target_state
        put_body = {
            "api_version": vm.get("api_version", "3.1.0"),
            "metadata":    vm.get("metadata", {}),
            "spec":        spec,
        }
        _api_put(pc, f"/api/nutanix/v3/vms/{vm_uuid}", put_body)
        return {"success": True,
                "message": f"Power action '{action}' submitted for VM {vm_uuid}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ── VM snapshot ───────────────────────────────────────────────────────
def vm_snapshot(pc: dict, vm_uuid: str, snapshot_name: str) -> dict:
    """Create a crash-consistent snapshot via v1 API."""
    try:
        body = {
            "snapshotSpecs": [
                {"vmUuid": vm_uuid, "snapshotName": snapshot_name}
            ]
        }
        result = _api_post(pc,
                           "/PrismGateway/services/rest/v1/snapshots/",
                           body)
        return {"success": True,
                "message": f"Snapshot '{snapshot_name}' created",
                "task": result}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ── Overview summary ──────────────────────────────────────────────────
def get_pc_overview(pc: dict) -> dict:
    try:
        clusters   = get_pc_clusters(pc)
        vms        = get_pc_vms(pc)
        hosts      = get_pc_hosts(pc)
        alerts     = get_pc_alerts(pc)
        running    = sum(1 for v in vms if v.get("power_state", "").upper() == "ON")
        off        = sum(1 for v in vms if v.get("power_state", "").upper()
                         in ("OFF", "POWERED_OFF", "SHUTDOWN"))
        critical   = sum(1 for a in alerts if a.get("severity") == "critical")
        warning    = sum(1 for a in alerts if a.get("severity") == "warning")
        total_mem  = sum(h.get("memory_gib", 0) for h in hosts)
        total_cpu  = sum(h.get("total_vcpus", 0) for h in hosts)
        return {
            "clusters":        len(clusters),
            "vms":             {"total": len(vms), "running": running, "off": off},
            "hosts":           len(hosts),
            "alerts":          {"total": len(alerts), "critical": critical,
                                "warning": warning},
            "total_memory_gib": round(total_mem, 1),
            "total_vcpus":     total_cpu,
        }
    except Exception as e:
        log.error("Overview error: %s", e)
        raise


# ── Image Service ─────────────────────────────────────────────────────
def get_pc_images(pc: dict) -> list:
    """List all images available in the Prism Central image service."""
    items = _list_all(pc, "/api/nutanix/v3/images/list", "image", length=500)
    imgs = []
    for it in items:
        meta   = it.get("metadata", {})
        status = it.get("status", {})
        res    = status.get("resources", {})
        imgs.append({
            "uuid":        meta.get("uuid", ""),
            "name":        status.get("name", "—"),
            "image_type":  res.get("image_type", "DISK_IMAGE"),
            "size_bytes":  res.get("size_bytes", 0),
            "state":       status.get("state", ""),
            "description": status.get("description", ""),
        })
    imgs.sort(key=lambda x: x["name"].lower())
    return imgs


# ── VM Provisioning ───────────────────────────────────────────────────
def provision_nutanix_vm(pc: dict, spec: dict) -> dict:
    """
    Create a VM via Prism Central v3 API.
    spec fields:
      vm_name, cluster_uuid, num_vcpus, num_cores_per_vcpu, memory_mib,
      disks: [{type, bus_type, size_bytes, storage_container_uuid,
               storage_container_name, image_uuid, clone_from_image}],
      nics:  [{subnet_uuid, subnet_name}]
    """
    try:
        disk_list = []
        for i, d in enumerate(spec.get("disks", [])):
            dtype = "CDROM" if d.get("type", "DISK") == "CDROM" else "DISK"
            bus   = d.get("bus_type", "IDE" if dtype == "CDROM" else "SCSI")
            disk_entry = {
                "device_properties": {
                    "device_type": dtype,
                    "disk_address": {
                        "adapter_type": bus,
                        "device_index": i,
                    }
                }
            }
            if dtype == "DISK" and d.get("size_bytes"):
                disk_entry["disk_size_bytes"] = int(d["size_bytes"])
            if dtype == "DISK" and d.get("storage_container_uuid"):
                disk_entry["storage_config"] = {
                    "storage_container_reference": {
                        "kind": "storage_container",
                        "uuid": d["storage_container_uuid"],
                        "name": d.get("storage_container_name", ""),
                    }
                }
            if d.get("clone_from_image") and d.get("image_uuid"):
                disk_entry["data_source_reference"] = {
                    "kind": "image",
                    "uuid": d["image_uuid"],
                }
            disk_list.append(disk_entry)

        nic_list = []
        for nic in spec.get("nics", []):
            if nic.get("subnet_uuid"):
                nic_list.append({
                    "subnet_reference": {
                        "kind": "subnet",
                        "uuid": nic["subnet_uuid"],
                    },
                    "is_connected": True,
                })

        body = {
            "api_version": "3.1",
            "metadata": {"kind": "vm", "spec_version": 0},
            "spec": {
                "name": spec["vm_name"],
                "cluster_reference": {
                    "kind": "cluster",
                    "uuid": spec["cluster_uuid"],
                },
                "resources": {
                    "num_vcpus_per_socket": int(spec.get("num_cores_per_vcpu", 1)),
                    "num_sockets":          int(spec.get("num_vcpus", 1)),
                    "memory_size_mib":      int(spec.get("memory_mib", 1024)),
                    "disk_list":            disk_list,
                    "nic_list":             nic_list,
                    "power_state":          "ON",
                }
            }
        }

        resp     = _api_post(pc, "/api/nutanix/v3/vms", body)
        task_uuid = ((resp.get("status") or {}).get("execution_context") or {}).get("task_uuid", "")
        vm_uuid   = (resp.get("metadata") or {}).get("uuid", "")
        return {
            "success":   True,
            "task_uuid": task_uuid,
            "vm_uuid":   vm_uuid,
            "message":   f"VM '{spec['vm_name']}' creation submitted. Task: {task_uuid or 'N/A'}",
        }
    except Exception as e:
        log.error("provision_nutanix_vm error: %s", e)
        return {"success": False, "message": str(e)}
