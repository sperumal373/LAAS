"""
veeam_client.py — Veeam Backup & Replication REST API integration
Authentication: OAuth2 password grant via /api/oauth2/token (port 9419)
Data via REST: /api/v1/*
"""
import logging, sqlite3, json, time
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("caas.veeam")
API_VER = "1.3-rev1"
TIMEOUT = 45

# ── DB ────────────────────────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(str(Path(__file__).parent / "caas.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def init_veeam_db():
    conn = _db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS veeam_connections (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            url           TEXT NOT NULL,
            port          INTEGER NOT NULL DEFAULT 9419,
            username      TEXT NOT NULL DEFAULT '',
            password      TEXT NOT NULL DEFAULT '',
            status        TEXT DEFAULT 'unknown',
            last_checked  TEXT DEFAULT '',
            created_by    TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            updated_at    TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    log.info("Veeam DB table initialized")

# ── CRUD ──────────────────────────────────────────────────────────────────────
def _safe(row):
    d = dict(row)
    d.pop("password", None)
    return d

def vm_list_connections():
    conn = _db()
    rows = conn.execute("SELECT * FROM veeam_connections ORDER BY name").fetchall()
    conn.close()
    return [_safe(r) for r in rows]

def vm_get_connection(cid: int) -> Optional[dict]:
    conn = _db()
    row = conn.execute("SELECT * FROM veeam_connections WHERE id=?", (cid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def vm_create_connection(data: dict) -> dict:
    conn = _db()
    now = _now()
    try:
        cur = conn.execute(
            """INSERT INTO veeam_connections
               (name, url, port, username, password, status, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["url"].rstrip("/"),
             data.get("port", 9419),
             data.get("username", ""), data.get("password", ""),
             "ok", data.get("created_by", "system"), now, now)
        )
        cid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return _safe(vm_get_connection(cid))

def vm_delete_connection(cid: int):
    conn = _db()
    conn.execute("DELETE FROM veeam_connections WHERE id=?", (cid,))
    conn.commit()
    conn.close()

def vm_set_status(cid: int, status: str):
    conn = _db()
    conn.execute("UPDATE veeam_connections SET status=?, last_checked=? WHERE id=?",
                 (status, _now(), cid))
    conn.commit()
    conn.close()

# ── Veeam API helpers ────────────────────────────────────────────────────────
_token_cache: dict = {}
TOKEN_TTL = 3500

def _base(url: str, port: int = 9419) -> str:
    u = url if url.startswith("http") else f"https://{url}"
    u = u.rstrip("/")
    if f":{port}" not in u:
        u = f"{u}:{port}"
    return u

def _get_token(url: str, port: int, username: str, password: str) -> str:
    base = _base(url, port)
    cache_key = f"{base}|{username}"
    cached = _token_cache.get(cache_key)
    if cached and time.time() < cached["exp"]:
        return cached["token"]
    resp = requests.post(
        f"{base}/api/oauth2/token",
        data={"grant_type": "password", "username": username, "password": password},
        headers={"x-api-version": API_VER},
        verify=False, timeout=30
    )
    if resp.status_code not in (200, 201):
        raise ValueError(f"Veeam auth failed HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    token = f"{data['token_type']} {data['access_token']}"
    _token_cache[cache_key] = {"token": token, "exp": time.time() + TOKEN_TTL}
    return token

def _hdr(token: str) -> dict:
    return {"Authorization": token, "x-api-version": API_VER, "Content-Type": "application/json", "Accept": "application/json"}

def _vget(url: str, token: str, path: str, params=None):
    base = url  # already fully formed
    r = requests.get(f"{base}/api/v1/{path}",
                     headers=_hdr(token), params=params, verify=False, timeout=TIMEOUT)
    if r.status_code in (404, 400, 500):
        return None
    r.raise_for_status()
    return r.json()

def _vpost(url: str, token: str, path: str, body=None):
    base = url
    r = requests.post(f"{base}/api/v1/{path}",
                      headers=_hdr(token), json=body, verify=False, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json() if r.text else {}

def _vdelete(url: str, token: str, path: str):
    base = url
    r = requests.delete(f"{base}/api/v1/{path}",
                        headers=_hdr(token), verify=False, timeout=TIMEOUT)
    r.raise_for_status()
    return {}

def _vput(url: str, token: str, path: str, body=None):
    base = url
    r = requests.put(f"{base}/api/v1/{path}",
                     headers=_hdr(token), json=body, verify=False, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json() if r.text else {}

def _vpatch(url: str, token: str, path: str, body=None):
    base = url
    r = requests.patch(f"{base}/api/v1/{path}",
                       headers=_hdr(token), json=body, verify=False, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json() if r.text else {}

def _creds(conn_row):
    base = _base(conn_row["url"], conn_row.get("port", 9419))
    token = _get_token(conn_row["url"], conn_row.get("port", 9419),
                       conn_row["username"], conn_row["password"])
    return base, token

def _list_data(resp):
    """Extract list from Veeam paginated response."""
    if resp is None:
        return []
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        return resp.get("data", [])
    return []

# ── Test connection ───────────────────────────────────────────────────────────
def vm_test_connection(data: dict) -> dict:
    url = data.get("url", "").strip().rstrip("/")
    port = data.get("port", 9419)
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not url or not username or not password:
        return {"ok": False, "message": "URL, username and password required"}
    try:
        base = _base(url, port)
        token = _get_token(url, port, username, password)
        info = _vget(base, token, "serverInfo")
        name = info.get("name", "?") if info else "?"
        ver = info.get("buildVersion", "") if info else ""
        return {"ok": True, "message": f"Connected to {name} (v{ver})"}
    except Exception as e:
        return {"ok": False, "message": str(e)}

# ── Fetch all data ────────────────────────────────────────────────────────────
def get_veeam_data(conn_row: dict) -> dict:
    base, token = _creds(conn_row)

    # 1. Server info
    info = _vget(base, token, "serverInfo") or {}

    # 2. Jobs
    all_jobs_raw = _list_data(_vget(base, token, "jobs"))
    jobs = []
    active_count = 0
    disabled_count = 0
    for j in all_jobs_raw:
        is_dis = j.get("isDisabled", False)
        if is_dis:
            disabled_count += 1
        else:
            active_count += 1
        vms = j.get("virtualMachines", {}).get("includes", [])
        jobs.append({
            "id": j.get("id"),
            "name": j.get("name"),
            "type": j.get("type"),
            "is_disabled": is_dis,
            "description": j.get("description", ""),
            "vm_count": len(vms),
            "vms": [{"name": v.get("name"), "platform": v.get("platform"), "size": v.get("size")} for v in vms[:20]],
        })

    # 3. Sessions (latest 50)
    sessions_raw = _list_data(_vget(base, token, "sessions", {"limit": 50}))
    sessions = []
    ok_count = 0
    fail_count = 0
    warning_count = 0
    running_count = 0
    for s in sessions_raw:
        res = s.get("result", {}) or {}
        result_str = res.get("result", "Unknown")
        if result_str == "Success":
            ok_count += 1
        elif result_str in ("Failed", "Error"):
            fail_count += 1
        elif result_str == "Warning":
            warning_count += 1
        if s.get("state") == "Working":
            running_count += 1
        sessions.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "type": s.get("sessionType"),
            "state": s.get("state"),
            "result": result_str,
            "message": res.get("message", ""),
            "progress": s.get("progressPercent"),
            "start": s.get("creationTime"),
            "end": s.get("endTime"),
        })

    # 4. Repositories with states
    repos_raw = _list_data(_vget(base, token, "backupInfrastructure/repositories/states"))
    repos = []
    total_cap = 0
    total_used = 0
    total_free = 0
    for rp in repos_raw:
        cap = rp.get("capacityGB", -1)
        used = rp.get("usedSpaceGB", 0)
        free = rp.get("freeGB", -1)
        if cap > 0:
            total_cap += cap
        if used > 0:
            total_used += used
        if free > 0:
            total_free += free
        repos.append({
            "id": rp.get("id"),
            "name": rp.get("name"),
            "type": rp.get("type"),
            "host": rp.get("hostName"),
            "path": rp.get("path"),
            "capacity_gb": cap,
            "used_gb": used,
            "free_gb": free,
            "description": rp.get("description", ""),
        })

    # 5. Managed Servers
    servers_raw = _list_data(_vget(base, token, "backupInfrastructure/managedServers"))
    servers = [{"id": m.get("id"), "name": m.get("name"), "type": m.get("type"), "description": m.get("description", "")}
               for m in servers_raw]

    # 6. Proxies
    proxies_raw = _list_data(_vget(base, token, "backupInfrastructure/proxies"))
    proxies = [{"id": p.get("id"), "name": p.get("name"), "type": p.get("type"),
                "max_tasks": p.get("server", {}).get("maxTaskCount", 0)}
               for p in proxies_raw]

    # 7. Backup objects
    objects_raw = _list_data(_vget(base, token, "backupObjects", {"limit": 200}))
    backup_objects = [{"name": o.get("name"), "type": o.get("type"),
                       "platform": o.get("platformName"), "job_id": o.get("jobId")}
                      for o in objects_raw]

    # 8. Credentials count
    creds_raw = _list_data(_vget(base, token, "credentials"))

    # Build summary
    summary = {
        "server_name": info.get("name", "?"),
        "version": info.get("buildVersion", ""),
        "db_vendor": info.get("databaseVendor", ""),
        "total_jobs": len(jobs),
        "active_jobs": active_count,
        "disabled_jobs": disabled_count,
        "sessions_ok": ok_count,
        "sessions_fail": fail_count,
        "sessions_warning": warning_count,
        "sessions_running": running_count,
        "repos_count": len(repos),
        "total_capacity_gb": round(total_cap, 1),
        "total_used_gb": round(total_used, 1),
        "total_free_gb": round(total_free, 1),
        "managed_servers": len(servers),
        "proxies_count": len(proxies),
        "backup_objects": len(backup_objects),
        "credentials_count": len(creds_raw),
    }

    return {
        "summary": summary,
        "jobs": jobs,
        "sessions": sessions,
        "repositories": repos,
        "managed_servers": servers,
        "proxies": proxies,
        "backup_objects": backup_objects,
    }

# ── Management Operations ────────────────────────────────────────────────────

def vm_start_job(conn_row, job_id):
    """Start (run) a backup job."""
    base, token = _creds(conn_row)
    return _vpost(base, token, f"jobs/{job_id}/start", {})

def vm_stop_job(conn_row, job_id):
    """Stop a running backup job."""
    base, token = _creds(conn_row)
    return _vpost(base, token, f"jobs/{job_id}/stop", {})

def vm_enable_job(conn_row, job_id):
    """Enable a disabled job."""
    base, token = _creds(conn_row)
    job = _vget(base, token, f"jobs/{job_id}")
    if not job:
        raise ValueError(f"Job {job_id} not found")
    job["isDisabled"] = False
    return _vput(base, token, f"jobs/{job_id}", job)

def vm_disable_job(conn_row, job_id):
    """Disable a job."""
    base, token = _creds(conn_row)
    job = _vget(base, token, f"jobs/{job_id}")
    if not job:
        raise ValueError(f"Job {job_id} not found")
    job["isDisabled"] = True
    return _vput(base, token, f"jobs/{job_id}", job)

def vm_delete_job(conn_row, job_id):
    """Delete a backup job."""
    base, token = _creds(conn_row)
    return _vdelete(base, token, f"jobs/{job_id}")

def vm_get_job_sessions(conn_row, job_id, limit=20):
    """Get sessions for a specific job."""
    base, token = _creds(conn_row)
    raw = _list_data(_vget(base, token, f"sessions", {"jobId": job_id, "limit": limit}))
    return [{"id": s.get("id"), "name": s.get("name"), "type": s.get("sessionType"),
             "state": s.get("state"), "result": (s.get("result") or {}).get("result", "?"),
             "message": (s.get("result") or {}).get("message", ""),
             "progress": s.get("progressPercent"),
             "start": s.get("creationTime"), "end": s.get("endTime")} for s in raw]

def vm_retry_session(conn_row, session_id):
    """Retry a failed session."""
    base, token = _creds(conn_row)
    return _vpost(base, token, f"sessions/{session_id}/retry", {})

def vm_stop_session(conn_row, session_id):
    """Stop a running session."""
    base, token = _creds(conn_row)
    return _vpost(base, token, f"sessions/{session_id}/stop", {})

def vm_instant_recovery(conn_row, body):
    """Start instant VM recovery."""
    base, token = _creds(conn_row)
    return _vpost(base, token, "restore/instantRecovery/", body)

def vm_search_objects(conn_row, query):
    """Search backup objects by name."""
    base, token = _creds(conn_row)
    raw = _list_data(_vget(base, token, "backupObjects", {"limit": 200, "nameFilter": query}))
    return [{"name": o.get("name"), "type": o.get("type"),
             "platform": o.get("platformName"), "job_id": o.get("jobId")}
            for o in raw]
