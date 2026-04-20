"""
cohesity_client.py — Cohesity DataProtect integration
Authentication: username + password → Bearer token via /irisservices/api/v1/public/accessTokens
Data via REST: /irisservices/api/v1/public/* and /v2/*
"""
import logging, sqlite3, json, time
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("caas.cohesity")

# ── DB ────────────────────────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(str(Path(__file__).parent / "caas.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def init_cohesity_db():
    conn = _db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cohesity_connections (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            url           TEXT NOT NULL,
            username      TEXT NOT NULL DEFAULT '',
            password      TEXT NOT NULL DEFAULT '',
            domain        TEXT NOT NULL DEFAULT 'LOCAL',
            status        TEXT DEFAULT 'unknown',
            last_checked  TEXT DEFAULT '',
            created_by    TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    log.info("Cohesity DB table initialized")

# ── CRUD ──────────────────────────────────────────────────────────────────────
def _safe(row):
    d = dict(row)
    d.pop("password", None)
    return d

def ch_list_connections():
    conn = _db()
    rows = conn.execute("SELECT * FROM cohesity_connections ORDER BY name").fetchall()
    conn.close()
    return [_safe(r) for r in rows]

def ch_get_connection(cid: int) -> Optional[dict]:
    conn = _db()
    row = conn.execute("SELECT * FROM cohesity_connections WHERE id=?", (cid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def ch_create_connection(data: dict) -> dict:
    conn = _db()
    now = _now()
    try:
        cur = conn.execute(
            """INSERT INTO cohesity_connections
               (name, url, username, password, domain, status, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["url"].rstrip("/"),
             data.get("username", ""), data.get("password", ""),
             data.get("domain", "LOCAL"),
             "ok", data.get("created_by", "system"), now, now)
        )
        cid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return _safe(ch_get_connection(cid))

def ch_delete_connection(cid: int):
    conn = _db()
    conn.execute("DELETE FROM cohesity_connections WHERE id=?", (cid,))
    conn.commit()
    conn.close()

def ch_set_status(cid: int, status: str):
    conn = _db()
    conn.execute("UPDATE cohesity_connections SET status=?, last_checked=? WHERE id=?",
                 (status, _now(), cid))
    conn.commit()
    conn.close()

# ── Cohesity API helpers ─────────────────────────────────────────────────────
_token_cache: dict = {}   # url -> {token, exp}
TOKEN_TTL = 3600

def _base(url: str) -> str:
    return f"https://{url}" if not url.startswith("http") else url

def _get_token(url: str, username: str, password: str, domain: str = "LOCAL") -> str:
    base = _base(url)
    cache_key = f"{base}|{username}"
    cached = _token_cache.get(cache_key)
    if cached and time.time() < cached["exp"]:
        return cached["token"]
    resp = requests.post(
        f"{base}/irisservices/api/v1/public/accessTokens",
        json={"domain": domain, "username": username, "password": password},
        verify=False, timeout=15
    )
    if resp.status_code not in (200, 201):
        raise ValueError(f"Cohesity auth failed HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    token = f"{data['tokenType']} {data['accessToken']}"
    _token_cache[cache_key] = {"token": token, "exp": time.time() + TOKEN_TTL}
    return token

def _hdr(token: str) -> dict:
    return {"Authorization": token, "Content-Type": "application/json"}

def _v1(url: str, token: str, path: str, params=None):
    base = _base(url)
    r = requests.get(f"{base}/irisservices/api/v1/public/{path}",
                     headers=_hdr(token), params=params, verify=False, timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def _v2(url: str, token: str, path: str, params=None):
    base = _base(url)
    r = requests.get(f"{base}/v2/{path}",
                     headers=_hdr(token), params=params, verify=False, timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()

def _v1_post(url: str, token: str, path: str, body=None):
    base = _base(url)
    r = requests.post(f"{base}/irisservices/api/v1/public/{path}",
                      headers=_hdr(token), json=body, verify=False, timeout=30)
    r.raise_for_status()
    return r.json() if r.text else {}

def _v1_put(url: str, token: str, path: str, body=None):
    base = _base(url)
    r = requests.put(f"{base}/irisservices/api/v1/public/{path}",
                     headers=_hdr(token), json=body, verify=False, timeout=30)
    r.raise_for_status()
    return r.json() if r.text else {}

def _v1_delete(url: str, token: str, path: str):
    base = _base(url)
    r = requests.delete(f"{base}/irisservices/api/v1/public/{path}",
                        headers=_hdr(token), verify=False, timeout=30)
    r.raise_for_status()
    return {}

def _v2_post(url: str, token: str, path: str, body=None):
    base = _base(url)
    r = requests.post(f"{base}/v2/{path}",
                      headers=_hdr(token), json=body, verify=False, timeout=30)
    r.raise_for_status()
    return r.json() if r.text else {}

def _creds(conn_row):
    return conn_row["url"], _get_token(conn_row["url"], conn_row["username"],
                                        conn_row["password"], conn_row.get("domain","LOCAL"))

# ── Test connection ───────────────────────────────────────────────────────────
def ch_test_connection(data: dict) -> dict:
    url = data.get("url","").strip().rstrip("/")
    username = data.get("username","").strip()
    password = data.get("password","")
    domain = data.get("domain","LOCAL")
    if not url or not username or not password:
        return {"ok": False, "message": "URL, username and password required"}
    try:
        token = _get_token(url, username, password, domain)
        cluster = _v1(url, token, "cluster")
        name = cluster.get("name","?") if cluster else "?"
        return {"ok": True, "message": f"Connected to {name} ({cluster.get('clusterSoftwareVersion','')})"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

# ── Fetch all data ────────────────────────────────────────────────────────────
def _usecs_to_iso(usecs):
    if not usecs: return None
    try: return datetime.utcfromtimestamp(usecs / 1_000_000).strftime("%Y-%m-%dT%H:%M:%SZ")
    except: return None

def _status_str(s):
    m = {"kSuccess":"Success","kFailure":"Failed","kRunning":"Running",
         "kAccepted":"Queued","kCanceled":"Canceled","kWarning":"Warning",
         "kSuccessWithWarning":"SuccessWithWarning"}
    return m.get(s, (s or "").replace("k","") if s else "Unknown")

def get_cohesity_data(conn_row: dict) -> dict:
    url, token = _creds(conn_row)

    # 1. Cluster
    cluster = _v1(url, token, "cluster") or {}

    # 2. Protection jobs
    all_jobs = _v1(url, token, "protectionJobs") or []
    active_jobs = [j for j in all_jobs if not j.get("isDeleted")]
    paused_jobs = [j for j in active_jobs if j.get("isPaused")]
    running_jobs_list = [j for j in active_jobs if not j.get("isPaused")]

    # 3. Protection runs (latest 100)
    runs = _v1(url, token, "protectionRuns", {"numRuns": 100, "excludeTasks": True}) or []
    ok_count = sum(1 for rn in runs if rn.get("backupRun",{}).get("status") == "kSuccess")
    fail_count = sum(1 for rn in runs if rn.get("backupRun",{}).get("status") == "kFailure")
    running_count = sum(1 for rn in runs if rn.get("backupRun",{}).get("status") in ("kRunning","kAccepted"))

    recent_runs = []
    for rn in runs[:50]:
        br = rn.get("backupRun",{})
        stats = br.get("stats",{})
        recent_runs.append({
            "job_name": rn.get("jobName","?"),
            "job_id": rn.get("jobId"),
            "status": _status_str(br.get("status")),
            "run_type": (br.get("runType","") or "").replace("k",""),
            "start": _usecs_to_iso(stats.get("startTimeUsecs")),
            "end": _usecs_to_iso(stats.get("endTimeUsecs")),
            "data_read": stats.get("totalBytesReadFromSource",0),
            "data_written": stats.get("totalPhysicalBackupSizeBytes",0),
            "logical_size": stats.get("totalLogicalBackupSizeBytes",0),
        })

    # 4. Protection policies
    policies = _v1(url, token, "protectionPolicies") or []
    policy_list = [{"id": p.get("id"), "name": p.get("name")} for p in policies]

    # 5. Sources / registration info
    reg_info = _v1(url, token, "protectionSources/registrationInfo") or {}
    roots = reg_info.get("rootNodes", [])
    sources = []
    total_protected = 0
    total_unprotected = 0
    for rn in roots:
        src = rn.get("rootNode",{})
        st = rn.get("stats",{})
        prot = st.get("protectedCount",0)
        unprot = st.get("unprotectedCount",0)
        total_protected += prot
        total_unprotected += unprot
        sources.append({
            "id": src.get("id"),
            "name": src.get("name","?"),
            "environment": (src.get("environment","") or "").replace("k",""),
            "protected": prot,
            "unprotected": unprot,
        })

    # 6. Alerts
    alerts_raw = _v1(url, token, "alerts", {"maxAlerts": 100, "alertStateList": ["kOpen"]}) or []
    critical = sum(1 for a in alerts_raw if a.get("severity") == "kCritical")
    warning = sum(1 for a in alerts_raw if a.get("severity") == "kWarning")
    alerts = []
    for a in alerts_raw[:50]:
        doc = a.get("alertDocument",{}) or {}
        alerts.append({
            "id": a.get("id"),
            "severity": (a.get("severity","") or "").replace("k",""),
            "category": (a.get("alertCategory","") or "").replace("k",""),
            "state": (a.get("alertState","") or "").replace("k",""),
            "name": doc.get("alertName",""),
            "description": doc.get("alertDescription",""),
            "cause": doc.get("alertCause",""),
            "time": _usecs_to_iso(a.get("latestTimestampUsecs") or a.get("firstTimestampUsecs")),
        })

    # 7. Storage domains (viewBoxes)
    vboxes = _v1(url, token, "viewBoxes") or []
    storage_domains = [{"id":v.get("id"),"name":v.get("name")} for v in vboxes]

    # 8. Views (NAS shares)
    views_data = _v1(url, token, "views") or {}
    views_list = views_data.get("views",[]) if isinstance(views_data, dict) else views_data
    views = [{"name":v.get("name"),"logical_bytes":v.get("logicalUsageBytes",0),
              "protocol":v.get("protocolAccess",""),"storage_domain":v.get("viewBoxName","")}
             for v in views_list[:50]]

    # 9. V2 protection groups
    v2_groups = _v2(url, token, "data-protect/protection-groups", {"isDeleted": False, "isActive": True})
    pg_list = (v2_groups or {}).get("protectionGroups", []) if v2_groups else []
    protection_groups = []
    for g in pg_list:
        if g.get("isDeleted"):
            continue
        protection_groups.append({
            "id": g.get("id"),
            "name": g.get("name"),
            "environment": (g.get("environment","") or "").replace("k",""),
            "policy_id": g.get("policyId",""),
            "is_paused": g.get("isPaused", False),
            "num_objects": g.get("numProtectedObjects"),
        })

    # 10. V2 recoveries
    v2_rec = _v2(url, token, "data-protect/recoveries", {"count": 20})
    rec_list = (v2_rec or {}).get("recoveries", []) if v2_rec else []
    recoveries = []
    for rc in rec_list[:20]:
        recoveries.append({
            "id": rc.get("id"),
            "name": rc.get("name",""),
            "status": rc.get("status",""),
            "environment": (rc.get("snapshotEnvironment","") or "").replace("k",""),
            "start": rc.get("startTimeUsecs"),
            "end": rc.get("endTimeUsecs"),
        })

    # 11. V2 search objects to get protected/unprotected objects
    v2_search = _v2(url, token, "data-protect/search/objects", {"searchString": "*"})
    search_objects = (v2_search or {}).get("objects", []) if v2_search else []

    # 12. Nodes
    nodes_raw = _v1(url, token, "nodes") or []
    nodes = [{"id":n.get("id"),"ip":n.get("ip"),"slot":n.get("slotNumber")} for n in nodes_raw]

    # Build summary
    env_counts = {}
    for j in active_jobs:
        e = (j.get("environment","") or "").replace("k","")
        env_counts[e] = env_counts.get(e,0) + 1

    summary = {
        "cluster_name": cluster.get("name","?"),
        "cluster_version": cluster.get("clusterSoftwareVersion",""),
        "cluster_type": (cluster.get("clusterType","") or "").replace("k",""),
        "node_count": cluster.get("nodeCount",0),
        "total_jobs": len(active_jobs),
        "paused_jobs": len(paused_jobs),
        "runs_ok": ok_count,
        "runs_fail": fail_count,
        "runs_running": running_count,
        "total_policies": len(policies),
        "sources_count": len(sources),
        "protected_objects": total_protected,
        "unprotected_objects": total_unprotected,
        "alerts_critical": critical,
        "alerts_warning": warning,
        "alerts_total": len(alerts_raw),
        "storage_domains": len(vboxes),
        "views_count": len(views),
        "recoveries_count": len(rec_list),
        "env_counts": env_counts,
        "metadata_used_pct": cluster.get("usedMetadataSpacePct", 0),
    }

    return {
        "summary": summary,
        "protection_groups": protection_groups,
        "recent_runs": recent_runs,
        "policies": policy_list,
        "sources": sources,
        "alerts": alerts,
        "storage_domains": storage_domains,
        "views": views,
        "recoveries": recoveries,
        "nodes": nodes,
        "search_objects": search_objects[:500],
    }

# ── Management Operations ────────────────────────────────────────────────────

def ch_run_job(conn_row, job_id, run_type="kRegular"):
    """Run a protection job on demand."""
    url, token = _creds(conn_row)
    body = {"copyRunTargets": [], "runType": run_type}
    return _v1_post(url, token, f"protectionJobs/run/{job_id}", body)

def ch_cancel_job_run(conn_row, job_id, run_id):
    """Cancel a running job."""
    url, token = _creds(conn_row)
    body = {"jobRunId": run_id}
    return _v1_post(url, token, f"protectionRuns/cancel/{job_id}", body)

def ch_pause_job(conn_row, job_id, pause=True):
    """Pause or resume a protection job."""
    url, token = _creds(conn_row)
    body = {"jobIds": [job_id], "action": "kPause" if pause else "kResume"}
    return _v1_post(url, token, "protectionJobState", body)

def ch_delete_job(conn_row, job_id, delete_snapshots=False):
    """Delete a protection job."""
    url, token = _creds(conn_row)
    base = _base(url)
    params = {}
    if delete_snapshots:
        params["deleteSnapshots"] = "true"
    r = requests.delete(f"{base}/irisservices/api/v1/public/protectionJobs/{job_id}",
                        headers=_hdr(token), params=params, verify=False, timeout=30)
    r.raise_for_status()
    return {"ok": True, "message": f"Job {job_id} deleted"}

def ch_update_job(conn_row, job_id, updates):
    """Update a protection job (policy, schedule, sources, etc.)."""
    url, token = _creds(conn_row)
    # First get the current job
    job = _v1(url, token, f"protectionJobs/{job_id}")
    if not job:
        raise ValueError(f"Job {job_id} not found")
    job.update(updates)
    return _v1_put(url, token, f"protectionJobs/{job_id}", job)

def ch_create_job(conn_row, body):
    """Create a new protection job."""
    url, token = _creds(conn_row)
    return _v1_post(url, token, "protectionJobs", body)

def ch_resolve_alert(conn_row, alert_id):
    """Resolve an alert."""
    url, token = _creds(conn_row)
    base = _base(url)
    body = {"alertIdList": [alert_id], "status": "kResolved"}
    r = requests.patch(f"{base}/irisservices/api/v1/public/alerts",
                       headers=_hdr(token), json=body, verify=False, timeout=15)
    r.raise_for_status()
    return {"ok": True, "message": "Alert resolved"}

def ch_get_job_runs(conn_row, job_id, num_runs=20):
    """Get runs for a specific job."""
    url, token = _creds(conn_row)
    runs = _v1(url, token, "protectionRuns", {"jobId": job_id, "numRuns": num_runs, "excludeTasks": False}) or []
    result = []
    for rn in runs:
        br = rn.get("backupRun",{})
        stats = br.get("stats",{})
        sources_status = []
        for sb in br.get("sourceBackupStatus", []):
            src = sb.get("source",{})
            sources_status.append({
                "name": src.get("name","?"),
                "environment": (src.get("environment","") or "").replace("k",""),
                "status": _status_str(sb.get("status")),
            })
        result.append({
            "run_id": br.get("jobRunId"),
            "status": _status_str(br.get("status")),
            "run_type": (br.get("runType","") or "").replace("k",""),
            "start": _usecs_to_iso(stats.get("startTimeUsecs")),
            "end": _usecs_to_iso(stats.get("endTimeUsecs")),
            "data_read": stats.get("totalBytesReadFromSource",0),
            "data_written": stats.get("totalPhysicalBackupSizeBytes",0),
            "sources": sources_status,
        })
    return result

def ch_recover_vm(conn_row, body):
    """Recover (restore) a VM - V2 API."""
    url, token = _creds(conn_row)
    return _v2_post(url, token, "data-protect/recoveries", body)

def ch_search_objects(conn_row, query, environments=None):
    """Search objects by name."""
    url, token = _creds(conn_row)
    params = {"searchString": query}
    if environments:
        params["environments"] = environments
    result = _v2(url, token, "data-protect/search/objects", params) or {}
    objects = result.get("objects", [])
    return [{"name": o.get("name",""), "environment": (o.get("environment","") or "").replace("k",""),
             "id": o.get("id"), "sourceId": o.get("sourceId"),
             "objectType": (o.get("objectType","") or "").replace("k",""),
             "protectionGroupId": o.get("objectProtectionInfos",[{}])[0].get("protectionGroupId") if o.get("objectProtectionInfos") else None}
            for o in objects[:200]]

def ch_get_object_snapshots(conn_row, object_id):
    """Get snapshots for a protected object."""
    url, token = _creds(conn_row)
    result = _v2(url, token, f"data-protect/objects/{object_id}/snapshots") or {}
    snaps = result.get("snapshots", [])
    return [{"id": s.get("id"), "run_id": s.get("runInstanceId"),
             "timestamp": s.get("snapshotTimestampUsecs"),
             "date": _usecs_to_iso(s.get("snapshotTimestampUsecs")),
             "type": (s.get("runType","") or "").replace("k",""),
             "status": s.get("status",""),
             "expiry": _usecs_to_iso(s.get("expiryTimeUsecs"))}
            for s in snaps[:100]]

def ch_assign_policy(conn_row, job_id, policy_id):
    """Change the policy assigned to a protection job."""
    url, token = _creds(conn_row)
    job = _v1(url, token, f"protectionJobs/{job_id}")
    if not job:
        raise ValueError(f"Job {job_id} not found")
    job["policyId"] = policy_id
    return _v1_put(url, token, f"protectionJobs/{job_id}", job)

def ch_get_sources_tree(conn_row, env=None):
    """Get protection sources tree for a given environment."""
    url, token = _creds(conn_row)
    params = {}
    if env:
        params["environments"] = [env]
    return _v1(url, token, "protectionSources", params) or []
