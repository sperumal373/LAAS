"""
db.py — SQLite persistence layer for CaaS Dashboard
Tables: users, vm_requests, audit_log, project_tag_owners
"""
import sqlite3, os, json, time, hashlib, secrets
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "caas.db"

# ── Bootstrap ─────────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    UNIQUE NOT NULL,
            display_name TEXT   DEFAULT '',
            email       TEXT    DEFAULT '',
            role        TEXT    NOT NULL DEFAULT 'requester',
            auth_source TEXT    NOT NULL DEFAULT 'ad',   -- 'ad' | 'local'
            password_hash TEXT  DEFAULT NULL,            -- only for local users
            created_at  TEXT    DEFAULT (datetime('now')),
            last_login  TEXT    DEFAULT NULL,
            is_active   INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS vm_requests (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            req_number   TEXT    UNIQUE NOT NULL,        -- e.g. REQ-00042
            requester    TEXT    NOT NULL,
            vcenter_id   TEXT    NOT NULL,
            vm_name      TEXT    NOT NULL,
            cpu          INTEGER NOT NULL,
            ram_gb       INTEGER NOT NULL,
            disk_gb      INTEGER NOT NULL,
            os_template  TEXT    NOT NULL,
            host         TEXT    DEFAULT NULL,
            datastore    TEXT    DEFAULT NULL,
            network      TEXT    DEFAULT NULL,
            notes        TEXT    DEFAULT '',
            -- IP / Guest Customization
            ip_mode      TEXT    DEFAULT 'dhcp',         -- dhcp | static
            ip_address   TEXT    DEFAULT NULL,
            subnet_mask  TEXT    DEFAULT '255.255.255.0',
            gateway      TEXT    DEFAULT NULL,
            dns1         TEXT    DEFAULT NULL,
            dns2         TEXT    DEFAULT NULL,
            hostname     TEXT    DEFAULT NULL,
            domain       TEXT    DEFAULT NULL,
            status       TEXT    DEFAULT 'pending',      -- pending|approved|declined|provisioning|done|failed
            admin_notes  TEXT    DEFAULT '',
            reviewed_by  TEXT    DEFAULT NULL,
            reviewed_at  TEXT    DEFAULT NULL,
            -- Admin can modify resources before approving
            approved_cpu     INTEGER DEFAULT NULL,
            approved_ram_gb  INTEGER DEFAULT NULL,
            approved_disk_gb INTEGER DEFAULT NULL,
            approved_host    TEXT    DEFAULT NULL,
            approved_ds      TEXT    DEFAULT NULL,
            approved_network TEXT    DEFAULT NULL,
            created_at   TEXT    DEFAULT (datetime('now')),
            updated_at   TEXT    DEFAULT (datetime('now'))
        );
        -- Migrate existing db: add IP columns if they don't exist yet
        CREATE TABLE IF NOT EXISTS _migration_lock (id INTEGER PRIMARY KEY);


        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    DEFAULT (datetime('now')),
            username    TEXT    NOT NULL,
            role        TEXT    DEFAULT '',
            action      TEXT    NOT NULL,
            target      TEXT    DEFAULT '',
            detail      TEXT    DEFAULT '',
            ip          TEXT    DEFAULT '',
            result      TEXT    DEFAULT 'ok'            -- ok | fail
        );

        CREATE TABLE IF NOT EXISTS project_tag_owners (
            tag            TEXT NOT NULL,
            vcenter_scope  TEXT NOT NULL DEFAULT 'all',
            owner_name     TEXT DEFAULT '',
            owner_email    TEXT DEFAULT '',
            updated_by     TEXT DEFAULT '',
            updated_at     TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (tag, vcenter_scope)
        );

        -- Seed a local admin fallback (in case AD is unreachable)
        INSERT OR IGNORE INTO users (username, display_name, role, auth_source, password_hash)
        VALUES ('admin', 'Local Admin', 'admin', 'local',
                'caas@2024');
        """)
    print(f"[db] Initialized: {DB_PATH}")
    # Migrate existing databases — add IP columns if absent
    _migrate_db()

def _migrate_db():
    """Add new columns to existing databases without breaking them."""
    all_cols = [
        ("ip_mode",          "TEXT DEFAULT 'dhcp'"),
        ("ip_address",       "TEXT DEFAULT NULL"),
        ("subnet_mask",      "TEXT DEFAULT '255.255.255.0'"),
        ("gateway",          "TEXT DEFAULT NULL"),
        ("dns1",             "TEXT DEFAULT NULL"),
        ("dns2",             "TEXT DEFAULT NULL"),
        ("hostname",         "TEXT DEFAULT NULL"),
        ("domain",           "TEXT DEFAULT NULL"),
        # Nutanix-specific columns
        ("platform",         "TEXT DEFAULT 'vmware'"),
        ("ntx_pc_id",        "INTEGER DEFAULT NULL"),
        ("ntx_pc_name",      "TEXT DEFAULT NULL"),
        ("ntx_cluster_uuid", "TEXT DEFAULT NULL"),
        ("ntx_cluster_name", "TEXT DEFAULT NULL"),
        ("ntx_disks",        "TEXT DEFAULT NULL"),
        ("ntx_nics",         "TEXT DEFAULT NULL"),
        ("num_cores_per_vcpu", "INTEGER DEFAULT 1"),
    ]
    with get_conn() as c:
        existing = {row[1] for row in c.execute("PRAGMA table_info(vm_requests)").fetchall()}
        for col_name, col_def in all_cols:
            if col_name not in existing:
                c.execute(f"ALTER TABLE vm_requests ADD COLUMN {col_name} {col_def}")
                print(f"[db] Migrated: added column {col_name}")


# ── Users ─────────────────────────────────────────────────────────────────────
def upsert_user(username: str, display_name: str, email: str,
                role: str, auth_source: str = "ad") -> dict:
    with get_conn() as c:
        c.execute("""
            INSERT INTO users (username, display_name, email, role, auth_source, last_login)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(username) DO UPDATE SET
                display_name = excluded.display_name,
                email        = excluded.email,
                role         = excluded.role,
                last_login   = datetime('now')
        """, (username, display_name, email, role, auth_source))
    return get_user(username)

def get_user(username: str) -> dict | None:
    with get_conn() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None

def list_users() -> list:
    with get_conn() as c:
        rows = c.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]

def update_user_role(username: str, role: str):
    with get_conn() as c:
        c.execute("UPDATE users SET role=? WHERE username=?", (role, username))

def delete_user(username: str) -> bool:
    with get_conn() as c:
        r = c.execute("DELETE FROM users WHERE username=?", (username,))
    return r.rowcount > 0

# ── Password helpers (for local users) ───────────────────────────────────────
def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return f"pbkdf2:{salt}:{hashed}"

def _verify_password(stored: str, password: str) -> bool:
    try:
        if stored and stored.startswith("pbkdf2:"):
            _, salt, hashed = stored.split(":", 2)
            return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex() == hashed
        # Legacy plain-text fallback (original seeded admin)
        return stored == password
    except Exception:
        return False

def create_local_user(username: str, display_name: str, email: str,
                      role: str, password: str) -> dict:
    ph = _hash_password(password)
    with get_conn() as c:
        c.execute("""
            INSERT INTO users (username, display_name, email, role, auth_source, password_hash)
            VALUES (?, ?, ?, ?, 'local', ?)
            ON CONFLICT(username) DO UPDATE SET
                display_name  = excluded.display_name,
                email         = excluded.email,
                role          = excluded.role,
                password_hash = excluded.password_hash
        """, (username, display_name, email, role, ph))
    return get_user(username)

def verify_local_user(username: str, password: str) -> dict | None:
    """Return user dict if username/password match a local DB user, else None."""
    user = get_user(username)
    if not user or user.get("auth_source") != "local":
        return None
    if not user.get("password_hash"):
        return None
    if not _verify_password(user["password_hash"], password):
        return None
    return user

def upsert_ad_user(username: str, display_name: str, email: str, role: str) -> dict:
    """Insert or update an AD user entry (preserves auth_source=ad, never touches password_hash)."""
    with get_conn() as c:
        c.execute("""
            INSERT INTO users (username, display_name, email, role, auth_source)
            VALUES (?, ?, ?, ?, 'ad')
            ON CONFLICT(username) DO UPDATE SET
                display_name = excluded.display_name,
                email        = excluded.email,
                role         = excluded.role
        """, (username, display_name, email, role))
    return get_user(username)

# ── VM Requests ───────────────────────────────────────────────────────────────
def _next_req_number() -> str:
    with get_conn() as c:
        count = c.execute("SELECT COUNT(*) FROM vm_requests").fetchone()[0]
    return f"REQ-{str(count+1).zfill(5)}"

def create_vm_request(data: dict) -> dict:
    req_num = _next_req_number()
    platform = data.get("platform", "vmware")
    # For Nutanix requests use 'ntx-{pc_id}' as vcenter_id placeholder
    vcenter_id = data.get("vcenter_id") or (f"ntx-{data.get('ntx_pc_id','0')}" if platform == 'nutanix' else 'unknown')
    with get_conn() as c:
        c.execute("""
            INSERT INTO vm_requests
                (req_number, requester, vcenter_id, vm_name, cpu, ram_gb, disk_gb,
                 os_template, host, datastore, network, notes,
                 ip_mode, ip_address, subnet_mask, gateway, dns1, dns2, hostname, domain,
                 platform, ntx_pc_id, ntx_pc_name, ntx_cluster_uuid, ntx_cluster_name,
                 ntx_disks, ntx_nics, num_cores_per_vcpu)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (req_num, data["requester"], vcenter_id, data["vm_name"],
              data["cpu"], data["ram_gb"], data["disk_gb"], data.get("os_template","custom"),
              data.get("host",""), data.get("datastore",""),
              data.get("network",""), data.get("notes",""),
              data.get("ip_mode","dhcp"), data.get("ip_address",""),
              data.get("subnet_mask","255.255.255.0"), data.get("gateway",""),
              data.get("dns1",""), data.get("dns2",""),
              data.get("hostname",""), data.get("domain",""),
              platform,
              data.get("ntx_pc_id"), data.get("ntx_pc_name"),
              data.get("ntx_cluster_uuid"), data.get("ntx_cluster_name"),
              data.get("ntx_disks"), data.get("ntx_nics"),
              data.get("num_cores_per_vcpu", 1)))
    return get_vm_request(req_num)

def get_vm_request(req_number: str) -> dict | None:
    with get_conn() as c:
        row = c.execute("SELECT * FROM vm_requests WHERE req_number=?",
                        (req_number,)).fetchone()
    return dict(row) if row else None

def list_vm_requests(requester: str = None, status: str = None) -> list:
    sql = "SELECT * FROM vm_requests WHERE 1=1"
    params = []
    if requester:
        sql += " AND requester=?"; params.append(requester)
    if status:
        sql += " AND status=?";    params.append(status)
    sql += " ORDER BY created_at DESC"
    with get_conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [dict(r) for r in rows]

def review_vm_request(req_number: str, reviewer: str, decision: str,
                      admin_notes: str = "", overrides: dict = None) -> dict:
    overrides = overrides or {}
    with get_conn() as c:
        c.execute("""
            UPDATE vm_requests SET
                status          = ?,
                reviewed_by     = ?,
                reviewed_at     = datetime('now'),
                admin_notes     = ?,
                updated_at      = datetime('now'),
                approved_cpu    = ?,
                approved_ram_gb = ?,
                approved_disk_gb= ?,
                approved_host   = ?,
                approved_ds     = ?,
                approved_network= ?
            WHERE req_number = ?
        """, (decision, reviewer, admin_notes,
              overrides.get("cpu"), overrides.get("ram_gb"),
              overrides.get("disk_gb"), overrides.get("host"),
              overrides.get("datastore"), overrides.get("network"),
              req_number))
    return get_vm_request(req_number)

def update_request_status(req_number: str, status: str):
    with get_conn() as c:
        c.execute("UPDATE vm_requests SET status=?, updated_at=datetime('now') WHERE req_number=?",
                  (status, req_number))

# ── Audit Log ─────────────────────────────────────────────────────────────────
def audit(username: str, action: str, target: str = "",
          detail: str = "", ip: str = "", role: str = "", result: str = "ok"):
    with get_conn() as c:
        c.execute("""
            INSERT INTO audit_log (username, role, action, target, detail, ip, result)
            VALUES (?,?,?,?,?,?,?)
        """, (username, role, action, target, detail, ip, result))

def list_audit(limit: int = 500, username: str = None) -> list:
    sql = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if username:
        sql += " AND username=?"; params.append(username)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ── Project Tag Owner Overrides ──────────────────────────────────────────────
def list_project_tag_owners(vcenter_scope: str = "all") -> list:
    with get_conn() as c:
        rows = c.execute(
            "SELECT * FROM project_tag_owners WHERE vcenter_scope=? ORDER BY tag ASC",
            (vcenter_scope,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_project_tag_owner_map(vcenter_scope: str = "all") -> dict:
    rows = list_project_tag_owners(vcenter_scope)
    return {
        (r.get("tag") or ""): {
            "owner_name": r.get("owner_name") or "",
            "owner_email": r.get("owner_email") or "",
        }
        for r in rows
        if r.get("tag")
    }


def upsert_project_tag_owner(tag: str, vcenter_scope: str, owner_name: str,
                             owner_email: str, updated_by: str = ""):
    with get_conn() as c:
        c.execute("""
            INSERT INTO project_tag_owners (tag, vcenter_scope, owner_name, owner_email, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(tag, vcenter_scope) DO UPDATE SET
                owner_name = excluded.owner_name,
                owner_email = excluded.owner_email,
                updated_by = excluded.updated_by,
                updated_at = datetime('now')
        """, (tag, vcenter_scope, owner_name, owner_email, updated_by))

# Init on import
init_db()
