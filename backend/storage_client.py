"""
storage_client.py — Storage Array integration
Supports: NetApp ONTAP, Dell EMC PowerStore, HPE Primera/Nimble/3PAR,
          Pure Storage FlashArray, IBM FlashSystem, Hitachi VSP

Each vendor has a different REST API — this module abstracts them behind
a common interface:
    test_connection(array)  → {ok, message, system_info}
    get_array_data(array)   → {system, capacity, volumes, hosts, ...}
"""
import logging, sqlite3, json
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("caas.storage")

# ── DB ────────────────────────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(str(Path(__file__).parent / "caas.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def init_storage_db():
    conn = _db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS storage_arrays (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            vendor      TEXT NOT NULL,
            ip          TEXT NOT NULL,
            port        TEXT DEFAULT '',
            username    TEXT NOT NULL,
            password    TEXT NOT NULL,
            api_token   TEXT DEFAULT '',
            site        TEXT DEFAULT 'dc',
            capacity_tb REAL DEFAULT 0,
            status      TEXT DEFAULT 'unknown',
            last_checked TEXT DEFAULT '',
            created_by  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    # Migrate existing DB that may not have api_token column
    try:
        conn.execute("ALTER TABLE storage_arrays ADD COLUMN api_token TEXT DEFAULT ''")
        conn.commit()
        log.info("Migrated storage_arrays: added api_token column")
    except Exception:
        pass  # column already exists
    # Migrate: add console_url column
    try:
        conn.execute("ALTER TABLE storage_arrays ADD COLUMN console_url TEXT DEFAULT ''")
        conn.commit()
        log.info("Migrated storage_arrays: added console_url column")
    except Exception:
        pass  # column already exists
    conn.commit()
    conn.close()
    log.info("Storage DB tables initialized")

# ── CRUD ──────────────────────────────────────────────────────────────────────
def _safe(row):
    d = dict(row)
    d.pop("password", None)
    return d

def list_arrays():
    conn = _db()
    rows = conn.execute("SELECT * FROM storage_arrays ORDER BY site, vendor, name").fetchall()
    conn.close()
    return [_safe(r) for r in rows]

def get_array(arr_id: int) -> Optional[dict]:
    conn = _db()
    row = conn.execute("SELECT * FROM storage_arrays WHERE id=?", (arr_id,)).fetchone()
    conn.close()
    return dict(row) if row else None   # includes password for internal use

def create_array(data: dict) -> dict:
    conn = _db()
    now = _now()
    try:
        cur = conn.execute(
            """INSERT INTO storage_arrays
               (name, vendor, ip, port, username, password, api_token, site, capacity_tb,
                status, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["vendor"], data["ip"],
             data.get("port", ""), data["username"], data["password"],
             data.get("api_token", "") or "",
             data.get("site", "dc"), float(data.get("capacity_tb", 0) or 0),
             data.get("status", "unknown"), data["created_by"], now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM storage_arrays WHERE id=?", (cur.lastrowid,)).fetchone()
        return _safe(dict(row))
    except Exception as e:
        raise ValueError(str(e))
    finally:
        conn.close()

def delete_array(arr_id: int):
    conn = _db()
    conn.execute("DELETE FROM storage_arrays WHERE id=?", (arr_id,))
    conn.commit()
    conn.close()

def update_console_url(arr_id: int, url: str):
    conn = _db()
    conn.execute("UPDATE storage_arrays SET console_url=?, updated_at=? WHERE id=?",
                 (url, _now(), arr_id))
    conn.commit()
    row = conn.execute("SELECT * FROM storage_arrays WHERE id=?", (arr_id,)).fetchone()
    conn.close()
    return _safe(dict(row)) if row else None


def _set_status(arr_id: int, status: str):
    conn = _db()
    conn.execute("UPDATE storage_arrays SET status=?, last_checked=?, updated_at=? WHERE id=?",
                 (status, _now(), _now(), arr_id))
    conn.commit()
    conn.close()

# ── Vendor helpers ─────────────────────────────────────────────────────────────
def _base(arr: dict) -> str:
    port = arr.get("port", "").strip()
    h = arr["ip"].strip()
    # Strip any protocol prefix the user may have included
    h = h.removeprefix("https://").removeprefix("http://").rstrip("/")
    return f"https://{h}:{port}" if port else f"https://{h}"

def _sess(arr: dict) -> requests.Session:
    s = requests.Session()
    s.verify = False
    s.auth = (arr["username"], arr["password"])
    s.timeout = 15
    return s

# ── NetApp ONTAP REST API (9.6+) ───────────────────────────────────────────────
def _netapp_test(arr: dict) -> dict:
    base = _base(arr)
    s = _sess(arr)
    r = s.get(f"{base}/api/cluster", timeout=15)
    r.raise_for_status()
    d = r.json()
    # Fall back to first node's model/serial if cluster-level fields are empty
    model  = d.get("model", "")
    serial = d.get("serial_number", "")
    try:
        nr = s.get(f"{base}/api/cluster/nodes",
                   params={"fields": "name,model,serial_number"}, timeout=15).json()
        node0 = nr.get("records", [{}])[0]
        if not model:  model  = node0.get("model", "")
        if not serial: serial = node0.get("serial_number", "")
    except Exception:
        pass
    return {
        "ok": True,
        "message": f"Connected — ONTAP {d.get('version', {}).get('full', '')}",
        "system_info": {
            "name":     d.get("name", ""),
            "serial":   serial,
            "model":    model,
            "version":  d.get("version", {}).get("full", ""),
            "location": d.get("location", ""),
            "contact":  d.get("contact", ""),
            "uuid":     d.get("uuid", ""),
        }
    }

def _netapp_data(arr: dict) -> dict:
    base = _base(arr)
    s = _sess(arr)

    # cluster overview
    cluster = s.get(f"{base}/api/cluster").json()

    # nodes
    nodes_r = s.get(f"{base}/api/cluster/nodes",
                    params={"fields": "name,model,serial_number,state,uptime,uuid"}).json()
    nodes = nodes_r.get("records", [])
    cluster_model  = cluster.get("model", "") or (nodes[0].get("model", "") if nodes else "")
    cluster_serial = cluster.get("serial_number", "") or (nodes[0].get("serial_number", "") if nodes else "")

    # ── SVMs (used in admin dropdowns) ────────────────────────────────────────
    svm_r = s.get(f"{base}/api/svm/svms",
                  params={"fields": "name,uuid,state"}).json()
    svms = svm_r.get("records", [])
    svm_list = [{"name": sv.get("name",""), "uuid": sv.get("uuid",""), "state": sv.get("state","")} for sv in svms]

    # ── Aggregates / Local Tiers ──────────────────────────────────────────────
    agg_r = s.get(f"{base}/api/storage/aggregates",
                  params={"fields": "name,state,space,block_storage,node"}).json()
    aggregates = agg_r.get("records", [])
    total_bytes = sum(a.get("space", {}).get("block_storage", {}).get("size", 0) for a in aggregates)
    used_bytes  = sum(a.get("space", {}).get("block_storage", {}).get("used", 0) for a in aggregates)
    agg_list = []
    for a in aggregates:
        sp = a.get("space", {}).get("block_storage", {})
        sz = sp.get("size", 0)
        agg_list.append({
            "name":        a.get("name", ""),
            "state":       a.get("state", ""),
            "node":        a.get("node", {}).get("name", "") if isinstance(a.get("node"), dict) else "",
            "total_bytes": sz,
            "used_bytes":  sp.get("used", 0),
            "free_bytes":  sp.get("available", sz - sp.get("used", 0)),
            "used_pct":    round(sp.get("used", 0) / sz * 100, 1) if sz else 0,
        })

    # ── Volumes ───────────────────────────────────────────────────────────────
    vol_r = s.get(f"{base}/api/storage/volumes",
                  params={"fields": "name,state,type,space,svm,nas,uuid,comment,create_time,is_svm_root,guarantee,snapshot_policy",
                          "max_records": 500}).json()
    vol_records = vol_r.get("records", [])
    volume_list = []
    for v in vol_records:
        sp  = v.get("space", {})
        nas = v.get("nas", {})
        sz  = sp.get("size", 0)
        volume_list.append({
            "name":            v.get("name", ""),
            "svm":             v.get("svm", {}).get("name", ""),
            "svm_uuid":        v.get("svm", {}).get("uuid", ""),
            "state":           v.get("state", ""),
            "type":            v.get("type", ""),
            "uuid":            v.get("uuid", ""),
            "junction_path":   nas.get("path", ""),
            "total_bytes":     sz,
            "used_bytes":      sp.get("used", 0),
            "available_bytes": sp.get("available", 0),
            "used_pct":        round(sp.get("used", 0) / sz * 100, 1) if sz else 0,
            "guarantee":       v.get("guarantee", {}).get("type", ""),
            "is_root":         v.get("is_svm_root", False),
            "comment":         v.get("comment", ""),
            "created":         v.get("create_time", ""),
            "snapshot_policy": v.get("snapshot_policy", {}).get("name", "") if isinstance(v.get("snapshot_policy"), dict) else "",
        })

    # ── LUNs ──────────────────────────────────────────────────────────────────
    # NOTE: ONTAP REST does NOT have a "path" field — "name" IS the full path.
    # State lives under status.state, volume under location.volume.name.
    lun_list = []
    try:
        lun_resp = s.get(f"{base}/api/storage/luns",
                         params={"fields": "name,svm,space,status,os_type,uuid,location,enabled,serial_number,class",
                                 "max_records": 500})
        if lun_resp.status_code != 200:
            log.warning("LUN fetch HTTP %s: %s", lun_resp.status_code, lun_resp.text[:400])
        else:
            lun_r = lun_resp.json()
            for ln in lun_r.get("records", []):
                sp        = ln.get("space", {}) if isinstance(ln.get("space"), dict) else {}
                st        = ln.get("status", {}) if isinstance(ln.get("status"), dict) else {}
                loc       = ln.get("location", {}) if isinstance(ln.get("location"), dict) else {}
                full_path = ln.get("name", "")          # /vol/<vol>/<lun>
                short     = loc.get("logical_unit", "") or (full_path.split("/")[-1] if full_path else "")
                vol_name  = loc.get("volume", {}).get("name", "") if isinstance(loc.get("volume"), dict) else ""
                node_name = loc.get("node", {}).get("name", "") if isinstance(loc.get("node"), dict) else ""
                lun_list.append({
                    "name":        short,
                    "path":        full_path,
                    "svm":         ln.get("svm", {}).get("name", "") if isinstance(ln.get("svm"), dict) else "",
                    "svm_uuid":    ln.get("svm", {}).get("uuid", "") if isinstance(ln.get("svm"), dict) else "",
                    "state":       st.get("state", ""),
                    "mapped":      st.get("mapped", False),
                    "container":   st.get("container_state", ""),
                    "enabled":     ln.get("enabled", True),
                    "os_type":     ln.get("os_type", ""),
                    "uuid":        ln.get("uuid", ""),
                    "serial":      ln.get("serial_number", ""),
                    "lun_class":   ln.get("class", ""),
                    "total_bytes": sp.get("size", 0),
                    "used_bytes":  sp.get("used", 0),
                    "volume":      vol_name,
                    "node":        node_name,
                })
    except Exception as _e:
        log.warning("LUN fetch error: %s", _e)

    # ── Disks / Drives ─────────────────────────────────────────────────────────
    # ONTAP REST field for disk class is "class" not "disk_class"
    disk_list = []
    disk_records = []
    try:
        disk_r = s.get(f"{base}/api/storage/disks",
                       params={"fields": "name,type,state,model,serial_number,bay,home_node,rpm,usable_size,class,vendor,container_type,drawer",
                               "max_records": 1000}).json()
        disk_records = disk_r.get("records", [])
        for d in disk_records:
            hn     = d.get("home_node", {})
            drawer = d.get("drawer", {})
            disk_list.append({
                "name":       d.get("name", ""),
                "type":       d.get("type", ""),
                "state":      d.get("state", ""),
                "model":      d.get("model", ""),
                "serial":     d.get("serial_number", ""),
                "vendor":     d.get("vendor", ""),
                "bay":        d.get("bay", drawer.get("slot", "")),
                "node":       hn.get("name", "") if isinstance(hn, dict) else "",
                "rpm":        d.get("rpm", 0),
                "capacity":   d.get("usable_size", 0),
                "disk_class": d.get("class", d.get("disk_class", "")),
                "container":  d.get("container_type", ""),
            })
    except Exception as _e:
        log.debug("Disk fetch error: %s", _e)

    # ── Initiator Groups ───────────────────────────────────────────────────────
    igroup_list = []
    try:
        ig_r = s.get(f"{base}/api/protocols/san/igroups",
                     params={"fields": "name,protocol,os_type,initiators,svm,uuid",
                             "max_records": 500}).json()
        for ig in ig_r.get("records", []):
            initiators = ig.get("initiators", [])
            igroup_list.append({
                "name":            ig.get("name", ""),
                "svm":             ig.get("svm", {}).get("name", ""),
                "svm_uuid":        ig.get("svm", {}).get("uuid", ""),
                "protocol":        ig.get("protocol", ""),
                "os_type":         ig.get("os_type", ""),
                "uuid":            ig.get("uuid", ""),
                "initiators":      [i.get("name", "") for i in initiators],
                "initiator_count": len(initiators),
            })
    except Exception:
        pass

    # ── Network Interfaces ─────────────────────────────────────────────────────
    nic_list = []
    try:
        nic_r = s.get(f"{base}/api/network/ip/interfaces",
                      params={"fields": "name,ip,svm,state,location,service_policy,enabled",
                              "max_records": 500}).json()
        for n in nic_r.get("records", []):
            ip   = n.get("ip", {})
            loc  = n.get("location", {})
            nic_list.append({
                "name":     n.get("name", ""),
                "ip":       ip.get("address", ""),
                "netmask":  ip.get("netmask", ""),
                "svm":      n.get("svm", {}).get("name", "") if isinstance(n.get("svm"), dict) else "",
                "state":    n.get("state", ""),
                "enabled":  n.get("enabled", True),
                "node":     loc.get("node", {}).get("name", "") if isinstance(loc.get("node"), dict) else "",
                "port":     loc.get("port", {}).get("name", "") if isinstance(loc.get("port"), dict) else "",
                "policy":   n.get("service_policy", {}).get("name", "") if isinstance(n.get("service_policy"), dict) else "",
            })
    except Exception:
        pass

    # ── SnapMirror Relationships ───────────────────────────────────────────────
    snapmirror_list = []
    try:
        sm_r = s.get(f"{base}/api/snapmirror/relationships",
                     params={"fields": "source,destination,state,transfer_schedule,policy,lag_time,healthy",
                             "max_records": 500}).json()
        for rel in sm_r.get("records", []):
            src = rel.get("source", {})
            dst = rel.get("destination", {})
            snapmirror_list.append({
                "source_vol":   src.get("path", ""),
                "source_svm":   src.get("svm", {}).get("name", "") if isinstance(src.get("svm"), dict) else "",
                "dest_vol":     dst.get("path", ""),
                "dest_svm":     dst.get("svm", {}).get("name", "") if isinstance(dst.get("svm"), dict) else "",
                "state":        rel.get("state", ""),
                "healthy":      rel.get("healthy", None),
                "lag_time":     rel.get("lag_time", ""),
                "policy":       rel.get("policy", {}).get("name", "") if isinstance(rel.get("policy"), dict) else "",
                "schedule":     rel.get("transfer_schedule", {}).get("name", "") if isinstance(rel.get("transfer_schedule"), dict) else "",
            })
    except Exception:
        pass

    # ── EMS Events (recent alerts) ─────────────────────────────────────────────
    ems_events = []
    try:
        ems_r = s.get(f"{base}/api/support/ems/events",
                      params={"fields": "message,time,node,severity",
                              "filter.name": "ems.compliance.info,ems.compliance.warning,ems.compliance.error",
                              "max_records": 100,
                              "order_by": "time desc"}).json()
        for ev in ems_r.get("records", []):
            ems_events.append({
                "time":     ev.get("time", ""),
                "severity": ev.get("severity", ""),
                "message":  ev.get("message", {}).get("name", "") if isinstance(ev.get("message"), dict) else str(ev.get("message","")),
                "node":     ev.get("node", {}).get("name", "") if isinstance(ev.get("node"), dict) else "",
            })
    except Exception:
        pass

    # ── NFS Export Policies + Rules ───────────────────────────────────────────
    nfs_count  = 0
    nfs_exports = []
    try:
        ep_r = s.get(f"{base}/api/protocols/nfs/export-policies",
                     params={"fields": "name,id,svm", "max_records": 200}).json()
        nfs_count = ep_r.get("num_records", len(ep_r.get("records", [])))
        for ep in ep_r.get("records", []):
            eid  = ep.get("id", "")
            esvm = ep.get("svm", {}).get("name", "") if isinstance(ep.get("svm"), dict) else ""
            rules = []
            try:
                rr = s.get(f"{base}/api/protocols/nfs/export-policies/{eid}/rules",
                           params={"fields": "clients,ro_rule,rw_rule,protocols,index", "max_records": 100}).json()
                for rule in rr.get("records", []):
                    clients = [c.get("match","") for c in rule.get("clients", [])]
                    rules.append({
                        "index":     rule.get("index", ""),
                        "clients":   clients,
                        "ro_rule":   rule.get("ro_rule", []),
                        "rw_rule":   rule.get("rw_rule", []),
                        "protocols": rule.get("protocols", []),
                    })
            except Exception:
                pass
            nfs_exports.append({
                "name":       ep.get("name", ""),
                "id":         eid,
                "svm":        esvm,
                "rule_count": len(rules),
                "rules":      rules,
            })
    except Exception as _e:
        log.debug("NFS fetch error: %s", _e)

    # ── CIFS Shares ───────────────────────────────────────────────────────────
    cifs_count  = 0
    cifs_shares = []
    try:
        cs_r = s.get(f"{base}/api/protocols/cifs/shares",
                     params={"fields": "name,path,svm,comment,acls,volume,home_directory,oplocks,access_based_enumeration",
                             "max_records": 500}).json()
        cifs_count = cs_r.get("num_records", len(cs_r.get("records", [])))
        for sh in cs_r.get("records", []):
            acls = sh.get("acls", [])
            cifs_shares.append({
                "name":        sh.get("name", ""),
                "path":        sh.get("path", ""),
                "svm":         sh.get("svm", {}).get("name", "") if isinstance(sh.get("svm"), dict) else "",
                "volume":      sh.get("volume", {}).get("name", "") if isinstance(sh.get("volume"), dict) else "",
                "comment":     sh.get("comment", ""),
                "home_dir":    sh.get("home_directory", False),
                "oplocks":     sh.get("oplocks", True),
                "acls":        [{"user": a.get("user_or_group",""), "type": a.get("type",""), "permission": a.get("permission","")} for a in acls],
            })
    except Exception as _e:
        log.debug("CIFS fetch error: %s", _e)

    # ── Storage VM (SVM) Rich Details ─────────────────────────────────────────
    svm_details = []
    try:
        svmd_r = s.get(f"{base}/api/svm/svms",
                       params={"fields": "name,uuid,state,type,language,comment,snapshot_policy,cifs,nfs,iscsi,fcp,nvme,ip_space,dns,subtype",
                               "max_records": 200}).json()
        for sv in svmd_r.get("records", []):
            protos = []
            if sv.get("cifs",   {}).get("enabled"): protos.append("CIFS/SMB")
            if sv.get("nfs",    {}).get("enabled"): protos.append("NFS")
            if sv.get("iscsi",  {}).get("enabled"): protos.append("iSCSI")
            if sv.get("fcp",    {}).get("enabled"): protos.append("FC")
            if sv.get("nvme",   {}).get("enabled"): protos.append("NVMe")
            dns = sv.get("dns", {})
            svm_details.append({
                "name":            sv.get("name", ""),
                "uuid":            sv.get("uuid", ""),
                "state":           sv.get("state", ""),
                "type":            sv.get("type", sv.get("subtype", "")),
                "language":        sv.get("language", ""),
                "comment":         sv.get("comment", ""),
                "snapshot_policy": sv.get("snapshot_policy", {}).get("name", "") if isinstance(sv.get("snapshot_policy"), dict) else "",
                "ip_space":        sv.get("ip_space", {}).get("name", "") if isinstance(sv.get("ip_space"), dict) else "",
                "protocols":       protos,
                "dns_domains":     dns.get("domains", []) if isinstance(dns, dict) else [],
                "dns_servers":     dns.get("servers", []) if isinstance(dns, dict) else [],
            })
    except Exception as _e:
        log.debug("SVM detail fetch error: %s", _e)
        svm_details = svm_list  # fall back to basic list

    # ── Performance ───────────────────────────────────────────────────────────
    perf = {}
    try:
        pm = s.get(f"{base}/api/cluster/metrics",
                   params={"fields": "iops,latency,throughput", "interval": "1m"}).json()
        recs = pm.get("records", [{}])
        latest = recs[-1] if recs else {}
        iops_d = latest.get("iops", {})
        lat_d  = latest.get("latency", {})
        tput_d = latest.get("throughput", {})
        perf = {
            "iops_read":        iops_d.get("read", 0),
            "iops_write":       iops_d.get("write", 0),
            "iops_total":       iops_d.get("total", 0),
            "latency_read_us":  lat_d.get("read", 0),
            "latency_write_us": lat_d.get("write", 0),
            "throughput_read":  tput_d.get("read", 0),
            "throughput_write": tput_d.get("write", 0),
        }
    except Exception:
        pass

    return {
        "system": {
            "name":     cluster.get("name", ""),
            "model":    cluster_model,
            "serial":   cluster_serial,
            "version":  cluster.get("version", {}).get("full", ""),
            "location": cluster.get("location", ""),
            "uuid":     cluster.get("uuid", ""),
            "nodes":    len(nodes),
            "node_details": [
                {"name": n.get("name",""), "model": n.get("model",""),
                 "serial": n.get("serial_number",""), "state": n.get("state","")}
                for n in nodes
            ],
        },
        "capacity": {
            "total_bytes": total_bytes,
            "used_bytes":  used_bytes,
            "free_bytes":  total_bytes - used_bytes,
            "total_tb":    round(total_bytes / 1e12, 2),
            "used_tb":     round(used_bytes  / 1e12, 2),
            "free_tb":     round((total_bytes - used_bytes) / 1e12, 2),
            "used_pct":    round(used_bytes / total_bytes * 100, 1) if total_bytes else 0,
        },
        "volumes":          len(vol_records),
        "luns":             len(lun_list),
        "disks":            len(disk_list),
        "svms":             len(svms),
        "aggregates":       len(aggregates),
        "igroups":          len(igroup_list),
        "nics":             len(nic_list),
        "snapmirror":       len(snapmirror_list),
        "nfs_exports":      nfs_count,
        "cifs_shares":      cifs_count,
        "ems_event_count":  len(ems_events),
        "perf":             perf,
        # rich lists
        "volume_list":       volume_list,
        "lun_list":          lun_list,
        "disk_list":         disk_list,
        "igroup_list":       igroup_list,
        "agg_list":          agg_list,
        "nic_list":          nic_list,
        "snapmirror_list":   snapmirror_list,
        "ems_events":        ems_events,
        "svm_list":          svm_list,
        "svm_details":       svm_details,
        "nfs_export_list":   nfs_exports,
        "cifs_share_list":   cifs_shares,
    }


# ── NetApp ONTAP Admin Operations ───────────────────────────────────────────────
def netapp_volume_create(arr: dict, payload: dict) -> dict:
    """Create a volume. payload: name, svm_name, size_bytes, type(rw/dp), junction_path"""
    base = _base(arr)
    s = _sess(arr)
    body: dict = {
        "name": payload["name"],
        "svm":  {"name": payload["svm_name"]},
        "size": int(payload["size_bytes"]),
        "type": payload.get("type", "rw"),
        "guarantee": {"type": payload.get("guarantee", "none")},
    }
    if payload.get("aggregate"):
        body["aggregates"] = [{"name": payload["aggregate"]}]
    if payload.get("junction_path"):
        body["nas"] = {"path": payload["junction_path"]}
    r = s.post(f"{base}/api/storage/volumes", json=body, timeout=30)
    if not r.ok:
        raise ValueError(f"Volume create failed {r.status_code}: {r.text[:300]}")
    return {"ok": True, "message": "Volume created", "response": r.json() if r.text else {}}

def netapp_volume_delete(arr: dict, vol_uuid: str) -> dict:
    base = _base(arr)
    s = _sess(arr)
    r = s.delete(f"{base}/api/storage/volumes/{vol_uuid}", timeout=30)
    if not r.ok:
        raise ValueError(f"Volume delete failed {r.status_code}: {r.text[:300]}")
    return {"ok": True, "message": "Volume deleted"}

def netapp_snapshot_list(arr: dict, vol_uuid: str) -> list:
    base = _base(arr)
    s = _sess(arr)
    r = s.get(f"{base}/api/storage/volumes/{vol_uuid}/snapshots",
              params={"fields": "name,create_time,size,state,uuid", "max_records": 200},
              timeout=20)
    r.raise_for_status()
    snaps = []
    for sn in r.json().get("records", []):
        snaps.append({
            "name":    sn.get("name", ""),
            "uuid":    sn.get("uuid", ""),
            "state":   sn.get("state", ""),
            "size":    sn.get("size", 0),
            "created": sn.get("create_time", ""),
        })
    return snaps

def netapp_snapshot_create(arr: dict, vol_uuid: str, name: str) -> dict:
    base = _base(arr)
    s = _sess(arr)
    r = s.post(f"{base}/api/storage/volumes/{vol_uuid}/snapshots",
               json={"name": name}, timeout=30)
    if not r.ok:
        raise ValueError(f"Snapshot create failed {r.status_code}: {r.text[:300]}")
    return {"ok": True, "message": f"Snapshot '{name}' created"}

def netapp_snapshot_delete(arr: dict, vol_uuid: str, snap_uuid: str) -> dict:
    base = _base(arr)
    s = _sess(arr)
    r = s.delete(f"{base}/api/storage/volumes/{vol_uuid}/snapshots/{snap_uuid}", timeout=30)
    if not r.ok:
        raise ValueError(f"Snapshot delete failed {r.status_code}: {r.text[:300]}")
    return {"ok": True, "message": "Snapshot deleted"}

def netapp_igroup_create(arr: dict, payload: dict) -> dict:
    """payload: name, svm_name, protocol(iscsi/fcp), os_type, initiators(list of str)"""
    base = _base(arr)
    s = _sess(arr)
    body = {
        "name":      payload["name"],
        "svm":       {"name": payload["svm_name"]},
        "protocol":  payload.get("protocol", "iscsi"),
        "os_type":   payload.get("os_type", "linux"),
        "initiators": [{"name": i} for i in payload.get("initiators", []) if i.strip()],
    }
    r = s.post(f"{base}/api/protocols/san/igroups", json=body, timeout=30)
    if not r.ok:
        raise ValueError(f"iGroup create failed {r.status_code}: {r.text[:300]}")
    return {"ok": True, "message": "iGroup created", "response": r.json() if r.text else {}}

def netapp_igroup_delete(arr: dict, ig_uuid: str) -> dict:
    base = _base(arr)
    s = _sess(arr)
    r = s.delete(f"{base}/api/protocols/san/igroups/{ig_uuid}", timeout=30)
    if not r.ok:
        raise ValueError(f"iGroup delete failed {r.status_code}: {r.text[:300]}")
    return {"ok": True, "message": "iGroup deleted"}

def netapp_lun_create(arr: dict, payload: dict) -> dict:
    """payload: name, path, svm_name, os_type, size_bytes"""
    base = _base(arr)
    s = _sess(arr)
    body = {
        "name":    payload.get("name", ""),
        "svm":     {"name": payload["svm_name"]},
        "os_type": payload.get("os_type", "linux"),
        "space":   {"size": int(payload["size_bytes"])},
    }
    if payload.get("path"):
        body["location"] = {"logical_unit": payload["path"]}
    if payload.get("volume"):
        body.setdefault("location", {})["volume"] = {"name": payload["volume"]}
    r = s.post(f"{base}/api/storage/luns", json=body, timeout=30)
    if not r.ok:
        raise ValueError(f"LUN create failed {r.status_code}: {r.text[:300]}")
    return {"ok": True, "message": "LUN created", "response": r.json() if r.text else {}}

def netapp_lun_delete(arr: dict, lun_uuid: str) -> dict:
    base = _base(arr)
    s = _sess(arr)
    r = s.delete(f"{base}/api/storage/luns/{lun_uuid}", timeout=30)
    if not r.ok:
        raise ValueError(f"LUN delete failed {r.status_code}: {r.text[:300]}")
    return {"ok": True, "message": "LUN deleted"}

def netapp_get_svms(arr: dict) -> list:
    base = _base(arr)
    s = _sess(arr)
    r = s.get(f"{base}/api/svm/svms", params={"fields": "name,uuid,state"}, timeout=15)
    r.raise_for_status()
    return [{"name": sv.get("name",""), "uuid": sv.get("uuid",""), "state": sv.get("state","")}
            for sv in r.json().get("records", [])]

def netapp_get_aggregates(arr: dict) -> list:
    base = _base(arr)
    s = _sess(arr)
    r = s.get(f"{base}/api/storage/aggregates", params={"fields": "name,state"}, timeout=15)
    r.raise_for_status()
    return [{"name": a.get("name",""), "state": a.get("state","")}
            for a in r.json().get("records", [])]

# ── Dell EMC PowerStore REST API ───────────────────────────────────────────────
# PowerStore auth: POST /api/rest/auth_sessions → session cookie PWRSTN-TOKEN
# + DELL-EMC-TOKEN response header (CSRF token required on all mutating calls,
#   and respected on GETs too). Basic Auth alone is NOT sufficient on all firmware.

def _dell_session(arr: dict) -> requests.Session:
    """
    PowerStore auth:
    POST /api/rest/auth_sessions  with  Authorization: Basic ...
    Response gives back DELL-EMC-TOKEN header (CSRF token) + session cookie.
    GET endpoints also accept Basic Auth directly — we use both.
    """
    base = _base(arr)
    import base64 as _b64
    cred = _b64.b64encode(f"{arr['username']}:{arr['password']}".encode()).decode()

    s = requests.Session()
    s.verify  = False
    s.timeout = 20
    s.headers.update({
        "Accept":        "application/json",
        "Content-Type":  "application/json",
        "Authorization": f"Basic {cred}",
    })

    # Establish session — sends Basic Auth in header (required by PowerStore)
    login_r = s.post(
        f"{base}/api/rest/auth_sessions",
        json={"is_cookie_based": True},
        timeout=20,
    )

    if login_r.status_code == 401:
        raise requests.exceptions.HTTPError(
            f"401 — wrong username or password for {base}", response=login_r
        )
    if login_r.status_code not in (200, 201, 204):
        # Some older PowerStore firmware doesn't have auth_sessions — fall
        # back to keeping Basic Auth for all calls (works for GETs)
        log.debug("PowerStore auth_sessions returned %d — using Basic Auth only",
                  login_r.status_code)
        return s

    # Extract CSRF token (required for POST/PUT/DELETE, harmless on GETs)
    dell_token = (login_r.headers.get("DELL-EMC-TOKEN") or
                  login_r.headers.get("dell-emc-token") or "")
    if dell_token:
        s.headers.update({"DELL-EMC-TOKEN": dell_token})

    log.debug("PowerStore session OK for %s (CSRF token: %s)", base, bool(dell_token))
    return s


def _dell_version(s: requests.Session, base: str) -> str:
    """Fetch firmware version — field name varies by PowerStore firmware generation."""
    try:
        r = s.get(f"{base}/api/rest/software_installed",
                  params={"select": "release_version,is_package"}, timeout=10)
        if r.status_code == 200:
            items = r.json() if isinstance(r.json(), list) else []
            for item in items:
                if not item.get("is_package", True):
                    return item.get("release_version", "")
            if items:
                return items[0].get("release_version", "")
    except Exception:
        pass
    try:
        r2 = s.get(f"{base}/api/rest/cluster",
                   params={"select": "release_version"}, timeout=10)
        if r2.status_code == 200:
            cl = r2.json()
            cl = cl[0] if isinstance(cl, list) and cl else cl
            return cl.get("release_version", "")
    except Exception:
        pass
    return ""


def _dell_test(arr: dict) -> dict:
    base = _base(arr)
    s = _dell_session(arr)

    # Use only fields that exist across all PowerStore firmware versions
    r = s.get(f"{base}/api/rest/appliance",
              params={"select": "id,name,model,service_tag"},
              timeout=15)
    r.raise_for_status()
    records = r.json() if isinstance(r.json(), list) else []
    a = records[0] if records else {}
    version = _dell_version(s, base)
    return {
        "ok": True,
        "message": f"Connected — Dell EMC PowerStore {version}".strip(),
        "system_info": {
            "name":    a.get("name", ""),
            "model":   a.get("model", ""),
            "serial":  a.get("service_tag", ""),
            "version": version,
        }
    }


def _dell_capacity(s: requests.Session, base: str, appliance_id: str) -> tuple:
    """
    Fetch total/used bytes from PowerStore.
    Tries multiple endpoints since field names vary by firmware version.
    Returns (total_bytes, used_bytes).
    """
    # Method 1: /api/rest/capacity  (most firmware versions)
    try:
        r = s.get(f"{base}/api/rest/capacity", timeout=12)
        if r.status_code == 200:
            caps = r.json() if isinstance(r.json(), list) else []
            if caps:
                c = caps[0]
                total_b = int(c.get("total_raw_capacity",
                              c.get("total_capacity",
                              c.get("physical_total", 0))) or 0)
                used_b  = int(c.get("used_capacity",
                              c.get("physical_used",  0)) or 0)
                if total_b:
                    return total_b, used_b
    except Exception:
        pass

    # Method 2: appliance with individual capacity fields
    for fields in ("physical_total,physical_used",
                   "raw_capacity_bytes,usable_capacity_bytes"):
        try:
            r = s.get(f"{base}/api/rest/appliance",
                      params={"select": f"id,{fields}"}, timeout=12)
            if r.status_code == 200:
                items = r.json() if isinstance(r.json(), list) else []
                a = next((i for i in items if i.get("id") == appliance_id), items[0] if items else {})
                flds = fields.split(",")
                total_b = int(a.get(flds[0], 0) or 0)
                used_b  = int(a.get(flds[1], 0) or 0)
                if total_b:
                    return total_b, used_b
        except Exception:
            pass

    # Method 3: storage_resource aggregate
    try:
        r = s.get(f"{base}/api/rest/storage_resource",
                  params={"select": "size_total,size_used"}, timeout=12)
        if r.status_code == 200:
            items = r.json() if isinstance(r.json(), list) else []
            total_b = sum(int(i.get("size_total", 0) or 0) for i in items)
            used_b  = sum(int(i.get("size_used",  0) or 0) for i in items)
            if total_b:
                return total_b, used_b
    except Exception:
        pass

    return 0, 0


def _dell_data(arr: dict) -> dict:
    base = _base(arr)
    s = _dell_session(arr)

    def _get(path, params=None):
        try:
            r = s.get(f"{base}{path}", params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except Exception as _e:
            log.debug("PowerStore %s skipped: %s", path, _e)
            return []

    # ── Appliance + Cluster ──
    appliance_list = _get("/api/rest/appliance", {
        "select": "id,name,model,service_tag,express_service_code,drive_failure_tolerance_level,node_count"})
    a = appliance_list[0] if appliance_list else {}
    cluster_list = _get("/api/rest/cluster", {
        "select": "id,name,global_id,management_address,state,compatibility_level,system_time"})
    cl = cluster_list[0] if cluster_list else {}

    # ── Software version ──
    version = ""
    sw_list = _get("/api/rest/software_installed", {
        "select": "id,release_version,build_version,release_timestamp"})
    if sw_list:
        version = sw_list[0].get("release_version", "") or ""

    # ── Volumes (rich) ──
    vols = _get("/api/rest/volume", {
        "select": "id,name,size,state,type,wwn,appliance_id,protection_policy_id,"
                  "is_replication_destination,creation_timestamp,logical_used"})
    # ── Hosts (rich) ──
    hosts = _get("/api/rest/host", {
        "select": "id,name,os_type,type,description,host_group_id"})
    snaps = _get("/api/rest/volume_snapshot", {"select": "id,name,size"})

    # ── Capacity ──
    try:
        total_b, used_b = _dell_capacity(s, base, a.get("id", ""))
    except Exception as _ce:
        log.debug("PowerStore capacity query failed: %s", _ce)
        total_b, used_b = 0, 0

    # ── Performance metrics ──
    perf = {}
    try:
        pm_r = s.post(
            f"{base}/api/rest/metrics/query",
            json={"entity": "appliance", "entity_id": a.get("id", ""),
                  "interval": "Five_Mins",
                  "metrics": ["avg_read_iops", "avg_write_iops",
                              "avg_read_latency", "avg_write_latency",
                              "avg_read_bandwidth", "avg_write_bandwidth"]},
            timeout=15,
        )
        pm_r.raise_for_status()
        pm = pm_r.json() if isinstance(pm_r.json(), list) else []
        if pm:
            latest = pm[-1]
            perf = {
                "iops_read":        int(latest.get("avg_read_iops",  0) or 0),
                "iops_write":       int(latest.get("avg_write_iops", 0) or 0),
                "iops_total":       int((latest.get("avg_read_iops",  0) or 0) +
                                        (latest.get("avg_write_iops", 0) or 0)),
                "latency_read_us":  int((latest.get("avg_read_latency",  0) or 0) * 1000),
                "latency_write_us": int((latest.get("avg_write_latency", 0) or 0) * 1000),
                "throughput_read":  round((latest.get("avg_read_bandwidth",  0) or 0) / 1e9, 2),
                "throughput_write": round((latest.get("avg_write_bandwidth", 0) or 0) / 1e9, 2),
            }
    except Exception as _pe:
        log.debug("PowerStore perf query skipped: %s", _pe)

    # ── Additional resources ──
    host_groups   = _get("/api/rest/host_group",   {"select": "id,name,description,host_connectivity"})
    volume_groups = _get("/api/rest/volume_group",  {"select": "id,name,description,creation_timestamp,placement_rule"})
    file_systems  = _get("/api/rest/file_system",   {
        "select": "id,name,size_total,size_used,filesystem_type,access_policy,nas_server_id,protection_policy_id,creation_timestamp"})
    smb_shares    = _get("/api/rest/smb_share",     {"select": "id,name,path,file_system_id,is_continuous_availability_enabled"})
    nfs_exports   = _get("/api/rest/nfs_export",    {"select": "id,name,path,file_system_id,min_security,default_access"})
    nas_servers   = _get("/api/rest/nas_server",    {"select": "id,name,description,operational_status,current_node_id"})
    alerts        = _get("/api/rest/alert",         {"select": "id,severity,state,generated_timestamp,description_l10n,resource_type,resource_name"})
    snap_rules    = _get("/api/rest/snapshot_rule",  {"select": "id,name,interval,time_of_day,days_of_week,desired_retention"})
    eth_ports     = _get("/api/rest/eth_port",      {"select": "id,name,current_speed,is_link_up,mac_address,node_id"})
    fc_ports      = _get("/api/rest/fc_port",       {"select": "id,name,wwn,is_link_up,current_speed,node_id"})
    ip_addrs      = _get("/api/rest/ip_pool_address", {"select": "id,name,address,purposes,node_id"})
    stor_cont     = _get("/api/rest/storage_container", {"select": "id,name,quota,storage_protocol"})

    # Compute capacity from volumes + file-systems when appliance capacity unavailable
    vol_total = sum(int(v.get("size", 0) or 0) for v in vols)
    vol_used  = sum(int(v.get("logical_used", 0) or 0) for v in vols)
    fs_total  = sum(int(fs.get("size_total", 0) or 0) for fs in file_systems if fs.get("filesystem_type") == "Primary")
    fs_used   = sum(int(fs.get("size_used", 0) or 0)  for fs in file_systems if fs.get("filesystem_type") == "Primary")
    if total_b == 0:
        total_b = vol_total + fs_total
        used_b  = vol_used + fs_used

    return {
        "system": {
            "name":           a.get("name", ""),
            "model":          a.get("model", ""),
            "serial":         a.get("service_tag", ""),
            "service_code":   a.get("express_service_code", ""),
            "version":        version,
            "nodes":          int(a.get("node_count", 0) or 0),
            "drive_tolerance": a.get("drive_failure_tolerance_level", ""),
            "cluster_name":   cl.get("name", ""),
            "cluster_state":  cl.get("state", ""),
            "mgmt_ip":        cl.get("management_address", ""),
            "global_id":      cl.get("global_id", ""),
        },
        "capacity": {
            "total_bytes": total_b,
            "used_bytes":  used_b,
            "free_bytes":  total_b - used_b,
            "total_tb":    round(total_b / 1e12, 2),
            "used_tb":     round(used_b  / 1e12, 2),
            "free_tb":     round((total_b - used_b) / 1e12, 2),
            "used_pct":    round(used_b / total_b * 100, 1) if total_b else 0,
            "vol_provisioned_bytes": vol_total,
            "vol_used_bytes":        vol_used,
        },
        "volumes":       len(vols),
        "hosts":         len(hosts),
        "host_groups":   len(host_groups),
        "volume_groups": len(volume_groups),
        "snapshots":     len(snaps),
        "file_systems":  len([f for f in file_systems if f.get("filesystem_type") == "Primary"]),
        "fs_snapshots":  len([f for f in file_systems if f.get("filesystem_type") == "Snapshot"]),
        "smb_shares":    len(smb_shares),
        "nfs_exports":   len(nfs_exports),
        "nas_servers":   len(nas_servers),
        "alerts":        len(alerts),
        "snap_rules":    len(snap_rules),
        "eth_ports":     len(eth_ports),
        "fc_ports":      len(fc_ports),
        "perf":          perf,
        "volume_list": [
            {"name": v.get("name",""), "size": v.get("size",0),
             "state": v.get("state",""), "type": v.get("type",""),
             "logical_used": v.get("logical_used",0),
             "wwn": v.get("wwn",""),
             "is_repl": v.get("is_replication_destination", False),
             "created": v.get("creation_timestamp","")}
            for v in vols[:500]],
        "host_list": [
            {"name": h.get("name",""), "os_type": h.get("os_type",""),
             "type": h.get("type",""), "description": h.get("description",""),
             "host_group_id": h.get("host_group_id","")}
            for h in hosts[:500]],
        "host_group_list": [
            {"id": hg.get("id",""), "name": hg.get("name",""),
             "description": hg.get("description",""),
             "connectivity": hg.get("host_connectivity","")}
            for hg in host_groups],
        "volume_group_list": [
            {"name": vg.get("name",""), "description": vg.get("description",""),
             "created": vg.get("creation_timestamp",""),
             "placement": vg.get("placement_rule","")}
            for vg in volume_groups],
        "fs_list": [
            {"name": fs.get("name",""), "size_total": fs.get("size_total",0),
             "size_used": fs.get("size_used",0), "fs_type": fs.get("filesystem_type",""),
             "access": fs.get("access_policy",""), "nas_id": fs.get("nas_server_id",""),
             "created": fs.get("creation_timestamp","")}
            for fs in file_systems],
        "nas_list": [
            {"name": ns.get("name",""), "status": ns.get("operational_status",""),
             "description": ns.get("description",""), "node": ns.get("current_node_id","")}
            for ns in nas_servers],
        "alert_list": [
            {"severity": al.get("severity",""), "state": al.get("state",""),
             "description": al.get("description_l10n",""),
             "resource_type": al.get("resource_type",""),
             "resource_name": al.get("resource_name",""),
             "timestamp": al.get("generated_timestamp","")}
            for al in alerts[:200]],
        "snap_rule_list": [
            {"name": sr.get("name",""), "interval": sr.get("interval",""),
             "time_of_day": sr.get("time_of_day",""),
             "days": sr.get("days_of_week",[]),
             "retention": sr.get("desired_retention",0)}
            for sr in snap_rules],
        "smb_list": [
            {"name": sh.get("name",""), "path": sh.get("path",""),
             "ca": sh.get("is_continuous_availability_enabled", False)}
            for sh in smb_shares],
        "nfs_list": [
            {"name": ex.get("name",""), "path": ex.get("path",""),
             "security": ex.get("min_security",""), "access": ex.get("default_access","")}
            for ex in nfs_exports],
        "eth_port_list": [
            {"name": ep.get("name",""), "speed": ep.get("current_speed",""),
             "link_up": ep.get("is_link_up", False), "mac": ep.get("mac_address","")}
            for ep in eth_ports],
        "fc_port_list": [
            {"name": fp.get("name",""), "wwn": fp.get("wwn",""),
             "speed": fp.get("current_speed",""), "link_up": fp.get("is_link_up", False)}
            for fp in fc_ports],
        "ip_list": [
            {"name": ip.get("name",""), "address": ip.get("address",""),
             "purposes": ip.get("purposes",[])}
            for ip in ip_addrs],
    }

# ── HPE Alletra Storage MP / Primera / 3PAR  WSAPI ────────────────────────────
def _hpe_session(arr: dict) -> tuple:
    """Authenticate to HPE WSAPI and return (base_url, headers_dict).
    Tries port 443 first, then 8080."""
    base = _base(arr)
    cred = {"user": arr["username"], "password": arr["password"]}
    for port in ["", ":8080"]:
        url = f"{base}{port}/api/v1/credentials"
        try:
            r = requests.post(url, json=cred, verify=False, timeout=12)
            if r.status_code in (200, 201):
                tok = r.json().get("key", "")
                if tok:
                    return f"{base}{port}", {"X-HP3PAR-WSAPI-SessionKey": tok}
        except Exception:
            continue
    raise ConnectionError(f"Cannot authenticate to HPE WSAPI at {arr['ip']}")


def _hpe_test(arr: dict) -> dict:
    api_base, hdr = _hpe_session(arr)
    r = requests.get(f"{api_base}/api/v1/system", headers=hdr, verify=False, timeout=15)
    r.raise_for_status()
    d = r.json()
    return {
        "ok": True,
        "message": f"Connected — HPE {d.get('model','')} OS {d.get('systemVersion','')}",
        "system_info": {
            "name":    d.get("name", ""),
            "model":   d.get("model", ""),
            "serial":  d.get("serialNumber", ""),
            "version": d.get("systemVersion", ""),
        },
    }


def _hpe_data(arr: dict) -> dict:
    api_base, hdr = _hpe_session(arr)
    T = 15

    def _g(ep):
        try:
            r = requests.get(f"{api_base}/api/v1/{ep}", headers=hdr, verify=False, timeout=T)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    sys_d   = _g("system")
    vols_d  = _g("volumes")
    hosts_d = _g("hosts")
    hsets_d = _g("hostsets")
    cpgs_d  = _g("cpgs")
    ports_d = _g("ports")
    disks_d = _g("disks")
    vluns_d = _g("vluns")
    vsets_d = _g("volumesets")
    cap_d   = _g("capacity")

    # capacity
    all_cap    = cap_d.get("allCapacity", {})
    total_mib  = all_cap.get("totalMiB", 0) or 0
    alloc      = all_cap.get("allocated", {})
    used_mib   = alloc.get("totalAllocatedMiB", 0) or 0
    total_b    = total_mib * 1024 * 1024
    used_b     = used_mib  * 1024 * 1024
    free_b     = total_b - used_b

    # volumes
    vol_members = vols_d.get("members", [])
    normal_vols = [v for v in vol_members if not v.get("name","").startswith(".")]
    vol_list = []
    for v in normal_vols:
        sz = (v.get("sizeMiB", 0) or 0) * 1024 * 1024
        usr = v.get("userSpace", {})
        used = (usr.get("usedMiB", 0) or 0) * 1024 * 1024
        prov_type = {1: "Full", 2: "Thin", 3: "SNP", 4: "Peer", 5: "Unknown", 6: "TDVV"}.get(v.get("provisioningType", 0), "Unknown")
        state_map = {1: "online", 2: "degraded", 3: "offline", 4: "failed"}
        st = state_map.get(v.get("state", 0), "unknown")
        vol_list.append({
            "name": v.get("name", ""),
            "id": v.get("id", 0),
            "size_bytes": sz,
            "used_bytes": used,
            "used_pct": round(used / sz * 100, 1) if sz else 0,
            "provisioning": prov_type,
            "state": st,
            "copy_type": {1:"base",2:"physCopy",3:"virtualCopy"}.get(v.get("copyType",0),"base"),
            "wwn": v.get("wwn", ""),
            "cpg": v.get("userCPG", ""),
            "snap_cpg": v.get("snapCPG", ""),
            "dedup": v.get("deduplicationState", 0) == 1,
            "compression": v.get("compressionState", 0) == 1,
        })

    # CPGs (like aggregates / tiers)
    cpg_list = []
    for c in cpgs_d.get("members", []):
        usr = c.get("UsrUsage", {})
        sa  = c.get("SAUsage", {})
        sd  = c.get("SDUsage", {})
        total_u = (usr.get("totalMiB", 0) + sa.get("totalMiB", 0) + sd.get("totalMiB", 0))
        used_u  = (usr.get("usedMiB", 0) + sa.get("usedMiB", 0) + sd.get("usedMiB", 0))
        cpg_list.append({
            "name": c.get("name", ""),
            "id": c.get("id", 0),
            "num_fpvv": c.get("numFPVVs", 0),
            "num_tpvv": c.get("numTPVVs", 0),
            "num_tdvv": c.get("numTDVVs", 0),
            "total_mib": total_u,
            "used_mib": used_u,
            "free_mib": total_u - used_u if total_u > used_u else 0,
            "used_pct": round(used_u / total_u * 100, 1) if total_u else 0,
            "private_mib": c.get("privateSpaceMiB", 0),
            "shared_mib":  c.get("sharedSpaceMiB", 0),
            "free_for_alloc_mib": c.get("freeSpaceMiB", 0),
        })

    # Hosts
    host_list = []
    for h in hosts_d.get("members", []):
        fc_paths  = h.get("FCPaths", [])
        isc_paths = h.get("iSCSIPaths", [])
        nvme_paths = h.get("NVMETCPPaths", [])
        proto = "FC" if fc_paths else "iSCSI" if isc_paths else "NVMe-TCP" if nvme_paths else "—"
        ips = [p.get("IPAddr","") for p in (isc_paths or nvme_paths or []) if p.get("IPAddr")]
        host_list.append({
            "name": h.get("name", ""),
            "id": h.get("id", 0),
            "persona": {1:"Generic",2:"GenericALUA",3:"HP-UX",4:"AIX",5:"EGENERA",
                        6:"HPUX-L",7:"SunVCS",8:"VMware",9:"OpenVMS",10:"WindowsServer",
                        11:"AIX-ALUA"}.get(h.get("persona",1),"Generic"),
            "protocol": proto,
            "ip_addrs": ips[:3],
            "fc_wwns": [p.get("wwn","") for p in fc_paths[:4]],
            "iscsi_names": [p.get("name","") for p in isc_paths[:2]],
            "chap_enabled": h.get("initiatorChapEnabled", False),
        })

    # Host Sets
    hset_list = []
    for hs in hsets_d.get("members", []):
        hset_list.append({
            "name": hs.get("name", ""),
            "id": hs.get("id", 0),
            "members": hs.get("setmembers", []),
            "count": len(hs.get("setmembers", [])),
        })

    # Ports
    port_list = []
    type_map = {1:"FC",2:"ETH",4:"ISCSI",5:"CNA",6:"NVME"}
    for pt in ports_d.get("members", []):
        pos = pt.get("portPos", {})
        port_list.append({
            "position": f"{pos.get('node',0)}:{pos.get('slot',0)}:{pos.get('cardPort',0)}",
            "type": type_map.get(pt.get("type", 0), "Unknown"),
            "protocol": {1:"FC",2:"iSCSI",3:"FCOE",4:"IP",5:"SAS",6:"NVME"}.get(pt.get("protocol",0),"—"),
            "link_state": {1:"CONFIG_WAIT",2:"ALPA_WAIT",3:"LOGIN_WAIT",4:"READY",
                           5:"LOSS_SYNC",6:"ERROR_STATE",7:"XXX",8:"NONPARTICIPATE",
                           9:"COREDUMP",10:"OFFLINE",11:"FWDEAD",12:"IDLE_FC",
                           13:"IDLE_ISCSI",14:"DISABLED"}.get(pt.get("linkState",0),"unknown"),
            "label": pt.get("label", ""),
            "wwn": pt.get("portWWN", ""),
            "mode": {1:"SUSPENDED",2:"TARGET",3:"INITIATOR",4:"PEER"}.get(pt.get("mode",0),"—"),
            "speed": pt.get("connectedSpeed","—") if pt.get("connectedSpeed") else "—",
        })

    # Disks
    disk_list = []
    for dk in disks_d.get("members", []):
        disk_list.append({
            "id": dk.get("id", 0),
            "position": str(dk.get("position", "")),
            "type": {1:"FC",2:"NL",3:"SSD",4:"NVME"}.get(dk.get("type",0),"Unknown"),
            "state": {1:"normal",2:"degraded",3:"new",4:"failed",5:"unknown"}.get(dk.get("state",0),"unknown"),
            "total_mib": dk.get("totalSizeMiB", 0),
            "free_mib": dk.get("freeSizeMiB", 0),
            "capacity_gb": dk.get("mfgCapacityGB", 0),
            "manufacturer": dk.get("manufacturer", "").strip(),
            "model": dk.get("model", "").strip(),
            "serial": dk.get("serialNumber", "").strip(),
            "fw_version": dk.get("fwVersion", "").strip(),
            "media": {1:"HDD",2:"SSD",3:"NVME"}.get(dk.get("mediaType",0),"Unknown"),
            "protocol": {1:"FC",2:"SAS",3:"SATA",4:"NVME",5:"NVME2"}.get(dk.get("protocol",0),"—"),
        })

    # VLUNs (virtual LUN mappings)
    vlun_list = []
    for vl in vluns_d.get("members", []):
        pos = vl.get("portPos", {})
        vlun_list.append({
            "lun": vl.get("lun", 0),
            "volume": vl.get("volumeName", ""),
            "host": vl.get("hostname", ""),
            "port": f"{pos.get('node',0)}:{pos.get('slot',0)}:{pos.get('cardPort',0)}" if pos else "—",
            "type": {1:"empty",2:"port",3:"host",4:"matched_set",5:"host_set"}.get(vl.get("type",0),"—"),
            "active": vl.get("active", False),
            "volume_wwn": vl.get("volumeWWN", ""),
        })

    # Volume Sets
    vset_list = []
    for vs in vsets_d.get("members", []):
        vset_list.append({
            "name": vs.get("name", ""),
            "id": vs.get("id", 0),
            "members": vs.get("setmembers", []),
            "count": vs.get("count", len(vs.get("setmembers", []))),
            "qos": vs.get("qosEnabled", False),
        })

    # Performance (try to get from system reporter)
    perf = {}
    try:
        pr = requests.get(f"{api_base}/api/v1/systemreporter/attime/portstatistics/hires",
                          headers=hdr, verify=False, timeout=10)
        if pr.status_code == 200:
            ms = pr.json().get("members", [])
            if ms:
                latest = ms[-1]
                rw = latest.get("IO", {}).get("read", {})
                ww = latest.get("IO", {}).get("write", {})
                perf = {
                    "iops_read":       int(rw.get("IOSPerSec", 0) or 0),
                    "iops_write":      int(ww.get("IOSPerSec", 0) or 0),
                    "iops_total":      int((rw.get("IOSPerSec", 0) or 0) + (ww.get("IOSPerSec", 0) or 0)),
                    "latency_read_us": int((rw.get("ServiceTimeMS", 0) or 0) * 1000),
                    "latency_write_us":int((ww.get("ServiceTimeMS", 0) or 0) * 1000),
                    "throughput_read": round((rw.get("KBytesPerSec", 0) or 0) / 1024 / 1024, 2),
                    "throughput_write":round((ww.get("KBytesPerSec", 0) or 0) / 1024 / 1024, 2),
                }
    except Exception:
        pass

    # node info from system
    nodes = sys_d.get("totalNodes", 0)
    online = sys_d.get("onlineNodes", [])

    return {
        "system": {
            "name":    sys_d.get("name", ""),
            "model":   sys_d.get("model", ""),
            "serial":  sys_d.get("serialNumber", ""),
            "version": sys_d.get("systemVersion", ""),
            "nodes":   nodes,
            "online_nodes": online,
            "contact": sys_d.get("contact", ""),
            "ipv4":    sys_d.get("IPv4Addr", ""),
        },
        "capacity": {
            "total_bytes": total_b,
            "used_bytes":  used_b,
            "free_bytes":  free_b,
            "total_tb":    round(total_b / 1e12, 2),
            "used_tb":     round(used_b  / 1e12, 2),
            "free_tb":     round(free_b  / 1e12, 2),
            "used_pct":    round(used_b / total_b * 100, 1) if total_b else 0,
        },
        "volumes":    len(normal_vols),
        "hosts":      len(host_list),
        "host_sets":  len(hset_list),
        "cpgs":       len(cpg_list),
        "ports":      len(port_list),
        "disks":      len(disk_list),
        "vluns":      len(vlun_list),
        "volume_sets":len(vset_list),
        "volume_list": vol_list,
        "host_list":   host_list,
        "host_set_list": hset_list,
        "cpg_list":    cpg_list,
        "port_list":   port_list,
        "disk_list":   disk_list,
        "vlun_list":   vlun_list,
        "volume_set_list": vset_list,
        "perf": perf,
    }


# ── Pure Storage FlashBlade REST API ─────────────────────────────────────────
# Auth: POST /api/login with header api-token → returns x-auth-token
# API version auto-detected from /api/api_version (prefer 2.x, fallback 1.12)

def _fb_session(arr: dict) -> tuple:
    """Returns (session, api_version_str) with auth already set."""
    base = _base(arr)
    api_token = (arr.get("api_token") or "").strip()
    if not api_token:
        raise ConnectionError("API Token is required for Pure Storage FlashBlade")

    s = requests.Session()
    s.verify = False
    s.timeout = 20
    s.headers.update({"Content-Type": "application/json", "Accept": "application/json"})

    # Discover API versions
    api_ver = "1.12"
    try:
        vr = s.get(f"{base}/api/api_version", timeout=10)
        if vr.status_code == 200:
            versions = vr.json().get("versions", [])
            # prefer highest version
            if versions:
                api_ver = str(versions[-1])
    except Exception:
        pass

    # Login with api-token header
    lr = s.post(f"{base}/api/login", headers={**dict(s.headers), "api-token": api_token}, timeout=15)
    if lr.status_code != 200:
        raise ConnectionError(f"FlashBlade login failed HTTP {lr.status_code}: {lr.text[:200]}")
    tok = lr.headers.get("x-auth-token", "")
    if not tok:
        raise ConnectionError("FlashBlade login returned no x-auth-token")
    s.headers.update({"x-auth-token": tok})
    return s, api_ver


def _fb_items(resp):
    """Extract items list from FlashBlade paginated response."""
    if resp is None:
        return []
    d = resp.json()
    if isinstance(d, dict):
        return d.get("items", [])
    if isinstance(d, list):
        return d
    return []


def _pure_test(arr: dict) -> dict:
    base = _base(arr)
    s, api_ver = _fb_session(arr)
    r = s.get(f"{base}/api/{api_ver}/arrays", timeout=15)
    r.raise_for_status()
    items = _fb_items(r)
    d = items[0] if items else {}
    return {
        "ok": True,
        "message": f"Connected — Pure FlashBlade {d.get('name','')} {d.get('os','')} v{d.get('version','')}".strip(),
        "system_info": {
            "name":    d.get("name", ""),
            "model":   d.get("os", "FlashBlade"),
            "serial":  d.get("id", ""),
            "version": d.get("version", ""),
            "api_version": api_ver,
        }
    }


def _pure_data(arr: dict) -> dict:
    base = _base(arr)
    s, api_ver = _fb_session(arr)

    def _g(path, params=None, ver=None):
        r = s.get(f"{base}/api/{ver or api_ver}{path}", params=params, timeout=20)
        if r.status_code in (400, 404):
            return []
        r.raise_for_status()
        return _fb_items(r)

    # System info
    sys_items = _g("/arrays")
    sinfo = sys_items[0] if sys_items else {}

    # Capacity — use v1.12 /arrays/space which returns capacity fields
    cap = {}
    try:
        sp_items = _g("/arrays/space", ver="1.12")
        if sp_items:
            sp = sp_items[0]
            total_b = int(sp.get("capacity", 0) or 0)
            space = sp.get("space", {})
            used_b = int(space.get("total_physical", 0) or 0)
            virtual_b = int(space.get("virtual", 0) or 0)
            dr = space.get("data_reduction", 1.0)
            cap = {
                "total_bytes": total_b,
                "used_bytes": used_b,
                "free_bytes": total_b - used_b,
                "total_tb": round(total_b / 1e12, 2),
                "used_tb": round(used_b / 1e12, 2),
                "free_tb": round((total_b - used_b) / 1e12, 2),
                "used_pct": round(used_b / total_b * 100, 1) if total_b else 0,
                "virtual_tb": round(virtual_b / 1e12, 2),
                "data_reduction": round(dr, 2) if dr else 1.0,
            }
    except Exception:
        pass

    # File systems
    fs_items = _g("/file-systems")
    file_systems = []
    for fs in fs_items:
        sp = fs.get("space", {}) or {}
        prov = fs.get("provisioned", 0) or 0
        file_systems.append({
            "name": fs.get("name", ""),
            "provisioned_gb": round(prov / (1024**3), 1),
            "virtual_gb": round((sp.get("virtual", 0) or 0) / (1024**3), 2),
            "unique_gb": round((sp.get("unique", 0) or 0) / (1024**3), 2),
            "data_reduction": sp.get("data_reduction", 0),
            "nfs": fs.get("nfs_enabled", False),
            "smb": fs.get("smb_enabled", False),
            "destroyed": fs.get("destroyed", False),
        })

    # Buckets (S3)
    bkt_items = _g("/buckets")
    buckets = []
    for b in bkt_items:
        sp = b.get("space", {}) or {}
        acct = b.get("account", {})
        buckets.append({
            "name": b.get("name", ""),
            "account": acct.get("name", "") if isinstance(acct, dict) else str(acct),
            "virtual_gb": round((sp.get("virtual", 0) or 0) / (1024**3), 2),
            "unique_gb": round((sp.get("unique", 0) or 0) / (1024**3), 2),
            "object_count": b.get("object_count", 0),
            "versioning": b.get("versioning", ""),
            "destroyed": b.get("destroyed", False),
        })

    # Blades
    blade_items = _g("/blades")
    blades = []
    healthy_count = 0
    total_raw = 0
    for bl in blade_items:
        raw = bl.get("raw_capacity", 0) or 0
        total_raw += raw
        st = bl.get("status", "")
        if st == "healthy":
            healthy_count += 1
        blades.append({
            "name": bl.get("name", ""),
            "status": st,
            "raw_tb": round(raw / 1e12, 2),
        })

    # Hardware connectors (chassis components)
    hw_items = []
    try:
        hw_items = _g("/hardware")
    except Exception:
        pass
    fb_hw = []
    for h in hw_items:
        fb_hw.append({
            "name":    h.get("name", ""),
            "type":    h.get("type", ""),
            "status":  h.get("status", ""),
            "slot":    h.get("slot"),
            "speed":   h.get("speed"),
            "serial":  h.get("serial", ""),
            "identify": h.get("identify", ""),
            "index":   h.get("index"),
        })

    # Network interfaces
    net_items = _g("/network-interfaces")
    networks = [{"name": n.get("name", ""), "address": n.get("address", ""),
                 "type": n.get("type", "")} for n in net_items]

    # Object store accounts
    acct_items = _g("/object-store-accounts")
    accounts = [{"name": a.get("name", "")} for a in acct_items]

    # Alerts
    alert_items = _g("/alerts", {"filter": "state='open'"})
    alerts = [{"severity": a.get("severity", ""), "summary": a.get("summary", ""),
               "component": a.get("component_name", "")} for a in alert_items]

    # Policies
    pol_items = _g("/policies")
    policies = [{"name": p.get("name", ""), "enabled": p.get("enabled", False),
                 "rules": len(p.get("rules", []))} for p in pol_items]

    # File system snapshots
    snap_count = 0
    try:
        sr = s.get(f"{base}/api/{api_ver}/file-system-snapshots", timeout=15)
        if sr.status_code == 200:
            snap_count = sr.json().get("total_item_count", len(_fb_items(sr)))
    except Exception:
        pass

    # Performance
    perf = {}
    try:
        perf_items = _g("/arrays/performance")
        pf = perf_items[0] if perf_items else {}
        perf = {
            "writes_per_sec": round(pf.get("writes_per_sec", 0) or 0, 1),
            "reads_per_sec": round(pf.get("reads_per_sec", 0) or 0, 1),
            "usec_per_write": round(pf.get("usec_per_write_op", 0) or 0, 1),
            "usec_per_read": round(pf.get("usec_per_read_op", 0) or 0, 1),
            "write_bps": round((pf.get("write_bytes_per_sec", 0) or 0) / 1e6, 2),
            "read_bps": round((pf.get("read_bytes_per_sec", 0) or 0) / 1e6, 2),
        }
    except Exception:
        pass

    return {
        "system": {
            "name": sinfo.get("name", ""),
            "model": sinfo.get("os", "FlashBlade"),
            "version": sinfo.get("version", ""),
            "serial": sinfo.get("id", ""),
        },
        "capacity": cap,
        "file_systems": file_systems,
        "buckets": buckets,
        "blades": blades,
        "networks": networks,
        "accounts": accounts,
        "alerts": alerts,
        "policies": policies,
        "hardware": fb_hw,
        "perf": perf,
        "summary": {
            "fs_count": len(file_systems),
            "bucket_count": len(buckets),
            "blade_count": len(blade_items),
            "blades_healthy": healthy_count,
            "blade_raw_tb": round(total_raw / 1e12, 2),
            "network_count": len(networks),
            "account_count": len(accounts),
            "alert_count": len(alerts),
            "policy_count": len(policies),
            "snapshot_count": snap_count,
        },
    }

# ── IBM FlashSystem REST API ────────────────────────────────────────────────────
def _ibm_test(arr: dict) -> dict:
    base = _base(arr)
    s = _sess(arr)
    r = s.get(f"{base}/rest/v1/lssystem", timeout=15)
    r.raise_for_status()
    d = r.json()
    if isinstance(d, list): d = d[0] if d else {}
    return {
        "ok": True,
        "message": f"Connected — IBM {d.get('product_name','')} {d.get('code_level','')}",
        "system_info": {
            "name":    d.get("name", ""),
            "model":   d.get("product_name", ""),
            "serial":  d.get("id_alias", d.get("id", "")),
            "version": d.get("code_level", ""),
        }
    }

def _ibm_data(arr: dict) -> dict:
    base = _base(arr)
    s = _sess(arr)

    sys_d  = s.get(f"{base}/rest/v1/lssystem").json()
    vols_d = s.get(f"{base}/rest/v1/lsvdisk").json()
    hosts_d= s.get(f"{base}/rest/v1/lshost").json()
    snaps_d= s.get(f"{base}/rest/v1/lsfcmap").json()
    drv_d  = s.get(f"{base}/rest/v1/lsdrive").json()
    pool_d = s.get(f"{base}/rest/v1/lsmdiskgrp").json()

    sys  = (sys_d  if isinstance(sys_d, dict)  else (sys_d[0]  if sys_d  else {}))
    pods = pool_d  if isinstance(pool_d, list) else []

    def _cap(s_in): 
        """Convert IBM capacity string like '1.00TB' to bytes"""
        if not s_in: return 0
        s_in = str(s_in).upper().strip()
        try:
            if "TB" in s_in: return float(s_in.replace("TB",""))*1e12
            if "GB" in s_in: return float(s_in.replace("GB",""))*1e9
            if "MB" in s_in: return float(s_in.replace("MB",""))*1e6
            return float(s_in)
        except: return 0

    total_b = sum(_cap(p.get("capacity")) for p in pods)
    used_b  = sum(_cap(p.get("used_capacity")) for p in pods)

    perf = {}
    try:
        pm = s.get(f"{base}/rest/v1/lsnodestats").json()
        if isinstance(pm, list) and pm:
            tot_r = tot_w = 0
            for node in pm:
                tot_r += float(node.get("read_data_rate",  0) or 0)
                tot_w += float(node.get("write_data_rate", 0) or 0)
            perf = {
                "throughput_read":  round(tot_r / 1024, 2),
                "throughput_write": round(tot_w / 1024, 2),
                "iops_read":        sum(int(n.get("read_io_rate",  0) or 0) for n in pm),
                "iops_write":       sum(int(n.get("write_io_rate", 0) or 0) for n in pm),
            }
    except Exception:
        pass

    return {
        "system": {
            "name":    sys.get("name", ""),
            "model":   sys.get("product_name", ""),
            "serial":  sys.get("id_alias", ""),
            "version": sys.get("code_level", ""),
            "nodes":   int(sys.get("node_count", 0) or 0),
        },
        "capacity": {
            "total_bytes": total_b,
            "used_bytes":  used_b,
            "free_bytes":  total_b - used_b,
            "total_tb":    round(total_b / 1e12, 2),
            "used_tb":     round(used_b  / 1e12, 2),
            "free_tb":     round((total_b - used_b) / 1e12, 2),
            "used_pct":    round(used_b / total_b * 100, 1) if total_b else 0,
        },
        "volumes":   len(vols_d  if isinstance(vols_d,  list) else []),
        "hosts":     len(hosts_d if isinstance(hosts_d, list) else []),
        "snapshots": len(snaps_d if isinstance(snaps_d, list) else []),
        "disks":     len(drv_d   if isinstance(drv_d,   list) else []),
        "perf":      perf,
    }

# ── Hitachi VSP REST API ───────────────────────────────────────────────────────
def _hitachi_test(arr: dict) -> dict:
    base = _base(arr)
    s = _sess(arr)
    r = s.get(f"{base}/ConfigurationManager/v1/objects/storages", timeout=15)
    r.raise_for_status()
    items = r.json().get("data", r.json().get("storages", [r.json()]))
    d = items[0] if items else {}
    return {
        "ok": True,
        "message": f"Connected — Hitachi {d.get('model','')} {d.get('svpVersion','')}",
        "system_info": {
            "name":    d.get("storageDeviceId", ""),
            "model":   d.get("model", ""),
            "serial":  str(d.get("serialNumber", "")),
            "version": d.get("svpVersion", d.get("dkcMicroVersion", "")),
        }
    }

def _hitachi_data(arr: dict) -> dict:
    base = _base(arr)
    s = _sess(arr)
    CM = f"{base}/ConfigurationManager/v1"

    stor  = s.get(f"{CM}/objects/storages").json()
    items = stor.get("data", stor.get("storages", [stor]))
    d     = items[0] if items else {}
    dev   = d.get("storageDeviceId", "")

    vols  = s.get(f"{CM}/objects/storages/{dev}/ldevs",  params={"ldevOption":"defined"}).json()
    hosts = s.get(f"{CM}/objects/storages/{dev}/host-groups").json()
    pools = s.get(f"{CM}/objects/storages/{dev}/pools").json()

    pool_list = pools.get("data", [])
    total_b = sum(p.get("totalPhysicalCapacity", 0) * 512 for p in pool_list)
    used_b  = sum(p.get("usedPhysicalCapacity",  0) * 512 for p in pool_list)

    return {
        "system": {
            "name":    d.get("storageDeviceId", ""),
            "model":   d.get("model", ""),
            "serial":  str(d.get("serialNumber", "")),
            "version": d.get("dkcMicroVersion", ""),
            "nodes":   int(d.get("controllerCount", 0) or 0),
        },
        "capacity": {
            "total_bytes": total_b,
            "used_bytes":  used_b,
            "free_bytes":  total_b - used_b,
            "total_tb":    round(total_b / 1e12, 2),
            "used_tb":     round(used_b  / 1e12, 2),
            "free_tb":     round((total_b - used_b) / 1e12, 2),
            "used_pct":    round(used_b / total_b * 100, 1) if total_b else 0,
        },
        "volumes": len(vols.get("data",  [])),
        "hosts":   len(hosts.get("data", [])),
        "pools":   len(pool_list),
        "perf":    {},
    }


# -- Pure Storage FlashArray REST API v2 -----------------------------------------
def _fa_session(arr: dict) -> tuple:
    """Authenticate to FlashArray, return (session, api_version, base_url, is_v2)."""
    base = _base(arr)
    s = requests.Session()
    s.verify = False
    s.timeout = 20
    s.headers.update({"Content-Type": "application/json"})

    # Discover available API versions
    versions = []
    try:
        vr = s.get(f"{base}/api/api_version", timeout=10)
        if vr.status_code == 200:
            versions = vr.json().get("version", [])
    except Exception:
        pass

    v2_versions = [v for v in versions if v.startswith("2.")]
    v1_versions = [v for v in versions if v.startswith("1.")]
    is_v2 = len(v2_versions) > 0

    # Pick the best v1 version for obtaining api_token
    best_v1 = v1_versions[-1] if v1_versions else "1.16"

    # Get API token via v1 endpoint (username/password)
    api_token = (arr.get("api_token") or "").strip()
    if not api_token:
        tr = s.post(f"{base}/api/{best_v1}/auth/apitoken",
                     json={"username": arr["username"], "password": arr["password"]},
                     timeout=15)
        if tr.status_code == 200:
            api_token = tr.json().get("api_token", "")
    if not api_token:
        raise ConnectionError("Cannot obtain FlashArray API token")

    if is_v2:
        # v2 login
        api_ver = v2_versions[-1]
        lr = s.post(f"{base}/api/{api_ver}/login",
                    headers={**dict(s.headers), "api-token": api_token}, timeout=15)
        if lr.status_code != 200:
            raise ConnectionError(f"FlashArray v2 login failed HTTP {lr.status_code}")
        x_auth = lr.headers.get("x-auth-token", "")
        if not x_auth:
            raise ConnectionError("FlashArray login returned no x-auth-token")
        s.headers.update({"x-auth-token": x_auth})
    else:
        # v1-only: create session with api_token
        api_ver = best_v1
        sr = s.post(f"{base}/api/{api_ver}/auth/session",
                    json={"api_token": api_token}, timeout=15)
        if sr.status_code != 200:
            raise ConnectionError(f"FlashArray v1 session failed HTTP {sr.status_code}")

    return s, api_ver, base, is_v2


def _fa_test(arr: dict) -> dict:
    s, api_ver, base, is_v2 = _fa_session(arr)
    if is_v2:
        r = s.get(f"{base}/api/{api_ver}/arrays", timeout=15)
        r.raise_for_status()
        items = r.json().get("items", [])
        a = items[0] if items else {}
        name = a.get("name", "")
        version = a.get("version", a.get("os", ""))
        serial = a.get("id", "")
    else:
        r = s.get(f"{base}/api/{api_ver}/array", timeout=15)
        r.raise_for_status()
        a = r.json()
        name = a.get("array_name", "")
        version = a.get("version", "")
        serial = a.get("id", "")
    return {
        "ok": True,
        "message": f"Connected \u2014 Pure FlashArray {name} Purity {version}",
        "system_info": {
            "name":    name,
            "model":   "FlashArray",
            "serial":  serial,
            "version": version,
        }
    }


def _fa_data(arr: dict) -> dict:
    s, api_ver, base, is_v2 = _fa_session(arr)
    T = 15
    if is_v2:
        return _fa_data_v2(s, api_ver, base, T)
    else:
        return _fa_data_v1(s, api_ver, base, T)


def _fa_data_v2(s, api_ver, base, T):
    """Fetch FlashArray data using REST API v2.x."""

    def _g(ep, limit=5000):
        try:
            r = s.get(f"{base}/api/{api_ver}/{ep}?limit={limit}", timeout=T)
            if r.status_code == 200:
                return r.json().get("items", [])
        except Exception:
            pass
        return []

    arr_info  = _g("arrays")
    arr_space = _g("arrays/space")
    vols_raw  = _g("volumes")
    hosts_raw = _g("hosts")
    hgroups   = _g("host-groups")
    drives    = _g("drives")
    ports     = _g("ports")
    conns     = _g("connections")
    pgroups   = _g("protection-groups")
    vol_snaps = _g("volume-snapshots")
    net_ifs   = _g("network-interfaces")
    alerts    = _g("alerts")
    ctrls     = _g("controllers")
    hw_items  = _g("hardware")

    # System
    ai = arr_info[0] if arr_info else {}
    sp = (arr_space[0] if arr_space else {}).get("space", {})
    cap_bytes = (arr_space[0] if arr_space else {}).get("capacity", 0) or 0
    total_phys = sp.get("total_physical", 0) or 0
    free_b = cap_bytes - total_phys if cap_bytes > total_phys else 0

    # Volumes (exclude destroyed)
    active_vols = [v for v in vols_raw if not v.get("destroyed")]
    vol_list = []
    for v in active_vols:
        vsp = v.get("space", {}) or {}
        prov = v.get("provisioned", 0) or 0
        tp = vsp.get("total_physical", 0) or 0
        dr = vsp.get("data_reduction", 1) or 1
        vol_list.append({
            "name": v.get("name", ""),
            "serial": v.get("serial", ""),
            "provisioned_bytes": prov,
            "used_bytes": tp,
            "used_pct": round(tp / prov * 100, 1) if prov else 0,
            "data_reduction": round(dr, 2),
            "created": v.get("created", 0),
            "destroyed": v.get("destroyed", False),
            "pod": (v.get("pod", {}) or {}).get("name", ""),
        })

    # Hosts (exclude destroyed)
    active_hosts = [h for h in hosts_raw if not h.get("destroyed")]
    host_list = []
    for h in active_hosts:
        hg = (h.get("host_group", {}) or {}).get("name", "")
        host_list.append({
            "name": h.get("name", ""),
            "iqns": h.get("iqns", []) or [],
            "wwns": h.get("wwns", []) or [],
            "nqns": h.get("nqns", []) or [],
            "host_group": hg,
            "connection_count": h.get("connection_count", 0),
            "protocol": "FC" if h.get("wwns") else "iSCSI" if h.get("iqns") else "NVMe" if h.get("nqns") else "\u2014",
        })

    # Host groups
    hg_list = []
    for hg in hgroups:
        if not hg.get("destroyed"):
            hg_list.append({
                "name": hg.get("name", ""),
                "host_count": hg.get("host_count", 0),
                "connection_count": hg.get("connection_count", 0),
            })

    # Drives
    drive_list = []
    for d in drives:
        drive_list.append({
            "name": d.get("name", ""),
            "type": d.get("type", ""),
            "status": d.get("status", ""),
            "capacity_bytes": d.get("capacity", 0) or 0,
            "protocol": d.get("protocol", "\u2014"),
        })

    # Ports
    port_list = []
    for pt in ports:
        port_list.append({
            "name": pt.get("name", ""),
            "wwn": pt.get("wwn", ""),
            "iqn": pt.get("iqn", ""),
            "nqn": pt.get("nqn", ""),
            "failover": pt.get("failover", ""),
        })

    # Connections (LUN mappings)
    conn_list = []
    for c in conns:
        conn_list.append({
            "host": (c.get("host", {}) or {}).get("name", ""),
            "host_group": (c.get("host_group", {}) or {}).get("name", ""),
            "volume": (c.get("volume", {}) or {}).get("name", ""),
            "lun": c.get("lun", 0),
        })

    # Protection groups
    pg_list = []
    for pg in pgroups:
        if not pg.get("destroyed"):
            pg_list.append({
                "name": pg.get("name", ""),
                "host_count": pg.get("host_count", 0),
                "volume_count": pg.get("volume_count", 0) if "volume_count" in pg else 0,
                "target_count": pg.get("target_count", 0),
            })

    # Controllers
    ctrl_list = []
    for ct in ctrls:
        ctrl_list.append({
            "name": ct.get("name", ""),
            "model": ct.get("model", ""),
            "version": ct.get("version", ""),
            "status": ct.get("status", ""),
            "mode": ct.get("mode", ""),
        })

    # Hardware components (for chassis visualisation)
    hw_components = []
    for h in hw_items:
        hw_components.append({
            "name":      h.get("name", ""),
            "type":      h.get("type", ""),
            "status":    h.get("status", ""),
            "identify":  h.get("identify", ""),
            "index":     h.get("index"),
            "slot":      h.get("slot"),
            "speed":     h.get("speed"),
            "temperature": h.get("temperature"),
            "voltage":   h.get("voltage"),
            "model":     h.get("model", ""),
            "serial":    h.get("serial", ""),
        })
    # Classify by type for the frontend chassis view
    hw_by_type = {}
    for hc in hw_components:
        t = hc["type"] or "other"
        hw_by_type.setdefault(t, []).append(hc)
    hw_summary = {t: {"total": len(items), "healthy": sum(1 for i in items if i["status"] in ("ok","healthy","normal","not_installed"))} for t, items in hw_by_type.items()}

    # Alerts (open)
    open_alerts = [a for a in alerts if a.get("state") == "open"]
    alert_list = []
    for a in open_alerts:
        alert_list.append({
            "severity": a.get("severity", ""),
            "category": a.get("category", ""),
            "component": a.get("component_type", ""),
            "description": a.get("description", ""),
            "state": a.get("state", ""),
            "created": a.get("created", 0),
        })

    return {
        "system": {
            "name":    ai.get("name", ""),
            "model":   "FlashArray " + (ctrl_list[0]["model"] if ctrl_list else ""),
            "serial":  ai.get("id", ""),
            "version": ai.get("version", ai.get("os", "")),
            "parity":  ai.get("parity", ""),
        },
        "capacity": {
            "total_bytes": cap_bytes,
            "used_bytes":  total_phys,
            "free_bytes":  free_b,
            "total_tb":    round(cap_bytes / 1e12, 2),
            "used_tb":     round(total_phys / 1e12, 2),
            "free_tb":     round(free_b / 1e12, 2),
            "used_pct":    round(total_phys / cap_bytes * 100, 1) if cap_bytes else 0,
            "data_reduction": round(sp.get("data_reduction", 1) or 1, 2),
            "thin_provisioning_pct": round((sp.get("thin_provisioning", 0) or 0) * 100, 1),
        },
        "volumes":      len(active_vols),
        "hosts":        len(active_hosts),
        "host_groups":  len(hg_list),
        "drives":       len(drive_list),
        "ports":        len(port_list),
        "connections":  len(conn_list),
        "pgroups":      len(pg_list),
        "snapshots":    len(vol_snaps),
        "controllers":  len(ctrl_list),
        "alerts":       len(open_alerts),
        "total_alerts": len(alerts),
        "volume_list":      vol_list,
        "host_list":        host_list,
        "host_group_list":  hg_list,
        "drive_list":       drive_list,
        "port_list":        port_list,
        "connection_list":  conn_list,
        "pgroup_list":      pg_list,
        "controller_list":  ctrl_list,
        "alert_list":       alert_list,
        "hardware":         hw_components,
        "hw_by_type":       hw_by_type,
        "hw_summary":       hw_summary,
    }


def _fa_data_v1(s, api_ver, base, T):
    """Fetch FlashArray data using REST API v1.x (Purity 5.x and older)."""

    def _g1(ep):
        try:
            r = s.get(f"{base}/api/{api_ver}/{ep}", timeout=T)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return []

    arr_info  = _g1("array")                    # dict
    arr_space = _g1("array?space=true")          # list of 1 dict
    ctrls_raw = _g1("array?controllers=true")    # list of dicts
    vols_raw  = _g1("volume")                    # list
    vol_space = _g1("volume?space=true")         # list with space info
    hosts_raw = _g1("host")                      # list
    hgroups   = _g1("hgroup")                    # list
    drives    = _g1("drive")                     # list
    ports     = _g1("port")                      # list
    conns     = _g1("volume?connect=true")       # list
    pgroups   = _g1("pgroup")                    # list
    snaps     = _g1("volume?snap=true")          # list
    alerts    = _g1("message?flagged=true")      # list

    # Build space lookup by volume name
    space_by_name = {}
    if isinstance(vol_space, list):
        for vs in vol_space:
            space_by_name[vs.get("name", "")] = vs

    # System (v1 array response is a flat dict)
    ai = arr_info if isinstance(arr_info, dict) else {}
    sp_data = arr_space[0] if isinstance(arr_space, list) and arr_space else {}
    cap_bytes = sp_data.get("capacity", 0) or 0
    total_used = sp_data.get("total", 0) or 0
    free_b = cap_bytes - total_used if cap_bytes > total_used else 0
    data_reduction = sp_data.get("data_reduction", 1) or 1
    thin_prov = sp_data.get("thin_provisioning", 0) or 0

    # Volumes
    vols_list = vols_raw if isinstance(vols_raw, list) else []
    vol_list = []
    for v in vols_list:
        vname = v.get("name", "")
        vs = space_by_name.get(vname, {})
        prov = v.get("size", 0) or 0
        used = vs.get("total", 0) or 0
        dr = vs.get("data_reduction", 1) or 1
        vol_list.append({
            "name": vname,
            "serial": v.get("serial", ""),
            "provisioned_bytes": prov,
            "used_bytes": used,
            "used_pct": round(used / prov * 100, 1) if prov else 0,
            "data_reduction": round(dr, 2),
            "created": v.get("created", ""),
            "destroyed": False,
            "pod": "",
        })

    # Hosts
    hosts_list = hosts_raw if isinstance(hosts_raw, list) else []
    host_list = []
    for h in hosts_list:
        iqns = h.get("iqn", []) or []
        wwns = h.get("wwn", []) or []
        nqns = h.get("nqn", []) or []
        host_list.append({
            "name": h.get("name", ""),
            "iqns": iqns,
            "wwns": wwns,
            "nqns": nqns,
            "host_group": h.get("hgroup", "") or "",
            "connection_count": 0,
            "protocol": "FC" if wwns else "iSCSI" if iqns else "NVMe" if nqns else "\u2014",
        })

    # Host groups
    hg_raw = hgroups if isinstance(hgroups, list) else []
    hg_list = []
    for hg in hg_raw:
        hosts_in = hg.get("hosts", []) or []
        hg_list.append({
            "name": hg.get("name", ""),
            "host_count": len(hosts_in),
            "connection_count": 0,
        })

    # Drives
    drv_raw = drives if isinstance(drives, list) else []
    drive_list = []
    for d in drv_raw:
        drive_list.append({
            "name": d.get("name", ""),
            "type": d.get("type", ""),
            "status": d.get("status", ""),
            "capacity_bytes": d.get("capacity", 0) or 0,
            "protocol": d.get("protocol", "\u2014"),
        })

    # Ports
    port_raw = ports if isinstance(ports, list) else []
    port_list = []
    for pt in port_raw:
        port_list.append({
            "name": pt.get("name", ""),
            "wwn": pt.get("wwn", "") or "",
            "iqn": pt.get("iqn", "") or "",
            "nqn": pt.get("nqn", "") or "",
            "failover": pt.get("failover", "") or "",
        })

    # Connections (LUN mappings) - v1 uses volume?connect=true
    conn_raw = conns if isinstance(conns, list) else []
    conn_list = []
    for c in conn_raw:
        conn_list.append({
            "host": c.get("host", ""),
            "host_group": c.get("hgroup", "") or "",
            "volume": c.get("name", ""),
            "lun": c.get("lun", 0),
        })

    # Protection groups
    pg_raw = pgroups if isinstance(pgroups, list) else []
    pg_list = []
    for pg in pg_raw:
        pg_vols = pg.get("volumes", []) or []
        pg_targets = pg.get("targets", []) or []
        pg_hosts = pg.get("hosts", []) or []
        pg_list.append({
            "name": pg.get("name", ""),
            "host_count": len(pg_hosts),
            "volume_count": len(pg_vols),
            "target_count": len(pg_targets),
        })

    # Controllers
    ctrl_raw = ctrls_raw if isinstance(ctrls_raw, list) else []
    ctrl_list = []
    for ct in ctrl_raw:
        ctrl_list.append({
            "name": ct.get("name", ""),
            "model": ct.get("model", ""),
            "version": ct.get("version", ""),
            "status": ct.get("status", ""),
            "mode": ct.get("mode", ""),
        })

    # Hardware components (synthesised from controllers + drives for v1)
    hw_components = []
    for ct in ctrl_list:
        hw_components.append({"name":ct["name"],"type":"controller","status":ct.get("status","ok"),"model":ct.get("model",""),"serial":"","index":None,"slot":None,"speed":None,"temperature":None,"voltage":None,"identify":""})
    for d in drive_list:
        hw_components.append({"name":d["name"],"type":"drive_bay","status":d.get("status",""),"model":"","serial":"","index":None,"slot":None,"speed":None,"temperature":None,"voltage":None,"identify":""})
    hw_by_type = {}
    for hc in hw_components:
        t = hc["type"] or "other"
        hw_by_type.setdefault(t, []).append(hc)
    hw_summary = {t: {"total": len(items), "healthy": sum(1 for i in items if i["status"] in ("ok","healthy","normal","not_installed"))} for t, items in hw_by_type.items()}

    # Alerts (v1: message?flagged=true)
    alert_raw = alerts if isinstance(alerts, list) else []
    open_alerts = [a for a in alert_raw if a.get("current_severity", "") in ("warning", "error", "critical")]
    alert_list = []
    for a in open_alerts:
        alert_list.append({
            "severity": a.get("current_severity", ""),
            "category": a.get("category", ""),
            "component": a.get("component_type", "") or a.get("component_name", ""),
            "description": a.get("event", "") + ((" - " + a.get("details", "")) if a.get("details") else ""),
            "state": "open" if a.get("current_severity") else "closed",
            "created": a.get("opened", ""),
        })

    snap_list = snaps if isinstance(snaps, list) else []

    return {
        "system": {
            "name":    ai.get("array_name", ""),
            "model":   "FlashArray " + (ctrl_list[0]["model"] if ctrl_list else ""),
            "serial":  ai.get("id", ""),
            "version": ai.get("version", ""),
            "parity":  "",
        },
        "capacity": {
            "total_bytes": cap_bytes,
            "used_bytes":  total_used,
            "free_bytes":  free_b,
            "total_tb":    round(cap_bytes / 1e12, 2),
            "used_tb":     round(total_used / 1e12, 2),
            "free_tb":     round(free_b / 1e12, 2),
            "used_pct":    round(total_used / cap_bytes * 100, 1) if cap_bytes else 0,
            "data_reduction": round(data_reduction, 2),
            "thin_provisioning_pct": round(thin_prov * 100, 1),
        },
        "volumes":      len(vol_list),
        "hosts":        len(host_list),
        "host_groups":  len(hg_list),
        "drives":       len(drive_list),
        "ports":        len(port_list),
        "connections":  len(conn_list),
        "pgroups":      len(pg_list),
        "snapshots":    len(snap_list),
        "controllers":  len(ctrl_list),
        "alerts":       len(open_alerts),
        "total_alerts": len(alert_raw),
        "volume_list":      vol_list,
        "host_list":        host_list,
        "host_group_list":  hg_list,
        "drive_list":       drive_list,
        "port_list":        port_list,
        "connection_list":  conn_list,
        "pgroup_list":      pg_list,
        "controller_list":  ctrl_list,
        "alert_list":       alert_list,
        "hardware":         hw_components,
        "hw_by_type":       hw_by_type,
        "hw_summary":       hw_summary,
    }



# ── Dell PowerFlex ──────────────────────────────────────────────────
def _pflex_session(arr: dict) -> tuple:
    """Authenticate to PowerFlex Manager, return (session, base_url, system_id)."""
    base = _base(arr)
    s = requests.Session()
    s.verify = False
    s.timeout = 20
    s.headers.update({"Content-Type": "application/json"})

    # Login via /rest/auth/login (returns JWT)
    lr = s.post(f"{base}/rest/auth/login",
                json={"username": arr["username"], "password": arr["password"]},
                timeout=15)
    if lr.status_code != 200:
        raise ConnectionError(f"PowerFlex login failed HTTP {lr.status_code}: {lr.text[:200]}")
    token_data = lr.json()
    access_token = token_data.get("access_token", "")
    if not access_token:
        raise ConnectionError("PowerFlex login returned no access_token")
    s.headers.update({"Authorization": f"Bearer {access_token}"})

    # Get system ID
    sr = s.get(f"{base}/api/types/System/instances", timeout=15)
    systems = sr.json() if sr.status_code == 200 else []
    sys_id = systems[0].get("id", "") if systems else ""

    return s, base, sys_id


def _pflex_test(arr: dict) -> dict:
    s, base, sys_id = _pflex_session(arr)
    systems = s.get(f"{base}/api/types/System/instances", timeout=15).json()
    sys0 = systems[0] if systems else {}
    ver = sys0.get("systemVersionName", "")
    mdm = sys0.get("mdmCluster", {}) or {}
    return {
        "ok": True,
        "message": f"Connected \u2014 {ver}, MDM: {mdm.get('clusterMode','')}, System ID: {sys_id}",
        "system_info": {
            "name":    mdm.get("name", "") or ver,
            "model":   "Dell PowerFlex",
            "serial":  sys_id,
            "version": ver,
        }
    }


def _pflex_data(arr: dict) -> dict:
    s, base, sys_id = _pflex_session(arr)
    T = 15

    def _g(rtype):
        try:
            r = s.get(f"{base}/api/types/{rtype}/instances", timeout=T)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return []

    # System info
    systems = _g("System")
    sys0 = systems[0] if systems else {}
    mdm = sys0.get("mdmCluster", {}) or {}
    ver = sys0.get("systemVersionName", "")
    perf = sys0.get("perfProfile", "")

    # System statistics (capacity + counts)
    stats = {}
    if sys_id:
        try:
            r = s.get(f"{base}/api/instances/System::{sys_id}/relationships/Statistics", timeout=T)
            if r.status_code == 200:
                stats = r.json()
        except Exception:
            pass

    max_kb = stats.get("maxCapacityInKb", 0) or 0
    used_kb = stats.get("capacityInUseInKb", 0) or 0
    avail_kb = stats.get("capacityAvailableForVolumeAllocationInKb", 0) or 0
    total_bytes = max_kb * 1024
    used_bytes = used_kb * 1024
    free_bytes = total_bytes - used_bytes if total_bytes > used_bytes else 0

    # Protection Domains
    pd_raw = _g("ProtectionDomain")
    pd_list = []
    for pd in pd_raw:
        pd_list.append({
            "name": pd.get("name", ""),
            "id": pd.get("id", ""),
            "state": pd.get("protectionDomainState", ""),
            "rfcache_enabled": pd.get("rfcacheEnabled", False),
        })

    # Storage Pools
    sp_raw = _g("StoragePool")
    sp_list = []
    for sp in sp_raw:
        sp_list.append({
            "name": sp.get("name", ""),
            "id": sp.get("id", ""),
            "protection_domain_id": sp.get("protectionDomainId", ""),
            "media_type": sp.get("mediaType", ""),
            "compression": sp.get("compressionMethod", "None"),
            "data_layout": sp.get("dataLayout", ""),
        })

    # Volumes
    vol_raw = _g("Volume")
    vol_list = []
    for v in vol_raw:
        size_kb = v.get("sizeInKb", 0) or 0
        mapped = v.get("mappedSdcInfo", []) or []
        vol_list.append({
            "name": v.get("name", "") or v.get("id", ""),
            "id": v.get("id", ""),
            "size_bytes": size_kb * 1024,
            "size_gb": round(size_kb / (1024 * 1024), 1),
            "storage_pool_id": v.get("storagePoolId", ""),
            "volume_type": v.get("volumeType", ""),
            "creation_time": v.get("creationTime", 0),
            "mapped_sdc_count": len(mapped),
            "vtree_id": v.get("vtreeId", ""),
        })

    # SDS (Storage Data Servers)
    sds_raw = _g("Sds")
    sds_list = []
    for sd in sds_raw:
        ips = sd.get("ipList", []) or []
        ip_strs = [ip.get("ip", "") for ip in ips if ip.get("ip")]
        sds_list.append({
            "name": sd.get("name", ""),
            "id": sd.get("id", ""),
            "ip_addresses": ip_strs,
            "protection_domain_id": sd.get("protectionDomainId", ""),
            "state": sd.get("mdmConnectionState", ""),
            "membership": sd.get("membershipState", ""),
            "port": sd.get("port", 7072),
            "on_vmware": sd.get("onVmWare", False),
        })

    # SDC (Storage Data Clients)
    sdc_raw = _g("Sdc")
    sdc_list = []
    for sc in sdc_raw:
        sdc_list.append({
            "name": sc.get("name", "") or sc.get("sdcIp", "") or sc.get("id", ""),
            "id": sc.get("id", ""),
            "ip": sc.get("sdcIp", "") or "N/A",
            "os_type": sc.get("osType", ""),
            "state": "Active" if sc.get("sdcAgentActive") else "Inactive",
            "approved": sc.get("sdcApproved", False),
            "host_os": sc.get("hostOsFullType", ""),
        })

    # Devices (physical drives)
    dev_raw = _g("Device")
    dev_list = []
    for d in dev_raw:
        cap_kb = d.get("capacity", {}).get("maxCapacityInKb", 0) if isinstance(d.get("capacity"), dict) else 0
        dev_list.append({
            "name": d.get("name", "") or d.get("deviceCurrentPathName", ""),
            "id": d.get("id", ""),
            "path": d.get("deviceCurrentPathName", ""),
            "media_type": d.get("mediaType", ""),
            "storage_pool_id": d.get("storagePoolId", ""),
            "sds_id": d.get("sdsId", ""),
            "state": d.get("deviceState", ""),
            "capacity_bytes": cap_kb * 1024,
        })

    # Fault Sets
    fs_raw = _g("FaultSet")
    fs_list = []
    for fs in fs_raw:
        fs_list.append({
            "name": fs.get("name", ""),
            "id": fs.get("id", ""),
            "protection_domain_id": fs.get("protectionDomainId", ""),
        })

    # VTrees
    vt_raw = _g("VTree")
    vt_list = []
    for vt in vt_raw:
        vt_list.append({
            "name": vt.get("name", "") or vt.get("id", ""),
            "id": vt.get("id", ""),
            "storage_pool_id": vt.get("storagePoolId", ""),
            "data_layout": vt.get("dataLayout", ""),
            "compression": vt.get("compressionMethod", "None"),
            "in_deletion": vt.get("inDeletion", False),
        })

    # Alerts
    alert_raw = _g("Alert")
    alert_list = []
    for a in alert_raw:
        alert_list.append({
            "severity": a.get("severity", ""),
            "type": a.get("alertType", ""),
            "description": a.get("alertDescription", "") or a.get("name", ""),
            "state": a.get("state", ""),
            "start_time": a.get("startTime", 0),
        })

    # Build name-lookup maps for IDs
    pd_names = {p["id"]: p["name"] for p in pd_list}
    sp_names = {p["id"]: p["name"] for p in sp_list}
    sds_names = {p["id"]: p["name"] for p in sds_list}

    # Enrich with resolved names
    for v in vol_list:
        v["storage_pool"] = sp_names.get(v.get("storage_pool_id", ""), "")
    for d in dev_list:
        d["storage_pool"] = sp_names.get(d.get("storage_pool_id", ""), "")
        d["sds_name"] = sds_names.get(d.get("sds_id", ""), "")
    for sd in sds_list:
        sd["protection_domain"] = pd_names.get(sd.get("protection_domain_id", ""), "")
    for sp in sp_list:
        sp["protection_domain"] = pd_names.get(sp.get("protection_domain_id", ""), "")

    return {
        "system": {
            "name":    mdm.get("name", "") or ver,
            "model":   "Dell PowerFlex",
            "serial":  sys_id,
            "version": ver,
            "perf_profile": perf,
            "mdm_mode": mdm.get("clusterMode", ""),
        },
        "capacity": {
            "total_bytes": total_bytes,
            "used_bytes":  used_bytes,
            "free_bytes":  free_bytes,
            "total_tb":    round(total_bytes / 1e12, 2),
            "used_tb":     round(used_bytes / 1e12, 2),
            "free_tb":     round(free_bytes / 1e12, 2),
            "used_pct":    round(used_bytes / total_bytes * 100, 1) if total_bytes else 0,
            "allocatable_tb": round(avail_kb * 1024 / 1e12, 2),
        },
        "volumes":              stats.get("numOfVolumes", len(vol_list)),
        "sds_count":            stats.get("numOfSds", len(sds_list)),
        "sdc_count":            stats.get("numOfSdc", len(sdc_list)),
        "devices":              stats.get("numOfDevices", len(dev_list)),
        "protection_domains":   stats.get("numOfProtectionDomains", len(pd_list)),
        "storage_pools":        stats.get("numOfStoragePools", len(sp_list)),
        "fault_sets":           stats.get("numOfFaultSets", len(fs_list)),
        "vtrees":               stats.get("numOfVtrees", len(vt_list)),
        "snapshots":            stats.get("numOfSnapshots", 0),
        "alerts":               len(alert_list),
        "volume_list":          vol_list,
        "sds_list":             sds_list,
        "sdc_list":             sdc_list,
        "device_list":          dev_list,
        "pd_list":              pd_list,
        "sp_list":              sp_list,
        "fault_set_list":       fs_list,
        "vtree_list":           vt_list,
        "alert_list":           alert_list,
    }



# -- Dell PowerScale (Isilon) ----------------------------------------
def _pscale_session(arr: dict) -> tuple:
    """Authenticate to PowerScale, return (session, base_url)."""
    base = _base(arr)
    s = requests.Session()
    s.verify = False
    s.timeout = 30
    s.headers.update({"Content-Type": "application/json"})

    lr = s.post(f"{base}/session/1/session",
                json={"username": arr["username"], "password": arr["password"],
                      "services": ["platform", "namespace"]},
                timeout=15)
    if lr.status_code not in (200, 201):
        raise ConnectionError(f"PowerScale login failed HTTP {lr.status_code}: {lr.text[:200]}")
    csrf = s.cookies.get("isicsrf", "")
    s.headers.update({"X-CSRF-Token": csrf, "Referer": f"{base}/"})
    return s, base


def _pscale_test(arr: dict) -> dict:
    s, base = _pscale_session(arr)
    r = s.get(f"{base}/platform/1/cluster/config", timeout=15)
    r.raise_for_status()
    cfg = r.json()
    ov = cfg.get("onefs_version", {}) or {}
    ver = ov.get("version", "") if isinstance(ov, dict) else str(ov)
    return {
        "ok": True,
        "message": f"Connected \u2014 Dell PowerScale {cfg.get('name','')} {ov.get('type','')} {ov.get('release','')}",
        "system_info": {
            "name":    cfg.get("name", ""),
            "model":   "Dell PowerScale",
            "serial":  cfg.get("local_serial", ""),
            "version": ver,
        }
    }


def _pscale_data(arr: dict) -> dict:
    s, base = _pscale_session(arr)
    T = 30

    def _g(path):
        try:
            r = s.get(f"{base}{path}", timeout=T)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    # Cluster config
    cfg = _g("/platform/1/cluster/config")
    ov = cfg.get("onefs_version", {}) or {}
    devices = cfg.get("devices", [])

    # Cluster identity
    ident = _g("/platform/1/cluster/identity")

    # Capacity (statfs)
    st = _g("/platform/1/cluster/statfs")
    bsize = st.get("f_bsize", 8192)
    total_b = st.get("f_blocks", 0) * bsize
    free_b  = st.get("f_bfree", 0) * bsize
    avail_b = st.get("f_bavail", 0) * bsize
    used_b  = total_b - free_b

    # NFS Exports
    nfs_data = _g("/platform/1/protocols/nfs/exports")
    nfs_list = nfs_data.get("exports", [])
    nfs_exports = []
    for e in nfs_list:
        paths = e.get("paths", []) or []
        clients_list = e.get("clients", []) or []
        nfs_exports.append({
            "id": e.get("id", ""),
            "description": e.get("description", ""),
            "paths": paths,
            "path": paths[0] if paths else "",
            "clients": clients_list,
            "read_only": e.get("read_only", False),
            "all_dirs": e.get("all_dirs", False),
            "block_size": e.get("block_size", 0),
        })

    # SMB Shares
    smb_data = _g("/platform/1/protocols/smb/shares")
    smb_list = smb_data.get("shares", [])
    smb_shares = []
    for sh in smb_list:
        smb_shares.append({
            "name": sh.get("name", ""),
            "path": sh.get("path", ""),
            "description": sh.get("description", ""),
            "browsable": sh.get("browsable", False),
            "continuously_available": sh.get("continuously_available", False),
            "access_based_enumeration": sh.get("access_based_enumeration", False),
        })

    # Storage Pools
    sp_data = _g("/platform/1/storagepool/storagepools")
    sp_list = sp_data.get("storagepools", [])
    storage_pools = []
    for sp in sp_list:
        usage = sp.get("usage", {}) or {}
        storage_pools.append({
            "name": sp.get("name", ""),
            "id": sp.get("id", ""),
            "type": sp.get("type", ""),
            "lnns": sp.get("lnns", []),
            "node_count": len(sp.get("lnns", [])),
            "protection_policy": sp.get("protection_policy", ""),
            "usage_avail": usage.get("avail_bytes", 0),
            "usage_total": usage.get("total_bytes", 0),
        })

    # Quotas
    quota_data = _g("/platform/1/quota/quotas")
    quota_list = quota_data.get("quotas", [])
    quotas = []
    for q in quota_list:
        thresh = q.get("thresholds", {}) or {}
        usage_q = q.get("usage", {}) or {}
        quotas.append({
            "path": q.get("path", ""),
            "type": q.get("type", ""),
            "enforced": q.get("enforced", False),
            "hard_limit": thresh.get("hard", 0) or 0,
            "soft_limit": thresh.get("soft", 0) or 0,
            "usage_logical": usage_q.get("logical", 0) or 0,
            "usage_physical": usage_q.get("physical", 0) or 0,
            "ready": q.get("ready", False),
            "linked": q.get("linked", False),
        })

    # Snapshots
    snap_data = _g("/platform/1/snapshot/snapshots")
    snap_list = snap_data.get("snapshots", [])
    snapshots = []
    for sn in snap_list:
        snapshots.append({
            "name": sn.get("name", ""),
            "id": sn.get("id", ""),
            "path": sn.get("path", ""),
            "created": sn.get("created", 0),
            "size": sn.get("size", 0),
            "pct_filesystem": sn.get("pct_filesystem", 0),
            "schedule": sn.get("schedule", ""),
            "has_locks": sn.get("has_locks", False),
        })

    # Node list from config devices
    node_list = []
    for d in devices:
        node_list.append({
            "lnn": d.get("lnn", ""),
            "devid": d.get("devid", ""),
            "guid": d.get("guid", ""),
        })

    ver_str = ov.get("version", "") if isinstance(ov, dict) else str(ov)
    release = ov.get("release", "") if isinstance(ov, dict) else ""
    os_type = ov.get("type", "OneFS") if isinstance(ov, dict) else "OneFS"

    return {
        "system": {
            "name":    cfg.get("name", ""),
            "model":   "Dell PowerScale",
            "serial":  cfg.get("local_serial", ""),
            "version": f"{os_type} {release}",
            "encoding": cfg.get("encoding", ""),
            "join_mode": cfg.get("join_mode", ""),
            "guid": cfg.get("guid", ""),
        },
        "capacity": {
            "total_bytes": total_b,
            "used_bytes":  used_b,
            "free_bytes":  free_b,
            "total_tb":    round(total_b / 1e12, 2),
            "used_tb":     round(used_b / 1e12, 2),
            "free_tb":     round(free_b / 1e12, 2),
            "used_pct":    round(used_b / total_b * 100, 1) if total_b else 0,
            "avail_tb":    round(avail_b / 1e12, 2),
        },
        "nodes":          len(node_list),
        "nfs_exports":    len(nfs_exports),
        "smb_shares":     len(smb_shares),
        "storage_pools":  len(storage_pools),
        "quotas":         len(quotas),
        "snapshots":      len(snapshots),
        "node_list":      node_list,
        "nfs_export_list": nfs_exports,
        "smb_share_list":  smb_shares,
        "storage_pool_list": storage_pools,
        "quota_list":      quotas,
        "snapshot_list":   snapshots,
    }


# ── HPE Nimble Storage REST API ───────────────────────────────────────────────
# Auth: POST /v1/tokens → session_token, Header: X-Auth-Token
# Nimble REST API always on port 5392, no detail=true support.
# To get full object data, fetch individual items by ID.

def _nimble_session(arr: dict) -> tuple:
    """Authenticate to HPE Nimble and return (base_url, headers_dict)."""
    ip = arr["ip"].strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    port = (arr.get("port") or "5392").strip() or "5392"
    base = f"https://{ip}:{port}"
    cred = {"data": {"username": arr["username"], "password": arr["password"]}}
    r = requests.post(f"{base}/v1/tokens", json=cred, verify=False, timeout=12)
    if r.status_code in (200, 201):
        tok = r.json().get("data", {}).get("session_token", "")
        if tok:
            return base, {"X-Auth-Token": tok}
    raise ConnectionError(f"Cannot authenticate to HPE Nimble at {arr['ip']}")


def _nimble_test(arr: dict) -> dict:
    base, hdr = _nimble_session(arr)
    # Get array info (list then detail by id)
    r = requests.get(f"{base}/v1/arrays", headers=hdr, verify=False, timeout=15)
    r.raise_for_status()
    arrs = r.json().get("data", [])
    if not arrs:
        return {"ok": False, "message": "Connected but no arrays found"}
    aid = arrs[0]["id"]
    r2 = requests.get(f"{base}/v1/arrays/{aid}", headers=hdr, verify=False, timeout=15)
    d = r2.json().get("data", {})
    return {
        "ok": True,
        "message": f"Connected — HPE Nimble {d.get('model','')} v{d.get('version','')}",
        "system_info": {
            "name":    d.get("name", ""),
            "model":   d.get("model", ""),
            "serial":  d.get("serial", ""),
            "version": d.get("version", ""),
        },
    }


def _nimble_data(arr: dict) -> dict:
    import concurrent.futures as _cfn
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    ip   = arr["ip"].strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    port = (arr.get("port") or "5392").strip() or "5392"
    base = f"https://{ip}:{port}"
    T    = 12  # per-request timeout

    # Use a single session with persistent TLS connection (avoid re-handshake per call)
    sess = requests.Session()
    sess.verify = False
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=1,
        pool_maxsize=40,
        max_retries=0,
    )
    sess.mount("https://", adapter)

    # Authenticate
    cred = {"data": {"username": arr["username"], "password": arr["password"]}}
    r = sess.post(f"{base}/v1/tokens", json=cred, timeout=T)
    if r.status_code not in (200, 201):
        raise ConnectionError(f"Cannot authenticate to HPE Nimble at {arr['ip']}")
    tok = r.json().get("data", {}).get("session_token", "")
    if not tok:
        raise ConnectionError(f"No session token from HPE Nimble at {arr['ip']}")
    sess.headers.update({"X-Auth-Token": tok})

    def _lst(ep):
        try:
            rv = sess.get(f"{base}/v1/{ep}", timeout=T)
            if rv.status_code == 200:
                return rv.json().get("data", [])
        except Exception:
            pass
        return []

    def _detail(ep, item_id):
        try:
            rv = sess.get(f"{base}/v1/{ep}/{item_id}", timeout=T)
            if rv.status_code == 200:
                return rv.json().get("data", {})
        except Exception:
            pass
        return {}

    # -- Phase 1: all list endpoints in parallel (shared session) --
    endpoints = ["arrays", "groups", "pools", "volumes", "disks",
                 "shelves", "initiator_groups", "fibre_channel_interfaces",
                 "network_configs", "performance_policies"]
    with _cfn.ThreadPoolExecutor(max_workers=len(endpoints)) as ex:
        futs_map = {ep: ex.submit(_lst, ep) for ep in endpoints}
        lists = {}
        for ep, fut in futs_map.items():
            try:
                lists[ep] = fut.result(timeout=25)
            except Exception:
                lists[ep] = []

    arr_items   = lists.get("arrays", [])
    grp_items   = lists.get("groups", [])
    pool_items  = lists.get("pools", [])
    vol_items   = lists.get("volumes", [])
    disk_items  = lists.get("disks", [])
    shelf_items = lists.get("shelves", [])
    ig_items    = lists.get("initiator_groups", [])
    fc_items    = lists.get("fibre_channel_interfaces", [])
    net_items   = lists.get("network_configs", [])
    pp_items    = lists.get("performance_policies", [])

    # -- Phase 2: ALL detail calls in one flat pool (shared session) --
    all_tasks = []
    for ep, items in [
        ("arrays",                   arr_items[:1]),
        ("groups",                   grp_items[:1]),
        ("pools",                    pool_items),
        ("volumes",                  vol_items),
        ("disks",                    disk_items),
        ("shelves",                  shelf_items),
        ("initiator_groups",         ig_items),
        ("fibre_channel_interfaces", fc_items),
        ("network_configs",          net_items),
        ("performance_policies",     pp_items),
    ]:
        for item in items:
            all_tasks.append((ep, item["id"]))

    detail_cache: dict = {}
    if all_tasks:
        max_w = min(40, len(all_tasks))
        with _cfn.ThreadPoolExecutor(max_workers=max_w) as ex:
            futs = {ex.submit(_detail, ep, iid): (ep, iid) for ep, iid in all_tasks}
            for fut in _cfn.as_completed(futs, timeout=30):
                ep, iid = futs[fut]
                try:
                    detail_cache[(ep, iid)] = fut.result()
                except Exception:
                    detail_cache[(ep, iid)] = {}

    sess.close()

    def _dr(ep, item):
        return detail_cache.get((ep, item["id"]), {})

    arr_d = _dr("arrays", arr_items[0]) if arr_items else {}
    grp_d = _dr("groups", grp_items[0]) if grp_items else {}

    # -- Capacity from group --
    total_b        = grp_d.get("usable_capacity_bytes", 0) or 0
    used_b         = grp_d.get("usage", 0) or (total_b - (grp_d.get("free_space", 0) or 0))
    free_b         = grp_d.get("free_space", 0) or (total_b - used_b)
    comp_ratio     = grp_d.get("compression_ratio", 0) or 0
    dedupe_ratio   = grp_d.get("dedupe_ratio", 0) or 0
    savings_comp   = grp_d.get("savings_compression", 0) or 0
    savings_dedupe = grp_d.get("savings_dedupe", 0) or 0

    # -- Pools --
    pool_list = []
    for p in pool_items:
        pd = _dr("pools", p)
        pool_list.append({
            "name":           pd.get("name", p.get("name", "")),
            "id":             pd.get("id", p.get("id", "")),
            "capacity_bytes": pd.get("capacity", 0) or 0,
            "usage_bytes":    pd.get("usage", 0) or 0,
            "free_bytes":     (pd.get("capacity", 0) or 0) - (pd.get("usage", 0) or 0),
            "used_pct":       round((pd.get("usage", 0) or 0) / (pd.get("capacity", 0) or 1) * 100, 1),
            "vol_count":      pd.get("vol_count", 0) or 0,
            "snap_count":     pd.get("snap_count", 0) or 0,
            "dedupe_capable": pd.get("dedupe_capable", False),
            "is_default":     pd.get("is_default", False),
        })

    # -- Volumes --
    vol_list = []
    for v in vol_items:
        vd = _dr("volumes", v)
        sz   = (vd.get("size", 0) or 0) * 1024 * 1024  # MB -> bytes
        used = vd.get("total_usage_bytes", 0) or 0
        vol_list.append({
            "name":            vd.get("name", v.get("name", "")),
            "id":              vd.get("id", v.get("id", "")),
            "size_bytes":      sz,
            "used_bytes":      used,
            "used_pct":        round(used / sz * 100, 1) if sz else 0,
            "online":          vd.get("online", False),
            "thin":            vd.get("thinly_provisioned", False),
            "clone":           vd.get("clone", False),
            "pool":            vd.get("pool_name", ""),
            "perfpolicy":      vd.get("perfpolicy_name", ""),
            "serial":          vd.get("serial_number", ""),
            "num_snaps":       vd.get("num_snaps", 0) or 0,
            "num_connections": vd.get("num_connections", 0) or 0,
            "dedup":           vd.get("dedup_enabled", False),
            "agent_type":      vd.get("agent_type", "none"),
            "target_name":     vd.get("target_name", ""),
        })

    # -- Disks --
    disk_list = []
    for dk in disk_items:
        dd = _dr("disks", dk)
        disk_list.append({
            "serial":         dd.get("serial", dk.get("serial", "")),
            "slot":           dd.get("slot", 0),
            "size_bytes":     dd.get("size", 0) or 0,
            "type":           dd.get("type", "unknown"),
            "state":          dd.get("state", "unknown"),
            "model":          dd.get("model", ""),
            "vendor":         dd.get("vendor", ""),
            "firmware":       dd.get("firmware_version", ""),
            "path":           dd.get("path", ""),
            "shelf_serial":   dd.get("shelf_serial", ""),
            "shelf_location": dd.get("shelf_location", ""),
            "bank":           dd.get("bank", 0),
            "is_flash":       dd.get("type", "") == "ssd",
        })

    # -- Shelves --
    shelf_list = []
    for sh in shelf_items:
        sd = _dr("shelves", sh)
        shelf_list.append({
            "serial":       sd.get("serial", sh.get("serial", "")),
            "model":        sd.get("model", ""),
            "model_ext":    sd.get("model_ext", ""),
            "array_name":   sd.get("array_name", ""),
            "fan_status":   sd.get("fan_overall_status", "unknown"),
            "psu_status":   sd.get("psu_overall_status", "unknown"),
            "temp_status":  sd.get("temp_overall_status", "unknown"),
            "chassis_type": sd.get("chassis_type", ""),
        })

    # -- Initiator Groups --
    ig_list = []
    for ig in ig_items:
        igd = _dr("initiator_groups", ig)
        ig_list.append({
            "name":            igd.get("name", ig.get("name", "")),
            "id":              igd.get("id", ig.get("id", "")),
            "protocol":        igd.get("access_protocol", "iscsi"),
            "host_type":       igd.get("host_type", ""),
            "num_connections": igd.get("num_connections", 0) or 0,
            "description":     igd.get("description", ""),
            "fc_initiators":    [i.get("wwpn", "") for i in (igd.get("fc_initiators")    or [])],
            "iscsi_initiators": [i.get("iqn",  "") for i in (igd.get("iscsi_initiators") or [])],
        })

    # -- FC Interfaces --
    fc_list = []
    for fc in fc_items:
        fcd = _dr("fibre_channel_interfaces", fc)
        fc_list.append({
            "id":           fcd.get("id", fc.get("id", "")),
            "name":         fcd.get("name", ""),
            "wwnn":         fcd.get("wwnn", ""),
            "wwpn":         fcd.get("wwpn", ""),
            "online":       fcd.get("online", False),
            "link_speed":   fcd.get("link_speed", ""),
            "port":         fcd.get("fc_port_name", ""),
            "slot":         fcd.get("slot", 0),
            "bus_location": fcd.get("bus_location", ""),
        })

    # -- Network Configs --
    net_list = []
    for nc in net_items:
        ncd = _dr("network_configs", nc)
        net_list.append({
            "name":    ncd.get("name", nc.get("name", "")),
            "id":      ncd.get("id", nc.get("id", "")),
            "role":    ncd.get("role", ""),
            "mgmt_ip": ncd.get("mgmt_ip", ""),
            "iscsi_automatic_connection_method": ncd.get("iscsi_automatic_connection_method", False),
        })

    # -- Performance Policies --
    pp_list = []
    for pp in pp_items:
        ppd = _dr("performance_policies", pp)
        pp_list.append({
            "name":       ppd.get("name", pp.get("name", "")),
            "id":         ppd.get("id", pp.get("id", "")),
            "block_size": ppd.get("block_size", 0),
            "compress":   ppd.get("compress", False),
            "dedupe":     ppd.get("dedupe_enabled", False),
            "cache":      ppd.get("cache", False),
        })

    return {
        "system": {
            "name":              arr_d.get("name", ""),
            "model":             arr_d.get("model", ""),
            "serial":            arr_d.get("serial", ""),
            "version":           arr_d.get("version", ""),
            "full_name":         arr_d.get("full_name", ""),
            "status":            arr_d.get("status", ""),
            "all_flash":         arr_d.get("all_flash", False),
            "raw_capacity_bytes": arr_d.get("raw_capacity_bytes", 0) or 0,
        },
        "capacity": {
            "total_bytes":               total_b,
            "used_bytes":                used_b,
            "free_bytes":                free_b,
            "total_tb":                  round(total_b / 1e12, 2),
            "used_tb":                   round(used_b  / 1e12, 2),
            "free_tb":                   round(free_b  / 1e12, 2),
            "used_pct":                  round(used_b / total_b * 100, 1) if total_b else 0,
            "compression_ratio":         comp_ratio,
            "dedupe_ratio":              dedupe_ratio,
            "savings_compression_bytes": savings_comp,
            "savings_dedupe_bytes":      savings_dedupe,
        },
        "volumes":          len(vol_list),
        "disks":            len(disk_list),
        "shelves":          len(shelf_list),
        "pools":            len(pool_list),
        "initiator_groups": len(ig_list),
        "fc_interfaces":    len(fc_list),
        "perf_policies":    len(pp_list),
        "volume_list":      vol_list,
        "disk_list":        disk_list,
        "shelf_list":       shelf_list,
        "pool_list":        pool_list,
        "initiator_group_list": ig_list,
        "fc_interface_list":    fc_list,
        "network_list":     net_list,
        "perf_policy_list": pp_list,
    }


_VENDOR_TEST = {
    "NetApp":       _netapp_test,
    "Dell-EMC":     _dell_test,
    "Dell PowerFlex": _pflex_test,
    "Dell PowerScale": _pscale_test,
    "HPE":          _hpe_test,
    "Pure Storage": _pure_test,
    "Pure FlashArray": _fa_test,
    "IBM":          _ibm_test,
    "Hitachi":      _hitachi_test,
    "HPE Nimble":   _nimble_test,
}
_VENDOR_DATA = {
    "NetApp":       _netapp_data,
    "Dell-EMC":     _dell_data,
    "Dell PowerFlex": _pflex_data,
    "Dell PowerScale": _pscale_data,
    "HPE":          _hpe_data,
    "Pure Storage": _pure_data,
    "Pure FlashArray": _fa_data,
    "IBM":          _ibm_data,
    "Hitachi":      _hitachi_data,
    "HPE Nimble":   _nimble_data,
}

def test_connection(arr: dict) -> dict:
    """arr must contain: vendor, ip, port, username, password"""
    vendor = arr.get("vendor", "")
    fn = _VENDOR_TEST.get(vendor)
    if not fn:
        return {"ok": False, "message": f"Unsupported vendor: {vendor}"}
    try:
        return fn(arr)
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "message": f"Cannot reach {arr.get('ip','')}: {e}"}
    except requests.exceptions.Timeout:
        return {"ok": False, "message": f"Connection timed out to {arr.get('ip','')}"}
    except requests.exceptions.HTTPError as e:
        return {"ok": False, "message": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

def get_array_data(arr: dict) -> dict:
    """arr must contain: vendor, ip, port, username, password"""
    vendor = arr.get("vendor", "")
    fn = _VENDOR_DATA.get(vendor)
    if not fn:
        raise ValueError(f"Unsupported vendor: {vendor}")
    return fn(arr)


def get_volume_topology(arr: dict, volume_name: str, cached_data: dict = None) -> dict:
    """
    Build a complete topology map for a single volume showing:
    - Volume details (serial, size, WWN, etc.)
    - Connected hosts with IQN / WWN / NQN identifiers
    - LUN IDs, port mappings, protocol info
    - SnapMirror / replication relationships (NetApp)
    - Cross-vendor normalised result so the frontend can render uniformly.
    Returns: {
        "vendor": str,
        "volume": { name, serial, wwn, size_bytes, used_bytes, protocol, ... },
        "connections": [
            {
                "host": str,
                "host_group": str|None,
                "lun_id": int|None,
                "port": str|None,
                "protocol": str,          # "iSCSI"|"FC"|"NVMe-oF"|"NFS"|"SMB"|"NVMe/TCP"|"SAS"|"unknown"
                "iqns": [str],
                "wwns": [str],
                "nqns": [str],
                "os_type": str|None,
                "active": bool,
                "volume_wwn": str|None,
            }
        ],
        "replication": [
            { "direction": "outbound"|"inbound", "remote_volume": str,
              "remote_svm": str, "state": str, "healthy": bool|None, "lag_time": str }
        ],
        "storage_ports": [
            { "name": str, "wwn": str|None, "ip": str|None, "protocol": str, "link_state": str }
        ],
        "error": str|None
    }
    """
    vendor  = arr.get("vendor", "")
    result  = {
        "vendor": vendor,
        "volume": {},
        "connections": [],
        "replication": [],
        "storage_ports": [],
        "error": None,
    }
    try:
        data = cached_data if cached_data is not None else get_array_data(arr)
    except Exception as e:
        result["error"] = str(e)
        return result

    # ── Pure FlashArray ──────────────────────────────────────────────
    if vendor == "Pure FlashArray":
        vol_list   = data.get("volume_list", [])
        conn_list  = data.get("connection_list", [])
        host_list  = data.get("host_list", [])
        port_list  = data.get("port_list", [])

        vol = next((v for v in vol_list if v["name"] == volume_name), None)
        if vol:
            result["volume"] = {
                "name":        vol.get("name"),
                "serial":      vol.get("serial", ""),
                "size_bytes":  vol.get("provisioned_bytes", 0),
                "used_bytes":  vol.get("used_bytes", 0),
                "pod":         vol.get("pod", ""),
                "protocol":    "iSCSI/FC",
                "wwn":         "",
            }

        for conn in conn_list:
            if conn.get("volume") != volume_name:
                continue
            host_name = conn.get("host", "")
            host_rec  = next((h for h in host_list if h.get("name") == host_name), {})
            result["connections"].append({
                "host":        host_name,
                "host_group":  conn.get("host_group") or host_rec.get("host_group"),
                "lun_id":      conn.get("lun"),
                "port":        None,
                "protocol":    host_rec.get("protocol", "iSCSI/FC"),
                "iqns":        host_rec.get("iqns", []),
                "wwns":        host_rec.get("wwns", []),
                "nqns":        host_rec.get("nqns", []),
                "os_type":     None,
                "active":      True,
                "volume_wwn":  None,
            })

        for pt in port_list:
            result["storage_ports"].append({
                "name":       pt.get("name", ""),
                "wwn":        pt.get("wwwn") or pt.get("wwn"),
                "ip":         pt.get("iqn"),
                "protocol":   "FC" if (pt.get("wwwn") or pt.get("wwn")) else "iSCSI",
                "link_state": pt.get("status", ""),
            })

    # ── NetApp ONTAP ─────────────────────────────────────────────────
    elif vendor == "NetApp":
        vol_list    = data.get("volume_list", [])
        lun_list    = data.get("lun_list", [])
        igroup_list = data.get("igroup_list", [])
        sm_list     = data.get("snapmirror_list", [])
        nic_list    = data.get("nic_list", [])

        vol = next((v for v in vol_list if v["name"] == volume_name), None)
        if vol:
            result["volume"] = {
                "name":         vol.get("name"),
                "serial":       "",
                "size_bytes":   vol.get("total_bytes", 0),
                "used_bytes":   vol.get("used_bytes", 0),
                "svm":          vol.get("svm", ""),
                "junction_path": vol.get("junction_path", ""),
                "type":         vol.get("type", ""),
                "state":        vol.get("state", ""),
                "protocol":     "iSCSI/NFS/FC",
                "wwn":          "",
            }

        for lun in lun_list:
            if lun.get("volume") != volume_name:
                continue
            # find igroup that maps this LUN path
            lun_path = lun.get("path", "")
            ig_name  = ""
            iqns     = []
            wwns     = []
            for ig in igroup_list:
                # igroups don't directly reference LUN paths in the cached data,
                # but we include all igroups as potential targets for context
                pass
            # Try to match igroup by LUN name pattern: /vol/<vol>/<ig>/<lun>
            parts = lun_path.strip("/").split("/")
            if len(parts) >= 3:
                ig_name = parts[2] if len(parts) >= 4 else parts[-1]
            ig_rec = next((g for g in igroup_list if g.get("name") == ig_name), {})
            initiators = ig_rec.get("initiators", [])
            proto = (ig_rec.get("protocol") or "iscsi").lower()
            if "fc" in proto:
                wwns = initiators
            else:
                iqns = initiators

            result["connections"].append({
                "host":       ig_name or lun.get("name", ""),
                "host_group": ig_rec.get("name", ""),
                "lun_id":     None,
                "port":       None,
                "protocol":   ig_rec.get("protocol", "iSCSI"),
                "iqns":       iqns,
                "wwns":       wwns,
                "nqns":       [],
                "os_type":    lun.get("os_type") or ig_rec.get("os_type"),
                "active":     lun.get("mapped", False),
                "volume_wwn": None,
                "lun_serial": lun.get("serial", ""),
                "lun_name":   lun.get("name", ""),
                "lun_size":   lun.get("total_bytes", 0),
            })

        for r in sm_list:
            if r.get("source_vol") == volume_name:
                result["replication"].append({
                    "direction":      "outbound",
                    "remote_volume":  r.get("dest_vol", ""),
                    "remote_svm":     r.get("dest_svm", ""),
                    "state":          r.get("state", ""),
                    "healthy":        r.get("healthy"),
                    "lag_time":       r.get("lag_time", ""),
                    "policy":         r.get("policy", ""),
                })
            elif r.get("dest_vol") == volume_name:
                result["replication"].append({
                    "direction":      "inbound",
                    "remote_volume":  r.get("source_vol", ""),
                    "remote_svm":     r.get("source_svm", ""),
                    "state":          r.get("state", ""),
                    "healthy":        r.get("healthy"),
                    "lag_time":       r.get("lag_time", ""),
                    "policy":         r.get("policy", ""),
                })

        for nic in nic_list:
            result["storage_ports"].append({
                "name":       nic.get("name", ""),
                "wwn":        None,
                "ip":         nic.get("ip", ""),
                "protocol":   "NFS/iSCSI",
                "link_state": nic.get("state", ""),
            })

    # ── HPE Alletra (3PAR/Primera) ───────────────────────────────────
    elif vendor == "HPE":
        vol_list  = data.get("vol_list", [])
        vlun_list = data.get("vlun_list", [])
        host_list = data.get("host_list", [])
        port_list = data.get("port_list", [])

        vol = next((v for v in vol_list if v["name"] == volume_name), None)
        if vol:
            result["volume"] = {
                "name":       vol.get("name"),
                "serial":     "",
                "wwn":        vol.get("wwn", ""),
                "size_bytes": vol.get("size_bytes", 0),
                "used_bytes": vol.get("used_bytes", 0),
                "cpg":        vol.get("cpg", ""),
                "state":      vol.get("state", ""),
                "protocol":   "iSCSI/FC",
            }

        for vl in vlun_list:
            if vl.get("volume") != volume_name:
                continue
            host_name = vl.get("host", "")
            host_rec  = next((h for h in host_list if h.get("name") == host_name), {})
            result["connections"].append({
                "host":       host_name,
                "host_group": None,
                "lun_id":     vl.get("lun"),
                "port":       vl.get("port", ""),
                "protocol":   host_rec.get("protocol", "FC"),
                "iqns":       host_rec.get("iscsi_names", []),
                "wwns":       host_rec.get("fc_wwns", []),
                "nqns":       [],
                "os_type":    host_rec.get("persona", ""),
                "active":     vl.get("active", False),
                "volume_wwn": vl.get("volume_wwn", ""),
            })

        for pt in port_list:
            result["storage_ports"].append({
                "name":       pt.get("position", pt.get("label", "")),
                "wwn":        pt.get("wwn", ""),
                "ip":         None,
                "protocol":   pt.get("protocol", "FC"),
                "link_state": pt.get("link_state", ""),
            })

    # ── Dell PowerStore ──────────────────────────────────────────────
    elif vendor == "Dell-EMC":
        vol_list  = data.get("volume_list", [])
        host_list = data.get("host_list", [])
        fc_ports  = data.get("fc_port_list", [])
        eth_ports = data.get("eth_port_list", [])

        vol = next((v for v in vol_list if v["name"] == volume_name), None)
        if vol:
            result["volume"] = {
                "name":       vol.get("name"),
                "serial":     "",
                "wwn":        vol.get("wwn", ""),
                "size_bytes": vol.get("size", 0),
                "used_bytes": vol.get("logical_used", 0),
                "state":      vol.get("state", ""),
                "type":       vol.get("type", ""),
                "protocol":   "iSCSI/FC",
            }

        # PowerStore: host-to-volume mapping requires separate API call not cached,
        # but we include all hosts as potential connections with available info
        for h in host_list:
            result["connections"].append({
                "host":       h.get("name", ""),
                "host_group": h.get("host_group_id", ""),
                "lun_id":     None,
                "port":       None,
                "protocol":   "FC/iSCSI",
                "iqns":       [],
                "wwns":       [],
                "nqns":       [],
                "os_type":    h.get("os_type", ""),
                "active":     True,
                "volume_wwn": vol.get("wwn", "") if vol else None,
            })

        for pt in fc_ports:
            result["storage_ports"].append({
                "name":       pt.get("name", ""),
                "wwn":        pt.get("wwn", ""),
                "ip":         None,
                "protocol":   "FC",
                "link_state": "up" if pt.get("is_link_up") else "down",
            })
        for pt in eth_ports:
            result["storage_ports"].append({
                "name":       pt.get("name", ""),
                "wwn":        None,
                "ip":         pt.get("ip_address", ""),
                "protocol":   "iSCSI/NFS",
                "link_state": pt.get("link_state", ""),
            })

    # ── Dell PowerFlex ───────────────────────────────────────────────
    elif vendor == "Dell PowerFlex":
        vol_list = data.get("volume_list", [])
        sdc_list = data.get("sdc_list", [])
        sds_list = data.get("sds_list", [])

        vol = next((v for v in vol_list if v["name"] == volume_name), None)
        if vol:
            result["volume"] = {
                "name":        vol.get("name"),
                "serial":      vol.get("id", ""),
                "wwn":         "",
                "size_bytes":  (vol.get("size_gb", 0) or 0) * 1024 ** 3,
                "used_bytes":  0,
                "storage_pool": vol.get("storage_pool", ""),
                "type":        vol.get("volume_type", ""),
                "mapped_sdcs": vol.get("mapped_sdc_count", 0),
                "protocol":    "NVMe/TCP (SDC)",
            }

        # SDC clients = compute hosts connected via PowerFlex SDC driver
        for sdc in sdc_list:
            result["connections"].append({
                "host":       sdc.get("name", sdc.get("id", "")),
                "host_group": None,
                "lun_id":     None,
                "port":       None,
                "protocol":   "NVMe/TCP (SDC)",
                "iqns":       [],
                "wwns":       [],
                "nqns":       [],
                "os_type":    sdc.get("os_type", sdc.get("host_os", "")),
                "active":     sdc.get("state", "") == "Active",
                "volume_wwn": None,
                "sdc_ip":     sdc.get("ip", ""),
                "sdc_approved": sdc.get("approved", False),
            })

    # ── HPE Nimble ───────────────────────────────────────────────────
    elif vendor == "HPE Nimble":
        vol_list = data.get("volume_list", [])
        ig_list  = data.get("initiator_group_list", [])
        fc_list  = data.get("fc_interface_list", [])

        vol = next((v for v in vol_list if v.get("name") == volume_name), None)
        if vol:
            result["volume"] = {
                "name":       vol.get("name"),
                "serial":     vol.get("serial", ""),
                "wwn":        "",
                "size_bytes": vol.get("size_bytes", 0),
                "used_bytes": vol.get("used_bytes", 0),
                "pool":       vol.get("pool", ""),
                "online":     vol.get("online", True),
                "connections": vol.get("num_connections", 0),
                "protocol":   "iSCSI/FC",
            }

        for ig in ig_list:
            proto = (ig.get("protocol") or "iscsi").upper()
            # _nimble_data stores iscsi_initiators/fc_initiators as flat string lists
            iqns = ig.get("iscsi_initiators", []) if proto == "ISCSI" else []
            wwns = ig.get("fc_initiators", [])    if proto == "FC"    else []
            result["connections"].append({
                "host":       ig.get("name", ""),
                "host_group": None,
                "lun_id":     None,
                "port":       None,
                "protocol":   proto,
                "iqns":       iqns,
                "wwns":       wwns,
                "nqns":       [],
                "os_type":    ig.get("host_type", ""),
                "active":     (ig.get("num_connections", 0) or 0) > 0,
                "volume_wwn": None,
            })

        for fc in fc_list:
            result["storage_ports"].append({
                "name":       fc.get("name", ""),
                "wwn":        fc.get("wwpn", ""),
                "ip":         None,
                "protocol":   "FC",
                "link_state": "up" if fc.get("online") else "down",
            })

    # ── Dell PowerScale (file-level NAS) ────────────────────────────
    elif vendor == "Dell PowerScale":
        vol = next((v for v in data.get("nfs_export_list", []) if volume_name in (v.get("paths") or [])), None)
        smb = next((v for v in data.get("smb_share_list", []) if v.get("path", "").rstrip("/") == volume_name.rstrip("/")), None)
        obj = vol or smb or {}
        result["volume"] = {
            "name":     volume_name,
            "serial":   "",
            "wwn":      "",
            "size_bytes": 0,
            "type":     "NFS Export" if vol else ("SMB Share" if smb else ""),
            "protocol": "NFS" if vol else ("SMB" if smb else "NFS/SMB"),
            "path":     (vol.get("paths") or [volume_name])[0] if vol else (smb.get("path", volume_name) if smb else volume_name),
        }
        if vol:
            for client in (vol.get("read_write_clients") or []):
                result["connections"].append({
                    "host": client, "host_group": None, "lun_id": None,
                    "port": None, "protocol": "NFS", "iqns": [], "wwns": [], "nqns": [],
                    "os_type": "Linux/Unix", "active": True, "volume_wwn": None,
                })
        if smb:
            for perm in (smb.get("permissions") or []):
                result["connections"].append({
                    "host": perm.get("trustee", {}).get("name", ""),
                    "host_group": None, "lun_id": None,
                    "port": None, "protocol": "SMB", "iqns": [], "wwns": [], "nqns": [],
                    "os_type": "Windows", "active": True, "volume_wwn": None,
                })

    # ── Pure FlashBlade (file/object) ────────────────────────────────
    elif vendor == "Pure Storage":
        fs_list  = data.get("fs_list", [])
        bkt_list = data.get("bkt_list", [])
        obj = next((f for f in fs_list if f.get("name") == volume_name), None) \
           or next((b for b in bkt_list if b.get("name") == volume_name), None) \
           or {}
        result["volume"] = {
            "name":       volume_name,
            "serial":     "",
            "wwn":        "",
            "size_bytes": obj.get("size_bytes", obj.get("provisioned", 0)),
            "used_bytes": obj.get("used_bytes", 0),
            "protocol":   "NFS/SMB" if obj.get("nfs_enabled") or obj.get("smb_enabled") else "S3",
            "type":       "FileSystem" if obj in fs_list else "S3 Bucket",
        }

    # ── Flatten into the structure VolumeTopologyModal expects ──────────
    vol   = result.get("volume", {})
    conns = result.get("connections", [])

    def _fmt_bytes(b):
        try:
            b = int(b or 0)
        except Exception:
            b = 0
        if b >= 1 << 40: return f"{b/(1<<40):.2f} TB"
        if b >= 1 << 30: return f"{b/(1<<30):.2f} GB"
        if b >= 1 << 20: return f"{b/(1<<20):.2f} MB"
        return f"{b} B" if b else ""

    # Rename "host" key to "host_name" in every connection entry
    flat_topo = []
    for conn in conns:
        entry = dict(conn)
        if "host_name" not in entry:
            entry["host_name"] = entry.pop("host", "")
        flat_topo.append(entry)

    # Build NAA ID — Pure FlashArray canonical format is naa.624a9370 + serial (lowercase).
    # vCenter/VMFS always reports the vendor-prefixed form, not the bare serial.
    _serial  = vol.get("serial", "") or ""
    _vvendor = result.get("vendor", "")
    if _serial and _vvendor in ("Pure FlashArray", "Pure Storage"):
        _naa_id       = "naa.624a9370" + _serial.lower()
        _naa_id_short = "naa." + _serial.lower()
    elif _serial:
        _naa_id       = "naa." + _serial.lower()
        _naa_id_short = _naa_id
    else:
        _naa_id       = vol.get("wwn", "") or ""
        _naa_id_short = _naa_id

    flat = {
        "vendor":         result.get("vendor", ""),
        "volume_name":    vol.get("name",       volume_name),
        "serial":         _serial,
        "wwn":            vol.get("wwn",        ""),
        "naa_id":         _naa_id,
        "naa_id_short":   _naa_id_short,
        "size":           _fmt_bytes(vol.get("size_bytes", 0)),
        "used":           _fmt_bytes(vol.get("used_bytes", 0)),
        "state":          vol.get("state",      ""),
        "protocol":       vol.get("protocol",   ""),
        "pool":           vol.get("cpg") or vol.get("pool") or vol.get("storage_pool") or "",
        "svm":            vol.get("svm",        ""),
        "pod":            vol.get("pod",        ""),
        "data_reduction": vol.get("data_reduction"),
        "thin":           vol.get("thin"),
        "lun_id":         vol.get("lun_id"),
        # extra vendor-specific passthrough
        "junction_path":  vol.get("junction_path", ""),
        "type":           vol.get("type", ""),
        "topology":       flat_topo,
        "storage_ports":  result.get("storage_ports", []),
        "replication":    result.get("replication", []),
        "error":          result.get("error"),
    }
    return flat
