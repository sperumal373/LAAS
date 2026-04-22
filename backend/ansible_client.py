"""
ansible_client.py — Ansible Automation Platform (AAP) integration
Live data via AAP REST API v2.
Auth: username + password (Basic Auth)
"""
import logging
from pathlib import Path
from datetime import datetime
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("caas.ansible")

# ── DB helpers ─────────────────────────────────────────────────────────────────
def _get_db():
    import sqlite3
    db_path = Path(__file__).parent / "caas.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def init_aap_db():
    conn = _get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS aap_instances (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            url         TEXT NOT NULL,
            username    TEXT DEFAULT '',
            password    TEXT DEFAULT '',
            env         TEXT DEFAULT 'PROD',
            description TEXT DEFAULT '',
            status      TEXT DEFAULT 'unknown',
            created_by  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    log.info("AAP DB tables initialized")

# ── CRUD ───────────────────────────────────────────────────────────────────────
def _safe(d):
    d2 = dict(d)
    d2.pop("password", None)
    return d2

def list_aap_instances() -> list:
    conn = _get_db()
    rows = conn.execute("SELECT * FROM aap_instances ORDER BY env, name").fetchall()
    conn.close()
    return [_safe(dict(r)) for r in rows]

def get_aap_instance(inst_id: int) -> dict | None:
    conn = _get_db()
    row = conn.execute("SELECT * FROM aap_instances WHERE id=?", (inst_id,)).fetchone()
    conn.close()
    return dict(row) if row else None  # includes password for internal use

def create_aap_instance(name: str, url: str, username: str, password: str,
                        env: str, description: str, created_by: str) -> dict:
    conn = _get_db()
    now = _now()
    url = url.rstrip("/")
    try:
        conn.execute("""
            INSERT INTO aap_instances
              (name, url, username, password, env, description, status, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'unknown', ?, ?, ?)
        """, (name, url, username, password, env, description, created_by, now, now))
        conn.commit()
        row = conn.execute("SELECT * FROM aap_instances WHERE name=?", (name,)).fetchone()
        return _safe(dict(row))
    finally:
        conn.close()

def update_aap_instance(inst_id: int, **kwargs) -> dict | None:
    conn = _get_db()
    now = _now()
    allowed = {"name", "url", "username", "password", "env", "description"}
    if "url" in kwargs:
        kwargs["url"] = kwargs["url"].rstrip("/")
    sets = [f"{k}=?" for k in kwargs if k in allowed]
    vals = [v for k, v in kwargs.items() if k in allowed]
    if not sets:
        conn.close()
        return None
    conn.execute(f"UPDATE aap_instances SET {', '.join(sets)}, updated_at=? WHERE id=?",
                 [*vals, now, inst_id])
    conn.commit()
    row = conn.execute("SELECT * FROM aap_instances WHERE id=?", (inst_id,)).fetchone()
    conn.close()
    return _safe(dict(row)) if row else None

def delete_aap_instance(inst_id: int):
    conn = _get_db()
    conn.execute("DELETE FROM aap_instances WHERE id=?", (inst_id,))
    conn.commit()
    conn.close()

# ── HTTP helpers ───────────────────────────────────────────────────────────────
def _auth(inst: dict):
    return (inst["username"], inst["password"])

def _get(inst: dict, path: str, params: dict = None) -> dict:
    url = inst["url"].rstrip("/") + path
    r = requests.get(url, auth=_auth(inst), params=params or {},
                     verify=False, timeout=30)
    r.raise_for_status()
    return r.json()

def _post(inst: dict, path: str, body: dict = None) -> dict:
    url = inst["url"].rstrip("/") + path
    r = requests.post(url, auth=_auth(inst), json=body or {},
                      verify=False, timeout=30)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        raise RuntimeError(r.text[:500])
    try:
        return r.json()
    except Exception:
        return {"status": "ok"}

def _patch(inst: dict, path: str, body: dict) -> dict:
    url = inst["url"].rstrip("/") + path
    r = requests.patch(url, auth=_auth(inst), json=body,
                       verify=False, timeout=30)
    r.raise_for_status()
    return r.json()

def _delete_req(inst: dict, path: str) -> dict:
    url = inst["url"].rstrip("/") + path
    r = requests.delete(url, auth=_auth(inst), verify=False, timeout=30)
    try:
        r.raise_for_status()
    except requests.HTTPError:
        raise RuntimeError(r.text[:500])
    try:
        return r.json()
    except Exception:
        return {"status": "deleted"}

def _paginate(inst: dict, path: str, params: dict = None, max_items: int = 500) -> list:
    items = []
    url_path = path
    p = {**(params or {}), "page_size": 100}
    while url_path and len(items) < max_items:
        try:
            data = _get(inst, url_path, p)
        except Exception:
            break
        items.extend(data.get("results", []))
        nxt = data.get("next")
        if nxt:
            from urllib.parse import urlparse
            parsed = urlparse(nxt)
            url_path = parsed.path + ("?" + parsed.query if parsed.query else "")
            p = {}
        else:
            break
    return items

# ── Connection test ────────────────────────────────────────────────────────────
def test_aap_connection(inst: dict) -> dict:
    try:
        data = _get(inst, "/api/v2/config/")
        version = data.get("version", "unknown")
        conn = _get_db()
        conn.execute("UPDATE aap_instances SET status='ok', updated_at=? WHERE id=?",
                     (_now(), inst["id"]))
        conn.commit()
        conn.close()
        return {"reachable": True, "version": version, "message": f"Connected — AAP {version}"}
    except Exception as e:
        conn = _get_db()
        conn.execute("UPDATE aap_instances SET status='error', updated_at=? WHERE id=?",
                     (_now(), inst["id"]))
        conn.commit()
        conn.close()
        return {"reachable": False, "version": "", "message": str(e)}

# ── Dashboard overview ─────────────────────────────────────────────────────────
def get_aap_dashboard(inst: dict) -> dict:
    try:
        data = _get(inst, "/api/v2/dashboard/")
        return {
            "jobs_total":             (data.get("jobs") or {}).get("total", 0),
            "jobs_failed":            (data.get("jobs") or {}).get("failed", 0),
            "jobs_succeeded":         (data.get("jobs") or {}).get("successful", 0),
            "hosts_total":            (data.get("hosts") or {}).get("total", 0),
            "hosts_failed":           (data.get("hosts") or {}).get("failed", 0),
            "inventories_total":      (data.get("inventories") or {}).get("total", 0),
            "inventories_failed":     (data.get("inventories") or {}).get("inventory_failed", 0),
            "projects_total":         (data.get("projects") or {}).get("total", 0),
            "projects_failed":        (data.get("projects") or {}).get("failed", 0),
            "templates_total":        (data.get("job_templates") or {}).get("total", 0),
            "schedules_enabled":      0,
        }
    except Exception as e:
        return {"error": str(e)}

# ── Live data ──────────────────────────────────────────────────────────────────
def get_aap_jobs(inst: dict, limit: int = 100) -> list:
    try:
        items = _paginate(inst, "/api/v2/jobs/",
                          {"order_by": "-started", "page_size": min(limit, 100)},
                          max_items=limit)
        sf = lambda j, k: (j.get("summary_fields", {}).get(k) or {})
        return [{
            "id":            j.get("id"),
            "name":          j.get("name", ""),
            "status":        j.get("status", ""),
            "started":       j.get("started", ""),
            "finished":      j.get("finished", ""),
            "elapsed":       round(j.get("elapsed", 0), 1),
            "launched_by":   sf(j, "launched_by").get("name", ""),
            "job_template":  sf(j, "job_template").get("name", ""),
            "inventory":     sf(j, "inventory").get("name", ""),
            "project":       sf(j, "project").get("name", ""),
            "failed":        j.get("failed", False),
        } for j in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_aap_job_templates(inst: dict, search=None) -> list:
    try:
        params = {"search": search} if search else None
        items = _paginate(inst, "/api/v2/job_templates/", params=params, max_items=10000)
        sf = lambda j, k: (j.get("summary_fields", {}).get(k) or {})
        return [{
            "id":              j.get("id"),
            "name":            j.get("name", ""),
            "description":     j.get("description", ""),
            "playbook":        j.get("playbook", ""),
            "last_job_run":    j.get("last_job_run", ""),
            "last_job_failed": j.get("last_job_failed", False),
            "inventory":       sf(j, "inventory").get("name", ""),
            "project":         sf(j, "project").get("name", ""),
            "created":         j.get("created", ""),
        } for j in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_aap_inventories(inst: dict) -> list:
    try:
        items = _paginate(inst, "/api/v2/inventories/")
        sf = lambda i, k: (i.get("summary_fields", {}).get(k) or {})
        return [{
            "id":                    i.get("id"),
            "name":                  i.get("name", ""),
            "description":           i.get("description", ""),
            "kind":                  i.get("kind", ""),
            "hosts_total":           i.get("total_hosts", 0),
            "hosts_failed":          i.get("hosts_with_active_failures", 0),
            "groups_total":          i.get("total_groups", 0),
            "has_active_failures":   i.get("has_active_failures", False),
            "organization":          sf(i, "organization").get("name", ""),
            "created":               i.get("created", ""),
        } for i in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_aap_projects(inst: dict) -> list:
    try:
        items = _paginate(inst, "/api/v2/projects/")
        sf = lambda p, k: (p.get("summary_fields", {}).get(k) or {})
        return [{
            "id":               p.get("id"),
            "name":             p.get("name", ""),
            "description":      p.get("description", ""),
            "status":           p.get("status", ""),
            "scm_type":         p.get("scm_type", ""),
            "scm_url":          p.get("scm_url", ""),
            "scm_branch":       p.get("scm_branch", ""),
            "last_updated":     p.get("last_updated", ""),
            "last_update_failed": p.get("last_update_failed", False),
            "organization":     sf(p, "organization").get("name", ""),
            "created":          p.get("created", ""),
        } for p in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_aap_hosts(inst: dict, limit: int = 300) -> list:
    try:
        items = _paginate(inst, "/api/v2/hosts/", max_items=limit)
        sf = lambda h, k: (h.get("summary_fields", {}).get(k) or {})
        return [{
            "id":        h.get("id"),
            "name":      h.get("name", ""),
            "enabled":   h.get("enabled", True),
            "inventory": sf(h, "inventory").get("name", ""),
            "last_job":  sf(h, "last_job").get("status", ""),
            "last_failed": (sf(h, "last_job_host_summary")).get("failed", False),
            "created":   h.get("created", ""),
        } for h in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_aap_credentials(inst: dict) -> list:
    try:
        items = _paginate(inst, "/api/v2/credentials/")
        sf = lambda c, k: (c.get("summary_fields", {}).get(k) or {})
        return [{
            "id":           c.get("id"),
            "name":         c.get("name", ""),
            "description":  c.get("description", ""),
            "kind":         sf(c, "credential_type").get("name", c.get("kind", "")),
            "organization": sf(c, "organization").get("name", ""),
            "created":      c.get("created", ""),
        } for c in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_aap_organizations(inst: dict) -> list:
    try:
        items = _paginate(inst, "/api/v2/organizations/")
        return [{
            "id":          o.get("id"),
            "name":        o.get("name", ""),
            "description": o.get("description", ""),
            "created":     o.get("created", ""),
        } for o in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_aap_users(inst: dict) -> list:
    try:
        items = _paginate(inst, "/api/v2/users/")
        return [{
            "id":           u.get("id"),
            "username":     u.get("username", ""),
            "first_name":   u.get("first_name", ""),
            "last_name":    u.get("last_name", ""),
            "email":        u.get("email", ""),
            "is_superuser": u.get("is_superuser", False),
            "is_system_auditor": u.get("is_system_auditor", False),
            "last_login":   u.get("last_login", ""),
            "created":      u.get("created", ""),
        } for u in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_aap_teams(inst: dict) -> list:
    try:
        items = _paginate(inst, "/api/v2/teams/")
        sf = lambda t, k: (t.get("summary_fields", {}).get(k) or {})
        return [{
            "id":           t.get("id"),
            "name":         t.get("name", ""),
            "description":  t.get("description", ""),
            "organization": sf(t, "organization").get("name", ""),
            "created":      t.get("created", ""),
        } for t in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_aap_schedules(inst: dict) -> list:
    try:
        items = _paginate(inst, "/api/v2/schedules/")
        sf = lambda s, k: (s.get("summary_fields", {}).get(k) or {})
        return [{
            "id":       s.get("id"),
            "name":     s.get("name", ""),
            "enabled":  s.get("enabled", True),
            "rrule":    s.get("rrule", ""),
            "timezone": s.get("timezone", ""),
            "next_run": s.get("next_run", ""),
            "template": sf(s, "unified_job_template").get("name", ""),
            "created":  s.get("created", ""),
        } for s in items]
    except Exception as e:
        raise RuntimeError(str(e))

def get_job_output(inst: dict, job_id: int) -> str:
    try:
        url = inst["url"].rstrip("/") + f"/api/v2/jobs/{job_id}/stdout/"
        r = requests.get(url, auth=_auth(inst), params={"format": "txt"},
                         verify=False, timeout=60)
        return r.text[:60000]
    except Exception as e:
        return f"[Error] {e}"

# ── Actions ────────────────────────────────────────────────────────────────────
def launch_job_template(inst: dict, template_id: int, extra_vars: str = "") -> dict:
    body = {}
    if extra_vars:
        body["extra_vars"] = extra_vars
    return _post(inst, f"/api/v2/job_templates/{template_id}/launch/", body)

def cancel_job(inst: dict, job_id: int) -> dict:
    return _post(inst, f"/api/v2/jobs/{job_id}/cancel/")

def delete_job(inst: dict, job_id: int) -> dict:
    return _delete_req(inst, f"/api/v2/jobs/{job_id}/")

def sync_inventory(inst: dict, inventory_id: int) -> dict:
    return _post(inst, f"/api/v2/inventories/{inventory_id}/update_inventory_sources/")

def sync_project(inst: dict, project_id: int) -> dict:
    return _post(inst, f"/api/v2/projects/{project_id}/update/")

def toggle_host(inst: dict, host_id: int, enabled: bool) -> dict:
    return _patch(inst, f"/api/v2/hosts/{host_id}/", {"enabled": enabled})

def delete_host(inst: dict, host_id: int) -> dict:
    return _delete_req(inst, f"/api/v2/hosts/{host_id}/")

def toggle_schedule(inst: dict, schedule_id: int, enabled: bool) -> dict:
    return _patch(inst, f"/api/v2/schedules/{schedule_id}/", {"enabled": enabled})

def delete_schedule(inst: dict, schedule_id: int) -> dict:
    return _delete_req(inst, f"/api/v2/schedules/{schedule_id}/")

def create_aap_user(inst: dict, username: str, password: str,
                    first_name: str = "", last_name: str = "",
                    email: str = "", is_superuser: bool = False) -> dict:
    return _post(inst, "/api/v2/users/", {
        "username": username, "password": password,
        "first_name": first_name, "last_name": last_name,
        "email": email, "is_superuser": is_superuser,
    })

def delete_aap_user(inst: dict, user_id: int) -> dict:
    return _delete_req(inst, f"/api/v2/users/{user_id}/")

def delete_credential(inst: dict, cred_id: int) -> dict:
    return _delete_req(inst, f"/api/v2/credentials/{cred_id}/")

def delete_job_template(inst: dict, template_id: int) -> dict:
    return _delete_req(inst, f"/api/v2/job_templates/{template_id}/")

def delete_inventory(inst: dict, inventory_id: int) -> dict:
    return _delete_req(inst, f"/api/v2/inventories/{inventory_id}/")

def delete_project(inst: dict, project_id: int) -> dict:
    return _delete_req(inst, f"/api/v2/projects/{project_id}/")

# ── Create / Update resources ──────────────────────────────────────────────────
def create_job_template(inst: dict, body: dict) -> dict:
    return _post(inst, "/api/v2/job_templates/", body)

def update_job_template(inst: dict, template_id: int, body: dict) -> dict:
    return _patch(inst, f"/api/v2/job_templates/{template_id}/", body)

def create_inventory(inst: dict, body: dict) -> dict:
    return _post(inst, "/api/v2/inventories/", body)

def update_inventory(inst: dict, inventory_id: int, body: dict) -> dict:
    return _patch(inst, f"/api/v2/inventories/{inventory_id}/", body)

def create_project(inst: dict, body: dict) -> dict:
    return _post(inst, "/api/v2/projects/", body)

def update_project(inst: dict, project_id: int, body: dict) -> dict:
    return _patch(inst, f"/api/v2/projects/{project_id}/", body)

def create_credential(inst: dict, body: dict) -> dict:
    return _post(inst, "/api/v2/credentials/", body)

def update_credential(inst: dict, cred_id: int, body: dict) -> dict:
    return _patch(inst, f"/api/v2/credentials/{cred_id}/", body)

# ── Workflow Job Templates ─────────────────────────────────────────────────────
def get_aap_workflows(inst: dict) -> list:
    return _paginate(inst, "/api/v2/workflow_job_templates/")

def launch_workflow_template(inst: dict, wf_id: int) -> dict:
    return _post(inst, f"/api/v2/workflow_job_templates/{wf_id}/launch/", {})

def create_workflow(inst: dict, body: dict) -> dict:
    return _post(inst, "/api/v2/workflow_job_templates/", body)

def update_workflow(inst: dict, wf_id: int, body: dict) -> dict:
    return _patch(inst, f"/api/v2/workflow_job_templates/{wf_id}/", body)

def delete_workflow(inst: dict, wf_id: int) -> dict:
    return _delete_req(inst, f"/api/v2/workflow_job_templates/{wf_id}/")

# ── Execution Environments ─────────────────────────────────────────────────────
def get_execution_environments(inst: dict) -> list:
    """Fetch all Execution Environments from AAP."""
    try:
        items = _paginate(inst, "/api/v2/execution_environments/")
        return [{
            "id":                 ee.get("id"),
            "name":               ee.get("name", ""),
            "image":              ee.get("image", ""),
            "managed":            ee.get("managed", False),
            "description":        ee.get("description", ""),
        } for ee in items]
    except Exception:
        return []   # EEs may not exist in all AAP versions

# ── Project Local Paths (for Manual SCM type) ─────────────────────────────────
def get_project_local_paths(inst: dict) -> list:
    """Return available local_path directory names for Manual SCM projects.

    AAP's OPTIONS /api/v2/projects/ exposes choices in
    actions -> POST -> local_path -> choices.
    Falls back to scanning existing manual projects.
    """
    try:
        url = inst["url"].rstrip("/") + "/api/v2/projects/"
        r = requests.options(url, auth=_auth(inst), verify=False, timeout=20)
        if r.status_code == 200:
            data = r.json()
            choices = (data.get("actions", {}).get("POST", {})
                           .get("local_path", {}).get("choices", []))
            if choices:
                return [c[0] if isinstance(c, (list, tuple)) else c for c in choices]
    except Exception:
        pass
    # Fallback: collect local_path from existing manual projects
    try:
        items = _paginate(inst, "/api/v2/projects/", params={"scm_type": ""})
        paths = [p.get("local_path", "") for p in items if p.get("local_path")]
        return sorted(set(paths))
    except Exception:
        return []
