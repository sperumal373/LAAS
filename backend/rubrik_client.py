"""
rubrik_client.py — Rubrik Security Cloud (RSC / Polaris) integration
Authentication: Service Account client_id + client_secret → Bearer token via /api/client_token
Data via GraphQL: /api/graphql
"""
import logging, sqlite3, json, time
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("caas.rubrik")

# ── DB ────────────────────────────────────────────────────────────────────────
def _db():
    conn = sqlite3.connect(str(Path(__file__).parent / "caas.db"), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def init_rubrik_db():
    conn = _db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rubrik_connections (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            url           TEXT NOT NULL,
            client_id     TEXT NOT NULL DEFAULT '',
            client_secret TEXT NOT NULL DEFAULT '',
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
    # Migrate: add client_id / client_secret columns if missing
    try:
        conn.execute("ALTER TABLE rubrik_connections ADD COLUMN client_id TEXT NOT NULL DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE rubrik_connections ADD COLUMN client_secret TEXT NOT NULL DEFAULT ''")
        conn.commit()
    except Exception:
        pass
    conn.close()
    log.info("Rubrik DB table initialized")

# ── CRUD ──────────────────────────────────────────────────────────────────────
def _safe(row):
    d = dict(row)
    d.pop("password", None)
    d.pop("client_secret", None)
    return d

def list_connections():
    conn = _db()
    rows = conn.execute("SELECT * FROM rubrik_connections ORDER BY name").fetchall()
    conn.close()
    return [_safe(r) for r in rows]

def get_connection(cid: int) -> Optional[dict]:
    conn = _db()
    row = conn.execute("SELECT * FROM rubrik_connections WHERE id=?", (cid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_connection(data: dict) -> dict:
    conn = _db()
    now = _now()
    try:
        cur = conn.execute(
            """INSERT INTO rubrik_connections
               (name, url, client_id, client_secret, username, password, status, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (data["name"], data["url"].rstrip("/"),
             data.get("client_id", ""), data.get("client_secret", ""),
             data.get("username", ""), data.get("password", ""),
             "ok", data.get("created_by", "system"), now, now)
        )
        cid = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return _safe(get_connection(cid))

def delete_connection(cid: int):
    conn = _db()
    conn.execute("DELETE FROM rubrik_connections WHERE id=?", (cid,))
    conn.commit()
    conn.close()

def _set_status(cid: int, status: str):
    conn = _db()
    conn.execute("UPDATE rubrik_connections SET status=?, last_checked=? WHERE id=?",
                 (status, _now(), cid))
    conn.commit()
    conn.close()

# ── RSC API helpers ───────────────────────────────────────────────────────────
_token_cache: dict = {}   # url -> {token, exp}
TOKEN_TTL = 3600          # refresh token every hour

def _get_token_sa(url: str, client_id: str, client_secret: str) -> str:
    """Authenticate via Rubrik RSC Service Account (client_id + client_secret)."""
    cache_key = f"{url}|sa|{client_id}"
    cached = _token_cache.get(cache_key)
    if cached and time.time() < cached["exp"]:
        return cached["token"]
    resp = requests.post(
        f"{url}/api/client_token",
        json={"client_id": client_id, "client_secret": client_secret,
              "grant_type": "client_credentials"},
        headers={"Content-Type": "application/json"},
        verify=False, timeout=15
    )
    if resp.status_code not in (200, 201):
        raise ValueError(f"RSC service-account auth failed HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    token = data.get("access_token") or data.get("token") or data.get("sessionToken")
    if not token:
        raise ValueError(f"No token in RSC response: {list(data.keys())}")
    _token_cache[cache_key] = {"token": token, "exp": time.time() + TOKEN_TTL}
    return token

def _get_token_user(url: str, username: str, password: str) -> str:
    """Legacy: authenticate via username + password (session API)."""
    cache_key = f"{url}|user|{username}"
    cached = _token_cache.get(cache_key)
    if cached and time.time() < cached["exp"]:
        return cached["token"]
    resp = requests.post(
        f"{url}/api/session",
        json={"username": username, "password": password},
        headers={"Content-Type": "application/json"},
        verify=False, timeout=15
    )
    if resp.status_code not in (200, 201):
        raise ValueError(f"RSC auth failed HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    token = data.get("token") or data.get("access_token") or data.get("sessionToken")
    if not token:
        raise ValueError(f"No token in RSC response: {list(data.keys())}")
    _token_cache[cache_key] = {"token": token, "exp": time.time() + TOKEN_TTL}
    return token

def _get_token(url: str, client_id: str = "", client_secret: str = "",
               username: str = "", password: str = "") -> str:
    """Pick the right auth method: service account first, fallback to user/pass."""
    if client_id and client_secret:
        return _get_token_sa(url, client_id, client_secret)
    if username and password:
        return _get_token_user(url, username, password)
    raise ValueError("No credentials provided — supply client_id/client_secret or username/password")

def _gql(url: str, token: str, query: str, variables: dict = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(
        f"{url}/api/graphql",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        verify=False, timeout=30
    )
    if resp.status_code != 200:
        raise ValueError(f"GraphQL HTTP {resp.status_code}: {resp.text[:300]}")
    result = resp.json()
    if "errors" in result:
        errs = "; ".join(e.get("message","?") for e in result["errors"])
        log.warning("GraphQL errors: %s", errs)
    return result.get("data", {})

# ── Test connection ────────────────────────────────────────────────────────────
def test_connection(data: dict) -> dict:
    url           = data["url"].rstrip("/")
    client_id     = data.get("client_id", "")
    client_secret = data.get("client_secret", "")
    username      = data.get("username", "")
    password      = data.get("password", "")
    try:
        token = _get_token(url, client_id=client_id, client_secret=client_secret,
                           username=username, password=password)
        # Token obtained — auth succeeded.  Try a lightweight GQL probe.
        label = client_id or username
        try:
            gdata = _gql(url, token, "query CurrentUserQuery { currentUser { email name } }")
            user  = gdata.get("currentUser", {})
            label = user.get('email') or user.get('name') or label
        except Exception:
            pass   # auth worked; GQL schema may differ — still OK
        return {
            "ok": True,
            "message": f"Connected as {label}",
        }
    except Exception as e:
        return {"ok": False, "message": str(e)}

# ── Fetch live data ────────────────────────────────────────────────────────────
_UNPROTECTED_SLAS = {"UNPROTECTED", "DO_NOT_PROTECT", "INHERIT", "N/A", ""}

def get_rubrik_data(conn_row: dict) -> dict:
    url           = conn_row["url"].rstrip("/")
    client_id     = conn_row.get("client_id", "")
    client_secret = conn_row.get("client_secret", "")
    username      = conn_row.get("username", "")
    password      = conn_row.get("password", "")

    token = _get_token(url, client_id=client_id, client_secret=client_secret,
                       username=username, password=password)

    result = {
        "sla_domains": [],
        "protected_vms": [],
        "unprotected_vms": [],
        "recent_jobs": [],
        "events": [],
        "clusters": [],
        "summary": {}
    }

    # ── 1. SLA Domains ────────────────────────────────────────────────────────
    try:
        q_sla = """
        query SlaDomains {
          slaDomains(first: 200, filter: []) {
            edges {
              node { id name }
            }
          }
        }
        """
        d = _gql(url, token, q_sla)
        for edge in (d.get("slaDomains", {}).get("edges") or []):
            n = edge.get("node", {})
            sla_name = n.get("name", "")
            if sla_name in _UNPROTECTED_SLAS:
                continue   # skip placeholder SLAs
            result["sla_domains"].append({
                "id":              n.get("id", ""),
                "name":            sla_name,
                "object_types":    [],
                "protected_count": 0,
                "frequency":       "",
                "retention":       "",
                "replication":     False,
                "archival":        False,
            })
    except Exception as e:
        log.warning("SLA domain fetch error: %s", e)

    # ── 2. vSphere VMs (classify protected vs unprotected by SLA) ───────────────
    try:
        # Paginated query — fetches ALL VMs via cursor pagination
        _VM_PAGE = 500
        cursor = None
        vm_total_count = 0
        while True:
            after_clause = ', after: "{}"'.format(cursor) if cursor else ""
            q_vms = """
            query AllVMs {{
              vSphereVmNewConnection(
                filter: [{{field: IS_RELIC, texts: ["false"]}}]
                first: {page}{after}
              ) {{
                count
                pageInfo {{ endCursor hasNextPage }}
                edges {{
                  node {{
                    id
                    name
                    powerStatus
                    effectiveSlaDomain {{ name id }}
                    newestSnapshot {{ date }}
                    oldestSnapshot {{ date }}
                    cluster {{ name }}
                  }}
                }}
              }}
            }}
            """.format(page=_VM_PAGE, after=after_clause)
            d = _gql(url, token, q_vms)
            conn_data = d.get("vSphereVmNewConnection") or {}
            if vm_total_count == 0:
                vm_total_count = conn_data.get("count", 0)
            for edge in (conn_data.get("edges") or []):
                n = edge.get("node", {})
                ns = n.get("newestSnapshot") or {}
                os_ = n.get("oldestSnapshot") or {}
                sla = n.get("effectiveSlaDomain") or {}
                sla_name = sla.get("name", "")
                vm_rec = {
                    "id":             n.get("id", ""),
                    "name":           n.get("name", ""),
                    "power":          n.get("powerStatus", ""),
                    "sla_name":       sla_name,
                    "sla_assignment": "Protected" if sla_name not in _UNPROTECTED_SLAS else "Unprotected",
                    "last_backup":    ns.get("date", ""),
                    "oldest_backup":  os_.get("date", ""),
                    "cluster":        (n.get("cluster") or {}).get("name", ""),
                }
                if sla_name not in _UNPROTECTED_SLAS:
                    result["protected_vms"].append(vm_rec)
                else:
                    result["unprotected_vms"].append(vm_rec)
            # Check for next page
            page_info = conn_data.get("pageInfo") or {}
            if page_info.get("hasNextPage") and page_info.get("endCursor"):
                cursor = page_info["endCursor"]
            else:
                break
        log.info("Rubrik VMs: fetched %d (protected=%d, unprotected=%d, api_count=%d)",
                 len(result["protected_vms"]) + len(result["unprotected_vms"]),
                 len(result["protected_vms"]), len(result["unprotected_vms"]), vm_total_count)
        result["summary"]["protected_count"]   = len(result["protected_vms"])
        result["summary"]["unprotected_count"] = len(result["unprotected_vms"])
        result["summary"]["vm_total_count"]    = vm_total_count
        # Enrich SLA domains with per-SLA VM counts
        sla_counts = {}
        for vm in result["protected_vms"]:
            sn = vm.get("sla_name", "")
            sla_counts[sn] = sla_counts.get(sn, 0) + 1
        for sla in result["sla_domains"]:
            sla["protected_count"] = sla_counts.get(sla["name"], 0)
    except Exception as e:
        log.warning("vSphere VMs fetch error: %s", e)

    # Also get snappable-level counts (all object types, not just vSphere)
    try:
        q_snap_prot = """
        query ProtectedSnappables {
          snappableConnection(first: 0, filter: { protectionStatus: [Protected] }) { count }
        }
        """
        q_snap_unprot = """
        query UnprotectedSnappables {
          snappableConnection(first: 0, filter: { protectionStatus: [NoSla] }) { count }
        }
        """
        dp = _gql(url, token, q_snap_prot)
        du = _gql(url, token, q_snap_unprot)
        result["summary"]["snappable_protected"]   = (dp.get("snappableConnection") or {}).get("count", 0)
        result["summary"]["snappable_unprotected"]  = (du.get("snappableConnection") or {}).get("count", 0)
    except Exception as e:
        log.warning("Snappable count fetch error: %s", e)

    # ── 3. Recent backup jobs ─────────────────────────────────────────────────
    try:
        q_jobs = """
        query RecentJobs {
          activitySeriesConnection(
            first: 100
            sortOrder: DESC
            sortBy: START_TIME
            filters: { lastActivityType: [BACKUP] }
          ) {
            edges {
              node {
                activitySeriesId
                objectName
                objectType
                startTime
                lastUpdated
                lastActivityStatus
                lastActivityType
                clusterName
                progress
              }
            }
          }
        }
        """
        d = _gql(url, token, q_jobs)
        for edge in (d.get("activitySeriesConnection", {}).get("edges") or []):
            n = edge.get("node", {})
            result["recent_jobs"].append({
                "id":          n.get("activitySeriesId", ""),
                "object_name": n.get("objectName", ""),
                "type":        n.get("lastActivityType", ""),
                "status":      n.get("lastActivityStatus", ""),
                "start":       n.get("startTime", ""),
                "end":         n.get("lastUpdated", ""),
                "sla":         "",
                "cluster":     n.get("clusterName", ""),
                "progress":    n.get("progress"),
            })
    except Exception as e:
        log.warning("Recent jobs fetch error: %s", e)

    # ── 4. Events / Activity ──────────────────────────────────────────────────
    try:
        q_events = """
        query Events {
          activitySeriesConnection(
            first: 50
            sortOrder: DESC
            sortBy: START_TIME
          ) {
            edges {
              node {
                activitySeriesId
                objectName
                objectType
                startTime
                lastActivityType
                lastActivityStatus
                clusterName
              }
            }
          }
        }
        """
        d = _gql(url, token, q_events)
        for edge in (d.get("activitySeriesConnection", {}).get("edges") or []):
            n = edge.get("node", {})
            result["events"].append({
                "id":      n.get("activitySeriesId", ""),
                "object":  n.get("objectName", ""),
                "type":    n.get("objectType", ""),
                "time":    n.get("startTime", ""),
                "action":  n.get("lastActivityType", ""),
                "status":  n.get("lastActivityStatus", ""),
                "cluster": n.get("clusterName", ""),
            })
    except Exception as e:
        log.warning("Events fetch error: %s", e)

    # ── 5. Clusters via clusterConnection ─────────────────────────────────────
    try:
        q_clusters = """
        query Clusters {
          clusterConnection(first: 50) {
            edges {
              node {
                id
                name
                status
                systemStatus
                version
                productType
                type
                metric {
                  usedCapacity
                  availableCapacity
                  totalCapacity
                }
              }
            }
          }
        }
        """
        d = _gql(url, token, q_clusters)
        for edge in (d.get("clusterConnection", {}).get("edges") or []):
            c = edge.get("node", {})
            m = c.get("metric") or {}
            result["clusters"].append({
                "id":         c.get("id", ""),
                "name":       c.get("name", ""),
                "status":     c.get("status", ""),
                "version":    c.get("version", ""),
                "product":    c.get("productType", ""),
                "used_bytes": m.get("usedCapacity", 0),
                "free_bytes": m.get("availableCapacity", 0),
                "total_bytes":m.get("totalCapacity", 0),
            })
    except Exception as e:
        log.warning("Cluster capacity fetch error: %s", e)

    # ── Summary ───────────────────────────────────────────────────────────────
    jobs_ok   = sum(1 for j in result["recent_jobs"] if (j["status"] or "").lower() in ("success","succeeded"))
    jobs_fail = sum(1 for j in result["recent_jobs"] if (j["status"] or "").lower() in ("failed","failure"))
    jobs_run  = sum(1 for j in result["recent_jobs"] if (j["status"] or "").lower() in ("running","queued","in_progress","inprogress"))
    total_used  = sum(c.get("used_bytes", 0) or 0 for c in result["clusters"])
    total_cap   = sum(c.get("total_bytes", 0) or 0 for c in result["clusters"])
    result["summary"].update({
        "sla_count":         len(result["sla_domains"]),
        "protected_count":   max(result["summary"].get("protected_count", 0), result["summary"].get("snappable_protected", 0), len(result["protected_vms"])),
        "unprotected_count": max(result["summary"].get("unprotected_count", 0), result["summary"].get("snappable_unprotected", 0), len(result["unprotected_vms"])),
        "job_count":         len(result["recent_jobs"]),
        "jobs_ok":           jobs_ok,
        "jobs_fail":         jobs_fail,
        "jobs_running":      jobs_run,
        "cluster_count":     len(result["clusters"]),
        "used_bytes":        total_used,
        "total_bytes":       total_cap,
        "used_pct":          round(total_used / total_cap * 100, 1) if total_cap else 0,
    })

    return result


# ══════════════════════════════════════════════════════════════════════════════
# MANAGEMENT OPERATIONS  (admin / operator only)
# ══════════════════════════════════════════════════════════════════════════════

def _mutate(url: str, token: str, query: str, variables: dict = None) -> dict:
    """Run a GraphQL mutation and return the top-level data dict."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(
        f"{url}/api/graphql", json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        verify=False, timeout=60,
    )
    body = resp.json()
    if resp.status_code not in (200, 201):
        msg = body.get("message", "") or body.get("detail", "") or str(body)[:300]
        raise ValueError(f"Mutation HTTP {resp.status_code}: {msg}")
    if "errors" in body:
        errs = "; ".join(e.get("message", "?") for e in body["errors"])
        raise ValueError(f"GraphQL error: {errs}")
    return body.get("data", {})


def _creds(conn_row: dict):
    """Return (url, token) tuple from a connection row."""
    url = conn_row["url"].rstrip("/")
    token = _get_token(
        url,
        client_id=conn_row.get("client_id", ""),
        client_secret=conn_row.get("client_secret", ""),
        username=conn_row.get("username", ""),
        password=conn_row.get("password", ""),
    )
    return url, token


# ── 1. On-Demand Snapshot ─────────────────────────────────────────────────────
def on_demand_snapshot(conn_row: dict, vm_id: str, sla_id: str = None) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation VsphereOnDemandSnapshot($input: VsphereOnDemandSnapshotInput!) {
      vsphereOnDemandSnapshot(input: $input) {
        status { id }
      }
    }
    """
    config = {}
    if sla_id:
        config["slaId"] = sla_id
    variables = {"input": {"id": vm_id, "config": config, "userNote": "LaaS on-demand snapshot"}}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": "On-demand snapshot triggered", "data": d}


def bulk_on_demand_snapshot(conn_row: dict, vm_ids: list, sla_id: str = None) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation BulkSnapshot($input: VsphereBulkOnDemandSnapshotInput!) {
      vsphereBulkOnDemandSnapshot(input: $input) {
        statuses { id }
      }
    }
    """
    config = {"vms": vm_ids}
    if sla_id:
        config["slaId"] = sla_id
    variables = {"input": {"config": config, "userNote": "LaaS bulk snapshot"}}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": f"Bulk snapshot triggered for {len(vm_ids)} VM(s)", "data": d}


# ── 2. Assign / Change SLA Domain ────────────────────────────────────────────
def assign_sla(conn_row: dict, object_ids: list, sla_id: str) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation AssignSla($input: AssignSlaInput!) {
      assignSla(input: $input) {
        success
      }
    }
    """
    variables = {"input": {
        "slaDomainAssignType": "protectWithSlaId",
        "slaOptionalId": sla_id,
        "objectIds": object_ids,
        "shouldApplyToExistingSnapshots": False,
        "shouldApplyToNonPolicySnapshots": False,
    }}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": f"SLA assigned to {len(object_ids)} object(s)", "data": d}


def unassign_sla(conn_row: dict, object_ids: list) -> dict:
    """Remove SLA protection (do-not-protect)."""
    url, token = _creds(conn_row)
    mutation = """
    mutation AssignSla($input: AssignSlaInput!) {
      assignSla(input: $input) {
        success
      }
    }
    """
    variables = {"input": {
        "slaDomainAssignType": "doNotProtect",
        "objectIds": object_ids,
        "shouldApplyToExistingSnapshots": False,
        "shouldApplyToNonPolicySnapshots": False,
    }}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": f"SLA removed from {len(object_ids)} object(s)", "data": d}


# ── 3. Live Mount ────────────────────────────────────────────────────────────
def live_mount(conn_row: dict, snapshot_id: str, host_id: str = None,
               power_on: bool = True) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation LiveMount($input: VsphereVmInitiateLiveMountV2Input!) {
      vsphereVmInitiateLiveMountV2(input: $input) {
        status { id }
      }
    }
    """
    config = {}
    if host_id:
        config["hostId"] = host_id
    config["mountExportSnapshotJobCommonOptionsV2"] = {"powerOn": power_on}
    variables = {"input": {"id": snapshot_id, "config": config}}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": "Live Mount initiated", "data": d}


# ── 4. Export VM ──────────────────────────────────────────────────────────────
def export_vm(conn_row: dict, snapshot_id: str, host_id: str,
              datastore_id: str = None, vm_name: str = None,
              power_on: bool = False) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation ExportVm($input: VsphereVmExportSnapshotV3Input!) {
      vsphereVmExportSnapshotV3(input: $input) {
        status { id }
      }
    }
    """
    config = {
        "hostId": host_id,
        "shouldRecoverTags": True,
        "mountExportSnapshotJobCommonOptionsV2": {"powerOn": power_on},
    }
    if datastore_id:
        config["datastoreId"] = datastore_id
    if vm_name:
        config["vmName"] = vm_name
    variables = {"input": {"id": snapshot_id, "config": config}}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": f"VM export initiated ({vm_name or 'default'})", "data": d}


# ── 5. Instant Recovery ──────────────────────────────────────────────────────
def instant_recovery(conn_row: dict, snapshot_id: str,
                     host_id: str = None, preserve_moid: bool = True) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation InstantRecover($input: VsphereVmInitiateInstantRecoveryV2Input!) {
      vsphereVmInitiateInstantRecoveryV2(input: $input) {
        status { id }
      }
    }
    """
    config = {"preserveMoid": preserve_moid, "shouldRecoverTags": True}
    if host_id:
        config["hostId"] = host_id
    variables = {"input": {"id": snapshot_id, "config": config}}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": "Instant recovery initiated", "data": d}


# ── 6. File Recovery ─────────────────────────────────────────────────────────
def file_recovery(conn_row: dict, snapshot_id: str, paths: list) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation FileRecover($input: VsphereVmRecoverFilesNewInput!) {
      vsphereVmRecoverFilesNew(input: $input) {
        taskchainId
      }
    }
    """
    variables = {"input": {"snapshotFid": snapshot_id, "restoreConfig": {
        "restoreFilesConfig": [{"path": p, "restorePath": ""} for p in paths],
        "shouldUseAgent": True,
    }}}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": f"File recovery initiated for {len(paths)} path(s)", "data": d}


# ── 7. Download Snapshot Files ───────────────────────────────────────────────
def download_snapshot_files(conn_row: dict, snapshot_id: str, paths: list) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation DownloadFiles($input: VsphereVmDownloadSnapshotFilesInput!) {
      vsphereVmDownloadSnapshotFiles(input: $input) {
        taskchainId
      }
    }
    """
    variables = {"input": {"snapshotFid": snapshot_id, "paths": paths}}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": "File download initiated", "data": d}


# ── 8. Delete Snapshot ───────────────────────────────────────────────────────
def delete_snapshot(conn_row: dict, snapshot_id: str, location: str = "ALL") -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation DeleteSnapshot($input: VsphereVmDeleteSnapshotInput!) {
      vsphereVmDeleteSnapshot(input: $input) {
        status { id }
      }
    }
    """
    loc = f"V1_DELETE_VMWARE_SNAPSHOT_REQUEST_LOCATION_{location}"
    variables = {"input": {"id": snapshot_id, "location": loc}}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": "Snapshot marked for deletion", "data": d}


# ── 9. Pause / Resume SLA on Cluster ────────────────────────────────────────
def pause_resume_sla(conn_row: dict, sla_id: str, cluster_uuids: list,
                     pause: bool = True) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation PauseSla($input: PauseSlaInput!) {
      pauseSla(input: $input) {
        success
      }
    }
    """
    variables = {"input": {
        "slaId": sla_id,
        "clusterUuids": cluster_uuids,
        "pauseSla": pause,
    }}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": f"SLA {'paused' if pause else 'resumed'}", "data": d}


# ── 10. Pause / Resume Cluster Protection ────────────────────────────────────
def pause_resume_cluster(conn_row: dict, cluster_uuids: list,
                         pause: bool = True) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation PauseCluster($input: UpdateClusterPauseStatusInput!) {
      updateClusterPauseStatus(input: $input) {
        pauseStatuses { clusterUuid isPaused }
      }
    }
    """
    variables = {"input": {
        "clusterUuids": cluster_uuids,
        "togglePauseStatus": pause,
    }}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": f"Cluster protection {'paused' if pause else 'resumed'}", "data": d}


# ── 11. VM Snapshots listing ─────────────────────────────────────────────────
def list_vm_snapshots(conn_row: dict, vm_id: str) -> dict:
    url, token = _creds(conn_row)
    q = """
    query VmSnapshots($fid: UUID!) {
      snapshotOfASnappableConnection(
        workloadId: $fid,
        first: 50,
        sortOrder: DESC
      ) {
        edges {
          node {
            id
            date
            expirationDate
            isOnDemandSnapshot
            cluster { name }
          }
        }
      }
    }
    """
    d = _gql(url, token, q, {"fid": vm_id})
    snaps = []
    for edge in (d.get("snapshotOfASnappableConnection", {}).get("edges") or []):
        n = edge.get("node", {})
        snaps.append({
            "id":        n.get("id", ""),
            "date":      n.get("date", ""),
            "expiry":    n.get("expirationDate", ""),
            "on_demand": n.get("isOnDemandSnapshot", False),
            "cluster":   (n.get("cluster") or {}).get("name", ""),
        })
    return {"ok": True, "snapshots": snaps}


# ── 12. Retry Failed Job ─────────────────────────────────────────────────────
def retry_failed_job(conn_row: dict, object_ids: list) -> dict:
    url, token = _creds(conn_row)
    mutation = """
    mutation RetryBackup($objs: [BackupObject!]!, $cfg: BackupRunConfig!) {
      retryBackup(backupObjects: $objs, backupRunConfig: $cfg) { taskchainUuid }
    }
    """
    objs = [{"objectFid": oid, "objectType": "VMWARE_VIRTUAL_MACHINE"} for oid in object_ids]
    variables = {"objs": objs, "cfg": {"runNow": True}}
    d = _mutate(url, token, mutation, variables)
    return {"ok": True, "message": f"Retry triggered for {len(object_ids)} object(s)", "data": d}


# ── 13. Search VMs ───────────────────────────────────────────────────────────
def search_vms(conn_row: dict, query: str, first: int = 50) -> dict:
    url, token = _creds(conn_row)
    q = """
    query SearchVMs($q: String!, $first: Int) {
      vSphereVmNewConnection(
        filter: [{field: IS_RELIC, texts: ["false"]}, {field: NAME, texts: [$q]}]
        first: $first
      ) {
        count
        edges {
          node {
            id name powerStatus
            effectiveSlaDomain { id name }
            cluster { name }
          }
        }
      }
    }
    """
    d = _gql(url, token, q, {"q": query, "first": first})
    vms = []
    for edge in (d.get("vSphereVmNewConnection", {}).get("edges") or []):
        n = edge.get("node", {})
        sla = n.get("effectiveSlaDomain") or {}
        vms.append({
            "id":       n.get("id", ""),
            "name":     n.get("name", ""),
            "power":    n.get("powerStatus", ""),
            "sla_id":   sla.get("id", ""),
            "sla_name": sla.get("name", ""),
            "cluster":  (n.get("cluster") or {}).get("name", ""),
        })
    return {"vms": vms, "count": (d.get("vSphereVmNewConnection") or {}).get("count", len(vms))}

