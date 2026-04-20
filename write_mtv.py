import os

code = r'''"""
MTV (Migration Toolkit for Virtualization) Client
Real Forklift CRD integration for OpenShift migrations.
"""
import json
import logging
import time
import re
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("mtv_client")

# ---- constants ----
MTV_NS = "openshift-mtv"
FORKLIFT_API = "forklift.konveyor.io/v1beta1"
FORKLIFT_BASE = f"/apis/{FORKLIFT_API}/namespaces/{MTV_NS}"

# Provider name -> vcenter IP mapping (built dynamically)
_PROVIDER_CACHE = {}

# ---- helpers ----

def _ocp_cluster_for_target(target_detail):
    """Get the OCP cluster dict from openshift_client by cluster_id."""
    from openshift_client import get_cluster
    cid = target_detail.get("cluster_id")
    if not cid:
        raise ValueError("target_detail missing cluster_id")
    cluster = get_cluster(int(cid))
    if not cluster:
        raise ValueError(f"OCP cluster {cid} not found in DB")
    return cluster


def _api_get(cluster, path, timeout=30):
    from openshift_client import _api_get as _og
    return _og(cluster, path)


def _api_post(cluster, path, body, timeout=30):
    from openshift_client import _api_post as _op
    return _op(cluster, path, body)


def _api_delete(cluster, path):
    from openshift_client import _api_delete as _od
    return _od(cluster, path)


def _api_patch(cluster, path, body):
    """PATCH (merge-patch) a resource."""
    from openshift_client import _get_token
    token = _get_token(cluster)
    url = cluster["api_url"].rstrip("/") + path
    r = requests.patch(url,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/merge-patch+json"},
        data=json.dumps(body), verify=False, timeout=30)
    r.raise_for_status()
    return r.json()


def _inventory_url(cluster):
    """Get Forklift inventory route URL."""
    routes = _api_get(cluster, f"/apis/route.openshift.io/v1/namespaces/{MTV_NS}/routes")
    for r in routes.get("items", []):
        if r["metadata"]["name"] == "forklift-inventory":
            host = r["spec"]["host"]
            tls = r["spec"].get("tls")
            scheme = "https" if tls else "http"
            return f"{scheme}://{host}"
    raise ValueError("forklift-inventory route not found")


def _inv_headers(cluster):
    from openshift_client import _get_token
    return {"Authorization": f"Bearer {_get_token(cluster)}"}


def _safe_name(s):
    """Make a K8s-safe name."""
    s = re.sub(r'[^a-z0-9-]', '-', s.lower())
    s = re.sub(r'-+', '-', s).strip('-')
    return s[:58]


# ---- Provider resolution ----

def resolve_provider(cluster, vcenter_ip):
    """Find the Forklift Provider name for a given vCenter IP."""
    provs = _api_get(cluster, f"{FORKLIFT_BASE}/providers")
    for p in provs.get("items", []):
        spec = p.get("spec", {})
        if spec.get("type") == "vsphere":
            url = spec.get("url", "")
            if vcenter_ip in url:
                return p["metadata"]["name"]
    raise ValueError(f"No Forklift vsphere provider found for vCenter {vcenter_ip}")


def resolve_provider_uid(cluster, provider_name):
    """Get the inventory UID for a named provider."""
    inv = _inventory_url(cluster)
    headers = _inv_headers(cluster)
    r = requests.get(f"{inv}/providers/vsphere", headers=headers, verify=False, timeout=15)
    r.raise_for_status()
    for p in r.json():
        if p.get("name") == provider_name:
            return p["uid"]
    raise ValueError(f"Provider {provider_name} not found in inventory")


# ---- Inventory lookups ----

def lookup_vm_ids(cluster, provider_name, vm_names):
    """Resolve VM names to Forklift vm-XXXX IDs via inventory."""
    inv = _inventory_url(cluster)
    headers = _inv_headers(cluster)
    uid = resolve_provider_uid(cluster, provider_name)
    r = requests.get(f"{inv}/providers/vsphere/{uid}/vms", headers=headers, verify=False, timeout=60)
    r.raise_for_status()
    all_vms = r.json()
    name_map = {v["name"].lower(): v for v in all_vms}
    results = []
    for vn in vm_names:
        found = name_map.get(vn.lower())
        if found:
            results.append({"id": found["id"], "name": found["name"]})
        else:
            log.warning(f"VM '{vn}' not found in provider {provider_name}")
    return results


def lookup_networks(cluster, provider_name):
    """Get all networks from a vsphere provider."""
    inv = _inventory_url(cluster)
    headers = _inv_headers(cluster)
    uid = resolve_provider_uid(cluster, provider_name)
    r = requests.get(f"{inv}/providers/vsphere/{uid}/networks", headers=headers, verify=False, timeout=15)
    r.raise_for_status()
    return r.json()


def lookup_datastores(cluster, provider_name):
    """Get all datastores from a vsphere provider."""
    inv = _inventory_url(cluster)
    headers = _inv_headers(cluster)
    uid = resolve_provider_uid(cluster, provider_name)
    r = requests.get(f"{inv}/providers/vsphere/{uid}/datastores", headers=headers, verify=False, timeout=15)
    r.raise_for_status()
    return r.json()


def lookup_ocp_storage_classes(cluster):
    """Get storage classes from OCP host provider."""
    inv = _inventory_url(cluster)
    headers = _inv_headers(cluster)
    r = requests.get(f"{inv}/providers/openshift", headers=headers, verify=False, timeout=15)
    r.raise_for_status()
    for p in r.json():
        if p.get("name") == "host":
            uid = p["uid"]
            r2 = requests.get(f"{inv}/providers/openshift/{uid}/storageclasses", headers=headers, verify=False, timeout=15)
            r2.raise_for_status()
            return r2.json()
    return []


def lookup_ocp_nads(cluster):
    """Get NetworkAttachmentDefinitions from OCP host provider."""
    inv = _inventory_url(cluster)
    headers = _inv_headers(cluster)
    r = requests.get(f"{inv}/providers/openshift", headers=headers, verify=False, timeout=15)
    r.raise_for_status()
    for p in r.json():
        if p.get("name") == "host":
            uid = p["uid"]
            r2 = requests.get(f"{inv}/providers/openshift/{uid}/networkattachmentdefinitions", headers=headers, verify=False, timeout=15)
            r2.raise_for_status()
            return r2.json()
    return []


# ---- CRD creation ----

def create_network_map(cluster, name, source_provider, network_mappings):
    """Create a Forklift NetworkMap CRD.
    network_mappings: list of {"source_id": "network-XXXX", "source_name": "...",
                                "dest_type": "pod"|"multus", "dest_name": "...", "dest_namespace": "..."}
    """
    map_entries = []
    for m in network_mappings:
        dest_type = m.get("dest_type", "pod")
        if dest_type == "pod":
            entry = {
                "source": {"id": m["source_id"], "name": m.get("source_name", "")},
                "destination": {"type": "pod"}
            }
        else:
            entry = {
                "source": {"id": m["source_id"], "name": m.get("source_name", "")},
                "destination": {
                    "type": "multus",
                    "name": m["dest_name"],
                    "namespace": m.get("dest_namespace", "default")
                }
            }
        map_entries.append(entry)

    body = {
        "apiVersion": FORKLIFT_API,
        "kind": "NetworkMap",
        "metadata": {"name": name, "namespace": MTV_NS},
        "spec": {
            "map": map_entries,
            "provider": {
                "source": {"name": source_provider, "namespace": MTV_NS},
                "destination": {"name": "host", "namespace": MTV_NS}
            }
        }
    }
    return _api_post(cluster, f"{FORKLIFT_BASE}/networkmaps", body)


def create_storage_map(cluster, name, source_provider, storage_mappings):
    """Create a Forklift StorageMap CRD.
    storage_mappings: list of {"source_id": "datastore-XXXX", "dest_storage_class": "..."}
    """
    map_entries = []
    for m in storage_mappings:
        map_entries.append({
            "source": {"id": m["source_id"]},
            "destination": {"storageClass": m["dest_storage_class"]}
        })

    body = {
        "apiVersion": FORKLIFT_API,
        "kind": "StorageMap",
        "metadata": {"name": name, "namespace": MTV_NS},
        "spec": {
            "map": map_entries,
            "provider": {
                "source": {"name": source_provider, "namespace": MTV_NS},
                "destination": {"name": "host", "namespace": MTV_NS}
            }
        }
    }
    return _api_post(cluster, f"{FORKLIFT_BASE}/storagemaps", body)


def create_mtv_plan(cluster, name, source_provider, network_map_name, storage_map_name,
                    vm_ids, target_namespace="openshift-mtv", warm=True):
    """Create a Forklift Plan CRD."""
    body = {
        "apiVersion": FORKLIFT_API,
        "kind": "Plan",
        "metadata": {"name": name, "namespace": MTV_NS},
        "spec": {
            "archived": False,
            "description": f"CaaS Dashboard migration plan: {name}",
            "warm": warm,
            "provider": {
                "source": {"name": source_provider, "namespace": MTV_NS},
                "destination": {"name": "host", "namespace": MTV_NS}
            },
            "map": {
                "network": {"name": network_map_name, "namespace": MTV_NS},
                "storage": {"name": storage_map_name, "namespace": MTV_NS}
            },
            "targetNamespace": target_namespace,
            "vms": [{"id": v["id"], "name": v["name"], "hooks": []} for v in vm_ids],
            "preserveStaticIPs": True,
            "runPreflightInspection": True,
        }
    }
    return _api_post(cluster, f"{FORKLIFT_BASE}/plans", body)


def create_migration(cluster, plan_name):
    """Create a Forklift Migration CRD to trigger the migration."""
    from datetime import datetime, timezone
    cutover = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {
        "apiVersion": FORKLIFT_API,
        "kind": "Migration",
        "metadata": {
            "name": plan_name,
            "namespace": MTV_NS
        },
        "spec": {
            "plan": {"name": plan_name, "namespace": MTV_NS},
            "cutover": cutover
        }
    }
    return _api_post(cluster, f"{FORKLIFT_BASE}/migrations", body)


# ---- Status polling ----

def get_plan_status(cluster, plan_name):
    """Get Plan CRD status including VM pipeline progress."""
    try:
        plan = _api_get(cluster, f"{FORKLIFT_BASE}/plans/{plan_name}")
    except Exception as e:
        return {"error": str(e), "phase": "unknown"}

    status = plan.get("status", {})
    conditions = status.get("conditions", [])
    migration = status.get("migration", {})

    # Determine overall phase
    phase = "unknown"
    for cond in conditions:
        if cond.get("type") == "Succeeded" and cond.get("status") == "True":
            phase = "completed"
        elif cond.get("type") == "Failed" and cond.get("status") == "True":
            phase = "failed"
        elif cond.get("type") == "Ready" and cond.get("status") == "True":
            if migration.get("started") and not migration.get("completed"):
                phase = "migrating"
            elif not migration.get("started"):
                phase = "ready"

    if migration.get("completed") and phase != "failed":
        phase = "completed"
    elif migration.get("started") and not migration.get("completed") and phase != "failed":
        phase = "migrating"

    # Extract VM-level progress
    vms_status = []
    total_bytes = 0
    completed_bytes = 0
    for vm in migration.get("vms", []):
        vm_info = {
            "name": vm.get("name", ""),
            "id": vm.get("id", ""),
            "phase": vm.get("phase", "Pending"),
            "started": vm.get("started", ""),
            "completed": vm.get("completed", ""),
            "pipeline": []
        }
        for step in vm.get("pipeline", []):
            prog = step.get("progress", {})
            t = prog.get("total", 0)
            c = prog.get("completed", 0)
            if step.get("name") == "DiskTransfer":
                total_bytes += t
                completed_bytes += c
            vm_info["pipeline"].append({
                "name": step["name"],
                "phase": step.get("phase", "Pending"),
                "total": t,
                "completed": c,
                "description": step.get("description", ""),
            })
        # Check conditions for success/failure
        for cond in vm.get("conditions", []):
            if cond.get("type") == "Succeeded":
                vm_info["succeeded"] = cond.get("status") == "True"
            if cond.get("type") == "Failed":
                vm_info["failed"] = cond.get("status") == "True"
                vm_info["error"] = cond.get("message", "")
        vms_status.append(vm_info)

    # Calculate overall progress %
    progress = 0
    if total_bytes > 0:
        progress = int(completed_bytes / total_bytes * 80) + 10  # 10-90 for disk transfer
    if phase == "completed":
        progress = 100
    elif phase == "migrating" and total_bytes == 0:
        progress = 5  # Just started

    return {
        "phase": phase,
        "progress": progress,
        "started": migration.get("started", ""),
        "completed": migration.get("completed", ""),
        "conditions": [{"type": c["type"], "status": c["status"], "message": c.get("message","")} for c in conditions],
        "vms": vms_status,
        "total_disk_mb": total_bytes,
        "completed_disk_mb": completed_bytes,
    }


def get_migration_status(cluster, migration_name):
    """Get Migration CRD status."""
    try:
        mig = _api_get(cluster, f"{FORKLIFT_BASE}/migrations/{migration_name}")
        return mig.get("status", {})
    except:
        return {}


# ---- Cleanup ----

def delete_mtv_resources(cluster, name):
    """Delete all MTV CRDs for a plan (migration, plan, maps)."""
    errors = []
    for kind in ["migrations", "plans", "networkmaps", "storagemaps"]:
        try:
            _api_delete(cluster, f"{FORKLIFT_BASE}/{kind}/{name}")
        except Exception as e:
            if "404" not in str(e):
                errors.append(f"{kind}/{name}: {e}")
    # Also try with suffixed map names
    for suffix in ["-nw", "-st"]:
        kind = "networkmaps" if "nw" in suffix else "storagemaps"
        try:
            _api_delete(cluster, f"{FORKLIFT_BASE}/{kind}/{name}{suffix}")
        except:
            pass
    return errors


# ---- Full orchestration ----

def orchestrate_migration(plan_db_row, log_fn=None):
    """
    Full MTV migration orchestration:
    1. Resolve provider
    2. Lookup VM IDs from inventory
    3. Build network/storage maps from plan mappings
    4. Create NetworkMap, StorageMap, Plan, Migration CRDs
    5. Return the MTV plan name for polling

    plan_db_row: dict from migration_plans table
    log_fn: callable(plan_id, message, user) for event logging
    """
    plan_id = plan_db_row["id"]
    plan_name = _safe_name(plan_db_row["plan_name"])
    target_detail = json.loads(plan_db_row["target_detail"]) if isinstance(plan_db_row["target_detail"], str) else (plan_db_row["target_detail"] or {})
    source_vc = json.loads(plan_db_row["source_vcenter"]) if isinstance(plan_db_row["source_vcenter"], str) else (plan_db_row["source_vcenter"] or {})
    vm_list = json.loads(plan_db_row["vm_list"]) if isinstance(plan_db_row["vm_list"], str) else (plan_db_row["vm_list"] or [])
    net_mapping = json.loads(plan_db_row["network_mapping"]) if isinstance(plan_db_row.get("network_mapping") or "", str) and plan_db_row.get("network_mapping") else (plan_db_row.get("network_mapping") or [])
    stor_mapping = json.loads(plan_db_row["storage_mapping"]) if isinstance(plan_db_row.get("storage_mapping") or "", str) and plan_db_row.get("storage_mapping") else (plan_db_row.get("storage_mapping") or [])

    def _log(msg):
        if log_fn:
            log_fn(plan_id, msg, "system")
        log.info(f"[MTV plan={plan_name}] {msg}")

    # 1. Get OCP cluster
    cluster = _ocp_cluster_for_target(target_detail)
    _log(f"Connected to OCP cluster: {cluster['name']} ({cluster['api_url']})")

    # 2. Resolve vCenter provider
    vc_ip = source_vc.get("vcenter_id", "")
    source_provider = resolve_provider(cluster, vc_ip)
    _log(f"Resolved vCenter {vc_ip} -> Forklift provider '{source_provider}'")

    # 3. Lookup VM IDs
    vm_names = [v.get("name", v) if isinstance(v, dict) else v for v in vm_list]
    vm_ids = lookup_vm_ids(cluster, source_provider, vm_names)
    if not vm_ids:
        raise ValueError(f"No VMs found in provider inventory for: {vm_names}")
    _log(f"Resolved {len(vm_ids)} VM(s): {', '.join(v['name']+' ('+v['id']+')' for v in vm_ids)}")

    # 4. Build network mappings
    # Get all source networks and datastores for default mapping
    src_networks = lookup_networks(cluster, source_provider)
    src_datastores = lookup_datastores(cluster, source_provider)
    net_id_map = {n["name"]: n["id"] for n in src_networks}
    ds_id_map = {d["name"]: d["id"] for d in src_datastores}

    nw_name = f"{plan_name}-nw"
    st_name = f"{plan_name}-st"

    # Build network map entries
    nw_entries = []
    if net_mapping:
        for m in net_mapping:
            src_name = m.get("source", "")
            tgt_name = m.get("target", "Pod Network (default)")
            src_id = net_id_map.get(src_name, "")
            if not src_id:
                # Try to find by partial match
                for k, v in net_id_map.items():
                    if src_name.lower() in k.lower():
                        src_id = v
                        src_name = k
                        break
            if not src_id and src_networks:
                # Default to first network
                src_id = src_networks[0]["id"]
                src_name = src_networks[0]["name"]
            if "pod" in tgt_name.lower() or tgt_name == "Pod Network (default)":
                nw_entries.append({"source_id": src_id, "source_name": src_name, "dest_type": "pod"})
            else:
                nw_entries.append({"source_id": src_id, "source_name": src_name,
                                   "dest_type": "multus", "dest_name": tgt_name, "dest_namespace": "default"})
    if not nw_entries and src_networks:
        # Fallback: map first network to pod network
        nw_entries.append({"source_id": src_networks[0]["id"], "source_name": src_networks[0]["name"], "dest_type": "pod"})

    # Build storage map entries
    st_entries = []
    if stor_mapping:
        for m in stor_mapping:
            src_name = m.get("source", "")
            tgt_sc = m.get("target", "purestorage-sc")
            src_id = ds_id_map.get(src_name, "")
            if not src_id:
                for k, v in ds_id_map.items():
                    if src_name.lower() in k.lower():
                        src_id = v
                        break
            if not src_id and src_datastores:
                src_id = src_datastores[0]["id"]
            st_entries.append({"source_id": src_id, "dest_storage_class": tgt_sc})
    if not st_entries and src_datastores:
        st_entries.append({"source_id": src_datastores[0]["id"], "dest_storage_class": "purestorage-sc"})

    # 5. Create CRDs - cleanup old ones first
    _log("Cleaning up any existing MTV resources...")
    delete_mtv_resources(cluster, plan_name)
    delete_mtv_resources(cluster, nw_name)
    delete_mtv_resources(cluster, st_name)
    import time as _time
    _time.sleep(3)

    _log(f"Creating NetworkMap '{nw_name}' with {len(nw_entries)} mapping(s)...")
    create_network_map(cluster, nw_name, source_provider, nw_entries)

    _log(f"Creating StorageMap '{st_name}' with {len(st_entries)} mapping(s)...")
    create_storage_map(cluster, st_name, source_provider, st_entries)

    _time.sleep(2)
    _log(f"Creating MTV Plan '{plan_name}' with {len(vm_ids)} VM(s)...")
    create_mtv_plan(cluster, plan_name, source_provider, nw_name, st_name, vm_ids)

    # Wait for plan to be Ready
    _log("Waiting for Plan to become Ready...")
    for attempt in range(30):
        _time.sleep(5)
        st = get_plan_status(cluster, plan_name)
        ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in st.get("conditions", []))
        if ready:
            _log("Plan is Ready. Creating Migration to trigger execution...")
            break
        errs = [c for c in st.get("conditions", []) if c.get("type") in ("Failed",) and c.get("status") == "True"]
        if errs:
            raise ValueError(f"Plan failed: {errs[0].get('message','')}")
    else:
        _log("WARNING: Plan not Ready after 150s, attempting migration anyway...")

    # 6. Create Migration (this triggers the actual migration)
    create_migration(cluster, plan_name)
    _log(f"Migration '{plan_name}' created! MTV is now migrating VMs...")

    return plan_name


def poll_mtv_status(plan_db_row):
    """Poll real MTV status and return structured result."""
    target_detail = json.loads(plan_db_row["target_detail"]) if isinstance(plan_db_row["target_detail"], str) else (plan_db_row["target_detail"] or {})
    plan_name = _safe_name(plan_db_row["plan_name"])
    cluster = _ocp_cluster_for_target(target_detail)
    return get_plan_status(cluster, plan_name)
'''

open(r"C:\caas-dashboard\backend\mtv_client.py", "w", encoding="utf-8").write(code)
print(f"Written {len(code)} bytes")