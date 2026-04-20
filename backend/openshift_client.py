"""
openshift_client.py - Red Hat OpenShift 4.x cluster integration
Live data via Kubernetes/OpenShift REST API (no oc/kubectl CLI needed).
Auth: username + password -> OAuth token exchange
"""
import os, json, logging, base64, time, urllib.parse
from pathlib import Path
from datetime import datetime

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("caas.openshift")

# Token cache {cluster_id: {"token": "...", "expires": epoch}}
_TOKEN_CACHE: dict = {}
_TOKEN_TTL   = 82800   # 23 hours

#  DB helpers 
def _get_db():
    import sqlite3
    db_path = Path(__file__).parent / "caas.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def init_openshift_db():
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ocp_clusters (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            api_url     TEXT NOT NULL,
            console_url TEXT DEFAULT '',
            version     TEXT DEFAULT '',
            description TEXT DEFAULT '',
            username    TEXT DEFAULT '',
            password    TEXT DEFAULT '',
            token       TEXT DEFAULT '',
            status      TEXT DEFAULT 'unknown',
            created_by  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    for col in ("username", "password", "ai_url"):
        try:
            c.execute(f"ALTER TABLE ocp_clusters ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass
    # OCP VM Requests table
    c.execute("""
        CREATE TABLE IF NOT EXISTS ocp_vm_requests (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            req_number           TEXT    UNIQUE NOT NULL,
            requester            TEXT    NOT NULL,
            cluster_id           INTEGER NOT NULL,
            cluster_name         TEXT    NOT NULL DEFAULT '',
            namespace            TEXT    NOT NULL DEFAULT 'default',
            vm_name              TEXT    NOT NULL,
            description          TEXT    DEFAULT '',
            os_template          TEXT    NOT NULL DEFAULT 'rhel9',
            cpu_sockets          INTEGER DEFAULT 1,
            cpu_cores            INTEGER DEFAULT 2,
            cpu_threads          INTEGER DEFAULT 1,
            memory_gi            INTEGER DEFAULT 4,
            boot_disk_size       TEXT    DEFAULT '30Gi',
            boot_disk_sc         TEXT    DEFAULT '',
            boot_disk_interface  TEXT    DEFAULT 'virtio',
            additional_disks     TEXT    DEFAULT '[]',
            network_type         TEXT    DEFAULT 'masquerade',
            network_interface    TEXT    DEFAULT 'virtio',
            network_name         TEXT    DEFAULT 'Pod Networking',
            cloud_init_enabled   INTEGER DEFAULT 1,
            ssh_public_key       TEXT    DEFAULT '',
            root_password        TEXT    DEFAULT '',
            start_on_create      INTEGER DEFAULT 1,
            notes                TEXT    DEFAULT '',
            status               TEXT    DEFAULT 'pending',
            reviewed_by          TEXT    DEFAULT NULL,
            review_notes         TEXT    DEFAULT '',
            reviewed_at          TEXT    DEFAULT NULL,
            created_at           TEXT    DEFAULT (datetime('now')),
            updated_at           TEXT    DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    log.info("OpenShift DB tables initialized")


# ── OCP VM Request CRUD ──────────────────────────────────────────────────────

def _next_ocp_req_number() -> str:
    conn = _get_db()
    count = conn.execute("SELECT COUNT(*) FROM ocp_vm_requests").fetchone()[0]
    conn.close()
    return f"OCPREQ-{str(count + 1).zfill(5)}"

def create_ocp_vm_req(data: dict) -> dict:
    rn = _next_ocp_req_number()
    conn = _get_db()
    conn.execute("""
        INSERT INTO ocp_vm_requests
            (req_number, requester, cluster_id, cluster_name, namespace, vm_name,
             description, os_template, cpu_sockets, cpu_cores, cpu_threads,
             memory_gi, boot_disk_size, boot_disk_sc, boot_disk_interface,
             additional_disks, network_type, network_interface, network_name,
             cloud_init_enabled, ssh_public_key, root_password, start_on_create, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (rn, data["requester"], data["cluster_id"], data.get("cluster_name",""),
          data.get("namespace","default"), data["vm_name"],
          data.get("description",""), data.get("os_template","rhel9"),
          data.get("cpu_sockets",1), data.get("cpu_cores",2), data.get("cpu_threads",1),
          data.get("memory_gi",4), data.get("boot_disk_size","30Gi"),
          data.get("boot_disk_sc",""), data.get("boot_disk_interface","virtio"),
          json.dumps(data.get("additional_disks",[])),
          data.get("network_type","masquerade"), data.get("network_interface","virtio"),
          data.get("network_name","Pod Networking"),
          1 if data.get("cloud_init_enabled",True) else 0,
          data.get("ssh_public_key",""), data.get("root_password",""),
          1 if data.get("start_on_create",True) else 0,
          data.get("notes","")))
    conn.commit()
    row = conn.execute("SELECT * FROM ocp_vm_requests WHERE req_number=?",(rn,)).fetchone()
    conn.close()
    return dict(row) if row else {}

def list_ocp_vm_reqs(requester: str = None, status: str = None) -> list:
    sql = "SELECT * FROM ocp_vm_requests WHERE 1=1"
    params = []
    if requester:
        sql += " AND requester=?"; params.append(requester)
    if status:
        sql += " AND status=?"; params.append(status)
    sql += " ORDER BY created_at DESC"
    conn = _get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_ocp_vm_req(req_id: int) -> dict | None:
    conn = _get_db()
    row = conn.execute("SELECT * FROM ocp_vm_requests WHERE id=?",(req_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def review_ocp_vm_req(req_id: int, reviewer: str, decision: str, review_notes: str = "") -> dict | None:
    conn = _get_db()
    conn.execute("""
        UPDATE ocp_vm_requests
           SET status=?, reviewed_by=?, review_notes=?, reviewed_at=datetime('now'),
               updated_at=datetime('now')
         WHERE id=?
    """, (decision, reviewer, review_notes, req_id))
    conn.commit()
    row = conn.execute("SELECT * FROM ocp_vm_requests WHERE id=?",(req_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

#  Cluster CRUD 
def _safe(d):
    d2 = dict(d)
    d2.pop("password", None)
    return d2

def list_clusters():
    conn = _get_db()
    rows = conn.execute("SELECT * FROM ocp_clusters ORDER BY name").fetchall()
    conn.close()
    return [_safe(dict(r)) for r in rows]

def get_cluster(cluster_id: int):
    conn = _get_db()
    row = conn.execute("SELECT * FROM ocp_clusters WHERE id=?", (cluster_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def find_cluster_by_url(api_url: str):
    conn = _get_db()
    row = conn.execute("SELECT * FROM ocp_clusters WHERE api_url=?", (api_url,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_cluster(data: dict) -> dict:
    conn = _get_db()
    now = _now()
    try:
        cur = conn.execute("""
            INSERT INTO ocp_clusters
              (name, api_url, console_url, ai_url, version, description,
               username, password, token, status, created_by, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["name"], data["api_url"],
            data.get("console_url",""), data.get("ai_url",""),
            data.get("version",""),
            data.get("description",""),
            data.get("username",""), data.get("password",""),
            data.get("token",""),    "unknown",
            data["created_by"], now, now
        ))
        conn.commit()
        row = conn.execute("SELECT * FROM ocp_clusters WHERE id=?", (cur.lastrowid,)).fetchone()
        return _safe(dict(row))
    except Exception as e:
        raise ValueError(str(e))
    finally:
        conn.close()

def update_cluster(cluster_id: int, data: dict) -> dict:
    conn = _get_db()
    now  = _now()
    fields, vals = [], []
    for k in ("name","api_url","console_url","ai_url","version","description","username","password","token","status"):
        if k in data:
            fields.append(f"{k}=?")
            vals.append(data[k])
    if not fields:
        conn.close()
        c = get_cluster(cluster_id)
        return _safe(c) if c else None
    fields.append("updated_at=?");  vals.append(now);  vals.append(cluster_id)
    conn.execute(f"UPDATE ocp_clusters SET {','.join(fields)} WHERE id=?", vals)
    conn.commit()
    row = conn.execute("SELECT * FROM ocp_clusters WHERE id=?", (cluster_id,)).fetchone()
    conn.close()
    return _safe(dict(row)) if row else None

def delete_cluster(cluster_id: int) -> bool:
    _TOKEN_CACHE.pop(cluster_id, None)
    conn = _get_db()
    r = conn.execute("DELETE FROM ocp_clusters WHERE id=?", (cluster_id,))
    conn.commit()
    conn.close()
    return r.rowcount > 0

#  OAuth token fetch 
def _fetch_token_password(api_url: str, username: str, password: str) -> str:
    """OCP 4.x: discover OAuth endpoint, then exchange username+password for token."""
    disc = requests.get(f"{api_url}/.well-known/oauth-authorization-server",
                        verify=False, timeout=10)
    disc.raise_for_status()
    auth_endpoint = disc.json()["authorization_endpoint"]
    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    r = requests.get(
        auth_endpoint,
        params={"client_id": "openshift-challenging-client", "response_type": "token"},
        headers={"Authorization": f"Basic {creds}", "X-CSRF-Token": "caas-portal"},
        verify=False, allow_redirects=False, timeout=10,
    )
    location = r.headers.get("Location", "")
    if not location:
        raise ValueError(f"OAuth server returned no redirect (HTTP {r.status_code}). Check credentials.")
    fragment = urllib.parse.urlparse(location).fragment
    params   = urllib.parse.parse_qs(fragment)
    token    = params.get("access_token", [""])[0]
    if not token:
        raise ValueError("access_token not found in OAuth redirect. Check username/password.")
    return token

def _get_token(cluster: dict) -> str:
    cid    = cluster["id"]
    cached = _TOKEN_CACHE.get(cid)
    if cached and time.time() < cached["expires"]:
        return cached["token"]
    # Static token first
    static = (cluster.get("token") or "").strip()
    if static:
        _TOKEN_CACHE[cid] = {"token": static, "expires": time.time() + _TOKEN_TTL}
        return static
    # Username+password
    username = (cluster.get("username") or "").strip()
    password = (cluster.get("password") or "").strip()
    if not username or not password:
        raise ValueError("No credentials configured for cluster")
    token = _fetch_token_password(cluster["api_url"], username, password)
    _TOKEN_CACHE[cid] = {"token": token, "expires": time.time() + _TOKEN_TTL}
    return token

#  REST API helper 
def _api_get(cluster: dict, path: str, params: dict = None) -> dict:
    token = _get_token(cluster)
    url   = cluster["api_url"].rstrip("/") + path
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                     params=params or {}, verify=False, timeout=30)
    r.raise_for_status()
    return r.json()

def _api_delete(cluster: dict, path: str) -> dict:
    token = _get_token(cluster)
    url   = cluster["api_url"].rstrip("/") + path
    r = requests.delete(url, headers={"Authorization": f"Bearer {token}"},
                        verify=False, timeout=30)
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return {"status": "deleted"}

def _api_post(cluster: dict, path: str, body: dict) -> dict:
    import json as _json
    token = _get_token(cluster)
    url   = cluster["api_url"].rstrip("/") + path
    r = requests.post(url, headers={"Authorization": f"Bearer {token}",
                                    "Content-Type": "application/json"},
                      data=_json.dumps(body), verify=False, timeout=30)
    r.raise_for_status()
    return r.json()

#  Live data 
def _parse_cpu(cpu_str: str) -> float:
    """Convert CPU string (e.g. '250m', '4', '2000m') to cores float."""
    if not cpu_str:
        return 0.0
    cpu_str = cpu_str.strip()
    if cpu_str.endswith("m"):
        return round(int(cpu_str[:-1]) / 1000, 3)
    try:
        return float(cpu_str)
    except Exception:
        return 0.0

def _parse_mem_gi(mem_str: str) -> float:
    """Convert memory string to GiB float."""
    if not mem_str:
        return 0.0
    mem_str = mem_str.strip()
    if mem_str.endswith("Ki"):
        return round(int(mem_str[:-2]) / 1024**2, 2)
    if mem_str.endswith("Mi"):
        return round(int(mem_str[:-2]) / 1024, 2)
    if mem_str.endswith("Gi"):
        return round(float(mem_str[:-2]), 2)
    if mem_str.endswith("Ti"):
        return round(float(mem_str[:-2]) * 1024, 2)
    try:
        return round(int(mem_str) / 1024**3, 2)
    except Exception:
        return 0.0

def get_cluster_version(cluster: dict) -> dict:
    try:
        data    = _api_get(cluster, "/apis/config.openshift.io/v1/clusterversions/version")
        spec    = data.get("spec", {})
        status  = data.get("status", {})
        history = status.get("history", [])
        current = next((h for h in history if h.get("state") == "Completed"), {})
        # channel is in spec.channel; clusterID is in spec.clusterID in OCP 4.x
        channel    = spec.get("channel","") or status.get("channel","")
        cluster_id = spec.get("clusterID","") or status.get("clusterID","")
        return {
            "version":           current.get("version") or status.get("desired",{}).get("version",""),
            "channel":           channel,
            "cluster_id":        cluster_id,
            "available_updates": len(status.get("availableUpdates") or []),
        }
    except Exception as e:
        return {"error": str(e)}

def get_live_nodes(cluster: dict) -> list:
    try:
        data  = _api_get(cluster, "/api/v1/nodes")
        items = data.get("items", [])
    except Exception:
        return []

    metrics_map = {}
    try:
        m = _api_get(cluster, "/apis/metrics.k8s.io/v1beta1/nodes")
        for item in m.get("items", []):
            nm = item["metadata"]["name"]
            metrics_map[nm] = {
                "cpu_usage_cores": _parse_cpu(item["usage"].get("cpu","0")),
                "mem_usage_gi":    _parse_mem_gi(item["usage"].get("memory","0")),
            }
    except Exception:
        pass

    nodes = []
    for item in items:
        meta   = item.get("metadata", {})
        status = item.get("status", {})
        spec   = item.get("spec", {})
        labels = meta.get("labels", {})
        conds  = status.get("conditions", [])
        roles  = sorted(lk.split("/")[-1] for lk in labels if "node-role.kubernetes.io/" in lk)
        role   = ", ".join(roles) if roles else "worker"
        ready_cond  = next((c for c in conds if c["type"] == "Ready"), {})
        ready       = ready_cond.get("status") == "True"
        pressures   = [c["type"] for c in conds if c["type"] != "Ready" and c.get("status") == "True"]
        capacity    = status.get("capacity", {})
        allocatable = status.get("allocatable", {})
        node_info   = status.get("nodeInfo", {})
        addrs       = status.get("addresses", [])
        internal_ip = next((a["address"] for a in addrs if a["type"] == "InternalIP"), "")
        taints      = spec.get("taints", [])
        unschedulable = bool(spec.get("unschedulable")) or any(t.get("effect")=="NoSchedule" for t in taints)
        m = metrics_map.get(meta["name"], {})
        cpu_alloc = _parse_cpu(allocatable.get("cpu",""))
        mem_alloc = _parse_mem_gi(allocatable.get("memory",""))
        nodes.append({
            "name":              meta["name"],
            "role":              role,
            "status":            "Ready" if ready else "NotReady",
            "ready":             ready,
            "reason":            ready_cond.get("reason",""),
            "pressures":         pressures,
            "unschedulable":     unschedulable,
            "ip":                internal_ip,
            "cpu_capacity":      capacity.get("cpu",""),
            "cpu_allocatable":   allocatable.get("cpu",""),
            "cpu_allocatable_cores": _parse_cpu(allocatable.get("cpu","")),
            "cpu_usage_cores":   m.get("cpu_usage_cores",0.0),
            "cpu_usage_pct":     round(m.get("cpu_usage_cores",0.0) / cpu_alloc * 100, 1) if cpu_alloc else 0,
            "mem_capacity_gi":   _parse_mem_gi(capacity.get("memory","")),
            "mem_allocatable_gi": mem_alloc,
            "mem_usage_gi":      m.get("mem_usage_gi",0.0),
            "mem_usage_pct":     round(m.get("mem_usage_gi",0.0) / mem_alloc * 100, 1) if mem_alloc else 0,
            "pods_capacity":     int(capacity.get("pods","0") or 0),
            "os_image":          node_info.get("osImage",""),
            "kernel":            node_info.get("kernelVersion",""),
            "container_runtime": node_info.get("containerRuntimeVersion",""),
            "kube_version":      node_info.get("kubeletVersion",""),
            "architecture":      node_info.get("architecture",""),
            "created_at":        meta.get("creationTimestamp",""),
            "taints":            [f"{t.get('key')}:{t.get('effect')}" for t in taints],
        })
    return nodes

def get_pods(cluster: dict, namespace: str = "") -> list:
    try:
        path  = f"/api/v1/namespaces/{namespace}/pods" if namespace and namespace != "all" else "/api/v1/pods"
        data  = _api_get(cluster, path)
        items = data.get("items", [])
    except Exception:
        return []
    pods = []
    for item in items:
        meta   = item.get("metadata", {})
        status = item.get("status", {})
        spec   = item.get("spec", {})
        cs     = status.get("containerStatuses", [])
        pods.append({
            "name":       meta["name"],
            "namespace":  meta.get("namespace",""),
            "node":       spec.get("nodeName",""),
            "phase":      status.get("phase","Unknown"),
            "ready":      f"{sum(1 for c in cs if c.get('ready'))}/{len(spec.get('containers',[]))}",
            "restarts":   sum(c.get("restartCount",0) for c in cs),
            "start_time": status.get("startTime") or meta.get("creationTimestamp",""),
            "pod_ip":     status.get("podIP",""),
            "host_ip":    status.get("hostIP",""),
            "qos_class":  status.get("qosClass",""),
        })
    return pods

def get_pod_detail(cluster: dict, namespace: str, pod_name: str) -> dict:
    """Full pod detail matching OpenShift UI — includes containers, conditions, volumes, labels, etc."""
    try:
        data   = _api_get(cluster, f"/api/v1/namespaces/{namespace}/pods/{pod_name}")
    except Exception as e:
        return {"error": str(e)}
    meta   = data.get("metadata", {})
    spec   = data.get("spec", {})
    status = data.get("status", {})
    cs_map = {c["name"]: c for c in status.get("containerStatuses", [])}
    ics_map= {c["name"]: c for c in status.get("initContainerStatuses", [])}

    def _fmt_resources(r):
        if not r: return {}
        return {k: dict(v) for k, v in r.items()}

    def _container_info(c, stat_map):
        st = stat_map.get(c["name"], {})
        raw_state = st.get("state", {})
        state_key = next(iter(raw_state), "unknown")
        state_val = raw_state.get(state_key, {})
        return {
            "name":          c.get("name",""),
            "image":         c.get("image",""),
            "image_pull_policy": c.get("imagePullPolicy",""),
            "state":         state_key,
            "state_reason":  state_val.get("reason","") or state_val.get("exitCode",""),
            "started_at":    state_val.get("startedAt",""),
            "finished_at":   state_val.get("finishedAt",""),
            "ready":         st.get("ready", False),
            "restarts":      st.get("restartCount", 0),
            "ports": [{"name": p.get("name",""), "container_port": p.get("containerPort",""),
                       "protocol": p.get("protocol","TCP")} for p in c.get("ports",[])],
            "resources": {
                "requests": _fmt_resources(c.get("resources",{}).get("requests",{})),
                "limits":   _fmt_resources(c.get("resources",{}).get("limits",{})),
            },
            "env": [{"name": e.get("name",""),
                     "value": e.get("value") or ("[configMapKeyRef]" if "configMapKeyRef" in e.get("valueFrom",{})
                               else "[secretKeyRef]" if "secretKeyRef" in e.get("valueFrom",{})
                               else "[fieldRef]" if "fieldRef" in e.get("valueFrom",{}) else ""),
                     "value_from": list(e["valueFrom"].keys())[0] if e.get("valueFrom") else ""}
                    for e in c.get("env",[])],
            "volume_mounts": [{"name": vm.get("name",""), "mount_path": vm.get("mountPath",""),
                               "read_only": vm.get("readOnly", False)} for vm in c.get("volumeMounts",[])],
            "liveness_probe":  bool(c.get("livenessProbe")),
            "readiness_probe": bool(c.get("readinessProbe")),
        }

    conditions = [{
        "type":    cond.get("type",""),
        "status":  cond.get("status",""),
        "reason":  cond.get("reason",""),
        "message": cond.get("message",""),
        "last_transition": cond.get("lastTransitionTime",""),
    } for cond in status.get("conditions",[])]

    volumes = [{
        "name": v.get("name",""),
        "type": next((k for k in v if k != "name"), "unknown"),
    } for v in spec.get("volumes",[])]

    owner_refs = [{
        "kind": o.get("kind",""),
        "name": o.get("name",""),
        "uid":  o.get("uid",""),
    } for o in meta.get("ownerReferences",[])]

    # PVC info — resolve each PVC-backed volume to its claim details
    pvcs = []
    for v in spec.get("volumes", []):
        if "persistentVolumeClaim" in v:
            claim_name = v["persistentVolumeClaim"]["claimName"]
            read_only  = v["persistentVolumeClaim"].get("readOnly", False)
            try:
                pvc        = _api_get(cluster, f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{claim_name}")
                pvc_spec   = pvc.get("spec", {})
                pvc_status = pvc.get("status", {})
                pvcs.append({
                    "volume_name":  v.get("name", ""),
                    "claim_name":   claim_name,
                    "phase":        pvc_status.get("phase", "Unknown"),
                    "storage_class":pvc_spec.get("storageClassName", "—"),
                    "access_modes": pvc_spec.get("accessModes", []),
                    "capacity":     pvc_status.get("capacity", {}).get("storage", ""),
                    "requested":    pvc_spec.get("resources", {}).get("requests", {}).get("storage", ""),
                    "bound_volume": pvc_spec.get("volumeName", ""),
                    "volume_mode":  pvc_spec.get("volumeMode", "Filesystem"),
                    "read_only":    read_only,
                })
            except Exception:
                pvcs.append({
                    "volume_name":  v.get("name", ""),
                    "claim_name":   claim_name,
                    "phase":        "Unknown",
                    "storage_class":"—",
                    "access_modes": [],
                    "capacity":     "",
                    "requested":    "",
                    "bound_volume": "",
                    "volume_mode":  "",
                    "read_only":    read_only,
                })

    return {
        # identity
        "name":            meta.get("name",""),
        "namespace":       meta.get("namespace",""),
        "uid":             meta.get("uid",""),
        "created_at":      meta.get("creationTimestamp",""),
        "labels":          meta.get("labels",{}),
        "annotations":     {k: v for k, v in meta.get("annotations",{}).items()
                            if not k.startswith("kubectl.kubernetes.io/last-applied")},
        # runtime
        "phase":           status.get("phase","Unknown"),
        "pod_ip":          status.get("podIP",""),
        "host_ip":         status.get("hostIP",""),
        "qos_class":       status.get("qosClass",""),
        "start_time":      status.get("startTime","") or meta.get("creationTimestamp",""),
        # spec
        "node":            spec.get("nodeName",""),
        "service_account": spec.get("serviceAccountName",""),
        "restart_policy":  spec.get("restartPolicy",""),
        "dns_policy":      spec.get("dnsPolicy",""),
        "node_selector":   spec.get("nodeSelector",{}),
        "scheduler_name":  spec.get("schedulerName",""),
        "tolerations":     [{"key": t.get("key",""), "operator": t.get("operator",""),
                             "effect": t.get("effect",""), "value": t.get("value","")}
                            for t in spec.get("tolerations",[])],
        # containers
        "containers":       [_container_info(c, cs_map)  for c in spec.get("containers",[])],
        "init_containers":  [_container_info(c, ics_map) for c in spec.get("initContainers",[])],
        # conditions / volumes / pvcs / owners
        "conditions":      conditions,
        "volumes":         volumes,
        "pvcs":            pvcs,
        "owner_refs":      owner_refs,
        "ready_str":       f"{sum(1 for c in cs_map.values() if c.get('ready'))}/{len(spec.get('containers',[]))}",
    }

def get_pod_logs(cluster: dict, namespace: str, pod_name: str,
                 container: str = "", tail: int = 200) -> dict:
    """Fetch recent pod logs from each (or a specific) container."""
    token = _get_token(cluster)
    base  = cluster["api_url"].rstrip("/")

    # Discover containers from pod spec
    all_containers, all_init = [], []
    try:
        spec_data      = _api_get(cluster, f"/api/v1/namespaces/{namespace}/pods/{pod_name}")
        all_containers = [c["name"] for c in spec_data.get("spec", {}).get("containers", [])]
        all_init       = [c["name"] for c in spec_data.get("spec", {}).get("initContainers", [])]
    except Exception:
        if container:
            all_containers = [container]

    fetch_list = [container] if container else (all_containers or [""])

    logs = {}
    for c_name in fetch_list[:6]:     # cap at 6 containers
        try:
            params: dict = {"tailLines": tail}
            if c_name:
                params["container"] = c_name
            url  = f"{base}/api/v1/namespaces/{namespace}/pods/{pod_name}/log"
            resp = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                                params=params, verify=False, timeout=30)
            logs[c_name or pod_name] = resp.text if resp.status_code == 200 \
                else f"[HTTP {resp.status_code}] {resp.text[:500]}"
        except Exception as e:
            logs[c_name or pod_name] = f"[Error] {e}"

    return {
        "containers":      all_containers,
        "init_containers": all_init,
        "logs":            logs,
    }

def get_namespace_detail(cluster: dict, namespace: str) -> dict:
    """Full namespace/project detail matching OpenShift UI — includes labels, quotas, limitranges."""
    try:
        # Try OCP project first, fall back to k8s namespace
        try:
            data = _api_get(cluster, f"/apis/project.openshift.io/v1/projects/{namespace}")
        except Exception:
            data = _api_get(cluster, f"/api/v1/namespaces/{namespace}")
    except Exception as e:
        return {"error": str(e)}

    meta = data.get("metadata", {})
    anns = meta.get("annotations", {})
    labels = meta.get("labels", {})
    status_phase = data.get("status", {}).get("phase", "Active")

    # Resource quotas
    quotas = []
    try:
        qdata = _api_get(cluster, f"/api/v1/namespaces/{namespace}/resourcequotas")
        for q in qdata.get("items", []):
            qmeta = q.get("metadata", {})
            hard  = q.get("spec",   {}).get("hard", {})
            used  = q.get("status", {}).get("used", {})
            all_keys = sorted(set(list(hard.keys()) + list(used.keys())))
            quotas.append({
                "name":  qmeta.get("name",""),
                "items": [{"resource": k, "hard": hard.get(k,"—"), "used": used.get(k,"—")} for k in all_keys],
            })
    except Exception:
        pass

    # LimitRanges
    limit_ranges = []
    try:
        ldata = _api_get(cluster, f"/api/v1/namespaces/{namespace}/limitranges")
        for lr in ldata.get("items", []):
            lrmeta = lr.get("metadata", {})
            limits = []
            for lim in lr.get("spec", {}).get("limits", []):
                limits.append({
                    "type":           lim.get("type",""),
                    "default":        lim.get("default",{}),
                    "default_request":lim.get("defaultRequest",{}),
                    "max":            lim.get("max",{}),
                    "min":            lim.get("min",{}),
                })
            limit_ranges.append({"name": lrmeta.get("name",""), "limits": limits})
    except Exception:
        pass

    return {
        "name":         meta.get("name",""),
        "uid":          meta.get("uid",""),
        "created_at":   meta.get("creationTimestamp",""),
        "phase":        status_phase,
        "display_name": anns.get("openshift.io/display-name","") or meta.get("name",""),
        "description":  anns.get("openshift.io/description",""),
        "requester":    anns.get("openshift.io/requester",""),
        "sa_requester": anns.get("openshift.io/sa.scc.supplemental-groups",""),
        "node_selector":anns.get("openshift.io/node-selector",""),
        "labels":       labels,
        "annotations":  {k: v for k, v in anns.items()},
        "quotas":       quotas,
        "limit_ranges": limit_ranges,
    }

def get_namespaces(cluster: dict) -> list:
    try:
        try:
            data  = _api_get(cluster, "/apis/project.openshift.io/v1/projects")
        except Exception:
            data  = _api_get(cluster, "/api/v1/namespaces")
        items = data.get("items", [])
    except Exception:
        return []
    result = []
    for item in items:
        meta = item.get("metadata", {})
        anns = meta.get("annotations", {})
        result.append({
            "name":         meta["name"],
            "phase":        item.get("status", {}).get("phase","Active"),
            "display_name": anns.get("openshift.io/display-name", meta["name"]),
            "description":  anns.get("openshift.io/description",""),
            "requester":    anns.get("openshift.io/requester",""),
            "created_at":   meta.get("creationTimestamp",""),
        })
    return result

def get_cluster_operators(cluster: dict) -> list:
    try:
        data  = _api_get(cluster, "/apis/config.openshift.io/v1/clusteroperators")
        items = data.get("items", [])
    except Exception:
        return []
    ops = []
    for item in items:
        meta  = item.get("metadata", {})
        conds = item.get("status", {}).get("conditions", [])
        def _c(t):
            c = next((c for c in conds if c["type"]==t), {})
            return c.get("status","Unknown"), c.get("message","")
        av_s, av_m = _c("Available")
        pr_s, _    = _c("Progressing")
        dg_s, dg_m = _c("Degraded")
        if dg_s == "True":        health = "Degraded"
        elif av_s == "False":     health = "Unavailable"
        elif pr_s == "True":      health = "Progressing"
        elif av_s == "True":      health = "Available"
        else:                     health = "Unknown"
        versions = item.get("status", {}).get("versions", [])
        version  = next((v["version"] for v in versions if v["name"]=="operator"), "")
        ops.append({
            "name":        meta["name"],
            "health":      health,
            "available":   av_s,
            "progressing": pr_s,
            "degraded":    dg_s,
            "degraded_msg": dg_m,
            "version":     version,
            "created_at":  meta.get("creationTimestamp",""),
        })
    return ops

def get_events(cluster: dict, limit: int = 200) -> list:
    try:
        data  = _api_get(cluster, "/api/v1/events", params={"limit": str(limit)})
        items = data.get("items", [])
    except Exception:
        return []
    events = []
    for item in items:
        meta = item.get("metadata", {})
        obj  = item.get("involvedObject", {})
        events.append({
            "name":       meta["name"],
            "namespace":  meta.get("namespace",""),
            "type":       item.get("type","Normal"),
            "reason":     item.get("reason",""),
            "message":    item.get("message",""),
            "component":  item.get("source",{}).get("component",""),
            "host":       item.get("source",{}).get("host",""),
            "obj_kind":   obj.get("kind",""),
            "obj_name":   obj.get("name",""),
            "count":      item.get("count",1),
            "last_time":  item.get("lastTimestamp",""),
        })
    events.sort(key=lambda e: (0 if e["type"]=="Warning" else 1, e["last_time"] or ""), reverse=True)
    return events

def get_routes(cluster: dict) -> list:
    """Return all OpenShift Routes (networking.openshift.io) with URL, TLS and service info."""
    try:
        data = _api_get(cluster, "/apis/route.openshift.io/v1/routes")
    except Exception as e:
        return [{"error": str(e)}]
    items = []
    for r in data.get("items", []):
        meta   = r.get("metadata", {})
        spec   = r.get("spec", {})
        tls    = spec.get("tls", None)
        scheme = "https" if tls else "http"
        host   = spec.get("host", "")
        path   = spec.get("path", "")
        url    = f"{scheme}://{host}{path}" if host else ""
        # Admission status
        ingress_list = r.get("status", {}).get("ingress", [])
        admitted = False
        for ing in ingress_list:
            for cond in ing.get("conditions", []):
                if cond.get("type") == "Admitted" and cond.get("status") == "True":
                    admitted = True
                    break
        items.append({
            "name":        meta.get("name", ""),
            "namespace":   meta.get("namespace", ""),
            "host":        host,
            "path":        path,
            "url":         url,
            "scheme":      scheme,
            "tls":         tls.get("termination", "edge") if tls else None,
            "service":     spec.get("to", {}).get("name", ""),
            "target_port": (spec.get("port") or {}).get("targetPort", ""),
            "admitted":    admitted,
            "wildcard":    spec.get("wildcardPolicy", "None"),
            "created_at":  meta.get("creationTimestamp", ""),
        })
    items.sort(key=lambda x: (x["namespace"], x["name"]))
    return items

def get_storage_classes(cluster: dict) -> list:
    """Return all StorageClasses with provisioner, reclaim policy, binding mode and parameters."""
    try:
        data = _api_get(cluster, "/apis/storage.k8s.io/v1/storageclasses")
    except Exception as e:
        return [{"error": str(e)}]
    items = []
    for sc in data.get("items", []):
        meta  = sc.get("metadata", {})
        anns  = meta.get("annotations", {})
        items.append({
            "name":           meta.get("name", ""),
            "provisioner":    sc.get("provisioner", ""),
            "reclaim_policy": sc.get("reclaimPolicy", "Delete"),
            "binding_mode":   sc.get("volumeBindingMode", "Immediate"),
            "allow_expansion":sc.get("allowVolumeExpansion", False),
            "is_default":     (
                anns.get("storageclass.kubernetes.io/is-default-class", "").lower() == "true"
                or anns.get("storageclass.beta.kubernetes.io/is-default-class", "").lower() == "true"
            ),
            "parameters":     sc.get("parameters", {}),
            "created_at":     meta.get("creationTimestamp", ""),
        })
    items.sort(key=lambda s: (not s["is_default"], s["name"]))
    return items

def get_cluster_overview(cluster: dict) -> dict:
    result = {
        "version":            {},
        "nodes_summary":      {"total":0,"ready":0,"not_ready":0},
        "operators_summary":  {"total":0,"available":0,"degraded":0},
        "pods_summary":       {"total":0,"running":0,"failed":0,"pending":0},
        "warnings":           0,
    }
    try: result["version"] = get_cluster_version(cluster)
    except Exception: pass
    try:
        nodes = get_live_nodes(cluster)
        result["nodes_summary"] = {
            "total": len(nodes),
            "ready": sum(1 for n in nodes if n["ready"]),
            "not_ready": sum(1 for n in nodes if not n["ready"]),
        }
    except Exception: pass
    try:
        ops = get_cluster_operators(cluster)
        result["operators_summary"] = {
            "total": len(ops),
            "available": sum(1 for o in ops if o["health"]=="Available"),
            "degraded":  sum(1 for o in ops if o["health"]=="Degraded"),
        }
    except Exception: pass
    try:
        pods = get_pods(cluster)
        result["pods_summary"] = {
            "total":   len(pods),
            "running": sum(1 for p in pods if p["phase"]=="Running"),
            "failed":  sum(1 for p in pods if p["phase"]=="Failed"),
            "pending": sum(1 for p in pods if p["phase"]=="Pending"),
        }
    except Exception: pass
    try:
        evts = get_events(cluster, limit=500)
        result["warnings"] = sum(1 for e in evts if e["type"]=="Warning")
    except Exception: pass
    return result

def node_action(cluster: dict, node_name: str, action: str) -> dict:
    try:
        token   = _get_token(cluster)
        api_url = cluster["api_url"].rstrip("/")
        bearer  = {"Authorization": f"Bearer {token}"}
        patch_hdr = {**bearer, "Content-Type": "application/json-patch+json"}
        if action in ("cordon","uncordon"):
            unschedulable = (action == "cordon")
            patch = json.dumps([{"op":"replace","path":"/spec/unschedulable","value":unschedulable}])
            r = requests.patch(f"{api_url}/api/v1/nodes/{node_name}",
                               headers=patch_hdr, data=patch, verify=False, timeout=15)
            if r.status_code == 200:
                return {"success":True,"message":f"Node {node_name} {'cordoned' if unschedulable else 'uncordoned'} successfully"}
            return {"success":False,"message":r.text[:300]}
        elif action == "drain":
            patch = json.dumps([{"op":"replace","path":"/spec/unschedulable","value":True}])
            requests.patch(f"{api_url}/api/v1/nodes/{node_name}", headers=patch_hdr, data=patch, verify=False, timeout=15)
            pods_r = requests.get(f"{api_url}/api/v1/pods",
                                  headers=bearer,
                                  params={"fieldSelector": f"spec.nodeName={node_name}"},
                                  verify=False, timeout=15)
            evicted = 0
            for pod in pods_r.json().get("items", []):
                pm  = pod.get("metadata", {})
                ors = pm.get("ownerReferences", [])
                if any(o.get("kind")=="DaemonSet" for o in ors): continue
                ns  = pm.get("namespace","default")
                pnm = pm["name"]
                requests.post(f"{api_url}/api/v1/namespaces/{ns}/pods/{pnm}/eviction",
                              headers={**bearer,"Content-Type":"application/json"},
                              json={"apiVersion":"policy/v1","kind":"Eviction",
                                    "metadata":{"name":pnm,"namespace":ns}},
                              verify=False, timeout=10)
                evicted += 1
            return {"success":True,"message":f"Node cordoned, {evicted} pods evicted"}
        elif action == "describe":
            nd = requests.get(f"{api_url}/api/v1/nodes/{node_name}", headers=bearer, verify=False, timeout=15).json()
            conds = nd.get("status",{}).get("conditions",[])
            info  = nd.get("status",{}).get("nodeInfo",{})
            lines = [f"Node: {node_name}",
                     f"OS: {info.get('osImage','')}",
                     f"Kernel: {info.get('kernelVersion','')}",
                     f"Runtime: {info.get('containerRuntimeVersion','')}",
                     f"Kubelet: {info.get('kubeletVersion','')}",
                     "Conditions:"] + \
                    [f"  {c['type']}: {c['status']}  {c.get('reason','')}" for c in conds]
            return {"success":True,"message":"\n".join(lines)}
        else:
            return {"success":False,"message":f"Unknown action: {action}"}
    except Exception as e:
        return {"success":False,"message":str(e)}

def test_cluster_connection(cluster: dict) -> dict:
    try:
        _TOKEN_CACHE.pop(cluster.get("id"), None)
        token = _get_token(cluster)
        data  = _api_get(cluster, "/api/v1/nodes")
        items = data.get("items", [])
        ready = sum(1 for n in items
                    for c in n.get("status",{}).get("conditions",[])
                    if c["type"]=="Ready" and c["status"]=="True")
        return {"reachable":True,"total_nodes":len(items),"ready_nodes":ready,
                "message":f"{ready}/{len(items)} nodes Ready"}
    except Exception as e:
        return {"reachable":False,"total_nodes":0,"ready_nodes":0,"message":str(e)}


# ─── PersistentVolumes ────────────────────────────────────────────────────────

def get_persistent_volumes(cluster: dict) -> list:
    """List all PersistentVolumes cluster-wide."""
    try:
        data = _api_get(cluster, "/api/v1/persistentvolumes")
    except Exception as e:
        return [{"error": str(e)}]
    items = []
    for pv in data.get("items", []):
        meta   = pv.get("metadata", {})
        spec   = pv.get("spec", {})
        status = pv.get("status", {})
        claim  = spec.get("claimRef", {})
        capacity = spec.get("capacity", {}).get("storage", "—")
        items.append({
            "name":           meta.get("name", ""),
            "capacity":       capacity,
            "access_modes":   spec.get("accessModes", []),
            "reclaim_policy": spec.get("persistentVolumeReclaimPolicy", "—"),
            "status":         status.get("phase", "—"),
            "claim_name":     claim.get("name", ""),
            "claim_namespace":claim.get("namespace", ""),
            "storage_class":  spec.get("storageClassName", "—"),
            "volume_mode":    spec.get("volumeMode", "Filesystem"),
            "created_at":     meta.get("creationTimestamp", ""),
        })
    items.sort(key=lambda x: x["name"])
    return items


def get_persistent_volume_claims(cluster: dict) -> list:
    """List all PersistentVolumeClaims across all namespaces."""
    try:
        data = _api_get(cluster, "/api/v1/persistentvolumeclaims")
    except Exception as e:
        return [{"error": str(e)}]
    items = []
    for pvc in data.get("items", []):
        meta     = pvc.get("metadata", {})
        spec     = pvc.get("spec", {})
        status   = pvc.get("status", {})
        capacity = status.get("capacity", {}).get("storage") or \
                   spec.get("resources", {}).get("requests", {}).get("storage", "—")
        items.append({
            "name":          meta.get("name", ""),
            "namespace":     meta.get("namespace", ""),
            "status":        status.get("phase", "—"),
            "volume":        spec.get("volumeName", "—"),
            "capacity":      capacity,
            "access_modes":  spec.get("accessModes", []),
            "storage_class": spec.get("storageClassName", "—"),
            "volume_mode":   spec.get("volumeMode", "Filesystem"),
            "created_at":    meta.get("creationTimestamp", ""),
        })
    items.sort(key=lambda x: (x["namespace"], x["name"]))
    return items


def describe_persistent_volume(cluster: dict, name: str) -> dict:
    """Return full PV object for describe view."""
    try:
        return _api_get(cluster, f"/api/v1/persistentvolumes/{name}")
    except Exception as e:
        raise RuntimeError(str(e))


def describe_persistent_volume_claim(cluster: dict, namespace: str, name: str) -> dict:
    """Return full PVC object for describe view."""
    try:
        return _api_get(cluster, f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{name}")
    except Exception as e:
        raise RuntimeError(str(e))


def describe_storage_class(cluster: dict, name: str) -> dict:
    """Return full StorageClass object for describe view."""
    try:
        return _api_get(cluster, f"/apis/storage.k8s.io/v1/storageclasses/{name}")
    except Exception as e:
        raise RuntimeError(str(e))


def delete_persistent_volume(cluster: dict, name: str) -> dict:
    """Delete a PersistentVolume."""
    return _api_delete(cluster, f"/api/v1/persistentvolumes/{name}")


def delete_persistent_volume_claim(cluster: dict, namespace: str, name: str) -> dict:
    """Delete a PersistentVolumeClaim."""
    return _api_delete(cluster, f"/api/v1/namespaces/{namespace}/persistentvolumeclaims/{name}")


def delete_storage_class(cluster: dict, name: str) -> dict:
    """Delete a StorageClass."""
    return _api_delete(cluster, f"/apis/storage.k8s.io/v1/storageclasses/{name}")


def create_persistent_volume_claim(cluster: dict, namespace: str, name: str,
                                   storage: str, access_mode: str, storage_class: str,
                                   volume_mode: str = "Filesystem") -> dict:
    """Create a PVC via the Kubernetes API."""
    body = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "accessModes": [access_mode],
            "resources": {"requests": {"storage": storage}},
            "volumeMode": volume_mode,
        },
    }
    if storage_class:
        body["spec"]["storageClassName"] = storage_class
    return _api_post(cluster, f"/api/v1/namespaces/{namespace}/persistentvolumeclaims", body)


def get_storage_resource_events(cluster: dict, name: str,
                                namespace: str = None, kind: str = "PersistentVolumeClaim") -> list:
    """Fetch events related to a storage resource."""
    try:
        field = f"involvedObject.name={name},involvedObject.kind={kind}"
        if namespace:
            data = _api_get(cluster, f"/api/v1/namespaces/{namespace}/events",
                            params={"fieldSelector": field})
        else:
            data = _api_get(cluster, "/api/v1/events",
                            params={"fieldSelector": field})
        events = []
        for ev in data.get("items", []):
            events.append({
                "type":    ev.get("type", "Normal"),
                "reason":  ev.get("reason", ""),
                "message": ev.get("message", ""),
                "count":   ev.get("count", 1),
                "last_seen": ev.get("lastTimestamp") or ev.get("eventTime", ""),
                "source":  ev.get("source", {}).get("component", ""),
            })
        events.sort(key=lambda e: e["last_seen"] or "", reverse=True)
        return events
    except Exception as e:
        return [{"type": "Error", "reason": "FetchFailed", "message": str(e), "count": 1, "last_seen": "", "source": ""}]


# ── Workloads ──────────────────────────────────────────────────────────────────
_WORKLOAD_APIPATHS: dict = {
    "deployments":       "/apis/apps/v1",
    "deploymentconfigs": "/apis/apps.openshift.io/v1",
    "statefulsets":      "/apis/apps/v1",
    "daemonsets":        "/apis/apps/v1",
    "replicasets":       "/apis/apps/v1",
    "secrets":           "/api/v1",
    "configmaps":        "/api/v1",
}

_SYSTEM_NAMESPACES = frozenset([
    "kube-system", "kube-public", "kube-node-lease",
    "openshift", "openshift-infra", "openshift-node",
])


def _ns_is_system(ns: str) -> bool:
    return ns in _SYSTEM_NAMESPACES or ns.startswith("openshift-") or ns.startswith("kube-")


def _parse_workload_item(item: dict, kind: str) -> dict:
    meta   = item.get("metadata", {}) or {}
    spec   = item.get("spec", {}) or {}
    status = item.get("status", {}) or {}
    result: dict = {
        "name":      meta.get("name", ""),
        "namespace": meta.get("namespace", ""),
        "created":   meta.get("creationTimestamp", ""),
        "labels":    meta.get("labels", {}),
    }
    if kind in ("deployments", "deploymentconfigs"):
        result["replicas"]           = spec.get("replicas", 0) or 0
        result["ready_replicas"]     = status.get("readyReplicas", 0) or 0
        result["available_replicas"] = status.get("availableReplicas", 0) or 0
        result["updated_replicas"]   = status.get("updatedReplicas", 0) or 0
    elif kind == "statefulsets":
        result["replicas"]       = spec.get("replicas", 0) or 0
        result["ready_replicas"] = status.get("readyReplicas", 0) or 0
    elif kind == "daemonsets":
        result["desired"] = status.get("desiredNumberScheduled", 0) or 0
        result["ready"]   = status.get("numberReady", 0) or 0
    elif kind == "replicasets":
        result["replicas"]       = spec.get("replicas", 0) or 0
        result["ready_replicas"] = status.get("readyReplicas", 0) or 0
    elif kind == "secrets":
        result["type"]      = item.get("type", "Opaque")
        result["data_keys"] = len(item.get("data", {}) or {})
    elif kind == "configmaps":
        result["data_keys"] = len((item.get("data") or {}))
    return result


def _list_workload_kind(cluster: dict, kind: str) -> list:
    api_prefix = _WORKLOAD_APIPATHS.get(kind, "/api/v1")
    data = _api_get(cluster, f"{api_prefix}/{kind}")
    items = []
    for item in data.get("items", []):
        try:
            ns = (item.get("metadata") or {}).get("namespace", "")
            # Filter system namespaces for secrets and configmaps
            if kind in ("secrets", "configmaps") and _ns_is_system(ns):
                continue
            # Skip service account tokens
            if kind == "secrets" and item.get("type") == "kubernetes.io/service-account-token":
                continue
            items.append(_parse_workload_item(item, kind))
        except Exception:
            pass
    return items


def get_deployments(cluster: dict) -> list:
    """Return all Deployments across all namespaces."""
    try:
        return _list_workload_kind(cluster, "deployments")
    except Exception as e:
        raise RuntimeError(str(e))


def get_deployment_configs(cluster: dict) -> list:
    """Return all DeploymentConfigs across all namespaces (OpenShift-specific)."""
    try:
        return _list_workload_kind(cluster, "deploymentconfigs")
    except Exception as e:
        # DeploymentConfigs may not exist on vanilla k8s — return empty
        return []


def get_statefulsets(cluster: dict) -> list:
    """Return all StatefulSets across all namespaces."""
    try:
        return _list_workload_kind(cluster, "statefulsets")
    except Exception as e:
        raise RuntimeError(str(e))


def get_daemonsets(cluster: dict) -> list:
    """Return all DaemonSets across all namespaces."""
    try:
        return _list_workload_kind(cluster, "daemonsets")
    except Exception as e:
        raise RuntimeError(str(e))


def get_replicasets(cluster: dict) -> list:
    """Return all ReplicaSets across all namespaces."""
    try:
        return _list_workload_kind(cluster, "replicasets")
    except Exception as e:
        raise RuntimeError(str(e))


def get_secrets(cluster: dict) -> list:
    """Return Secrets excluding service-account-tokens and system namespaces."""
    try:
        return _list_workload_kind(cluster, "secrets")
    except Exception as e:
        raise RuntimeError(str(e))


def get_configmaps(cluster: dict) -> list:
    """Return ConfigMaps excluding system namespaces."""
    try:
        return _list_workload_kind(cluster, "configmaps")
    except Exception as e:
        raise RuntimeError(str(e))


def describe_workload_resource(cluster: dict, kind: str, namespace: str, name: str) -> dict:
    """Return full API object for the describe view."""
    api_prefix = _WORKLOAD_APIPATHS.get(kind)
    if not api_prefix:
        raise RuntimeError(f"Unknown workload kind: {kind}")
    path = f"{api_prefix}/namespaces/{namespace}/{kind}/{name}"
    try:
        return _api_get(cluster, path)
    except Exception as e:
        raise RuntimeError(str(e))


def delete_workload_resource(cluster: dict, kind: str, namespace: str, name: str) -> dict:
    """Delete a namespaced workload resource."""
    api_prefix = _WORKLOAD_APIPATHS.get(kind)
    if not api_prefix:
        raise RuntimeError(f"Unknown workload kind: {kind}")
    path = f"{api_prefix}/namespaces/{namespace}/{kind}/{name}"
    return _api_delete(cluster, path)


def get_workload_pod_logs(cluster: dict, kind: str, namespace: str, name: str,
                          tail: int = 100) -> dict:
    """Get logs from the first pod belonging to a workload (Deployment / StatefulSet etc.)."""
    try:
        obj       = describe_workload_resource(cluster, kind, namespace, name)
        spec      = obj.get("spec", {}) or {}
        selector  = spec.get("selector") or {}
        match_lbl = selector.get("matchLabels") or {}
        if not match_lbl:
            return {"logs": {"info": "No pod selector found for this workload."}}
        label_sel  = ",".join(f"{k}={v}" for k, v in match_lbl.items())
        pods_data  = _api_get(cluster, f"/api/v1/namespaces/{namespace}/pods",
                              params={"labelSelector": label_sel})
        pods = pods_data.get("items", [])
        if not pods:
            return {"logs": {"info": "No running pods found for this workload."}}
        # Pick most-recent pod
        pod = sorted(pods,
                     key=lambda p: (p.get("metadata") or {}).get("creationTimestamp", ""),
                     reverse=True)[0]
        pod_name   = (pod.get("metadata") or {}).get("name", "")
        containers = [c["name"] for c in (pod.get("spec") or {}).get("containers", [])]

        token = _get_token(cluster)
        base  = cluster["api_url"].rstrip("/")
        logs  = {}
        for c_name in (containers or [""])[:4]:
            try:
                params: dict = {"tailLines": tail}
                if c_name:
                    params["container"] = c_name
                url  = f"{base}/api/v1/namespaces/{namespace}/pods/{pod_name}/log"
                resp = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                                    params=params, verify=False, timeout=30)
                logs[c_name or pod_name] = resp.text if resp.status_code == 200 \
                    else f"[HTTP {resp.status_code}] {resp.text[:500]}"
            except Exception as ex:
                logs[c_name or pod_name] = f"[Error] {ex}"
        return {"pod": pod_name, "containers": containers, "logs": logs}
    except Exception as e:
        return {"logs": {"error": str(e)}}
