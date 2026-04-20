"""
ipam_pg.py – Self-hosted IPAM using PostgreSQL
Manages VLANs and IP addresses for DC (172.17.0.0/16) and DR (172.16.0.0/16).
Provides: schema init, VLAN CRUD, IP CRUD, bulk-update, ping sweep, DNS lookup.
"""

import os, ipaddress, socket, subprocess, platform, logging, json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")
log = logging.getLogger("caas.ipam_pg")

# ── PostgreSQL connection ──────────────────────────────────────────────────────
PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5433"))
PG_DB   = os.getenv("PG_DB",   "caas_dashboard")
PG_USER = os.getenv("PG_USER", "caas_app")
PG_PASS = os.getenv("PG_PASS", "CaaS@App2024#")

def _get_pg():
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT,
        dbname=PG_DB, user=PG_USER, password=PG_PASS,
        connect_timeout=10,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    conn.autocommit = False
    return conn

# ── Schema bootstrap ──────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS ipam_vlans (
    id           SERIAL PRIMARY KEY,
    site         TEXT NOT NULL DEFAULT 'DC',       -- DC | DR
    vlan_id      INTEGER NOT NULL,
    name         TEXT NOT NULL DEFAULT '',
    subnet       TEXT NOT NULL,                    -- e.g. 172.17.63.0/24
    gateway      TEXT,
    description  TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    vrf          TEXT DEFAULT '',
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    deleted_at   TIMESTAMPTZ DEFAULT NULL,          -- soft-delete tombstone
    UNIQUE(site, vlan_id)
);

CREATE TABLE IF NOT EXISTS ipam_ips (
    id           SERIAL PRIMARY KEY,
    vlan_id      INTEGER NOT NULL REFERENCES ipam_vlans(id) ON DELETE CASCADE,
    ip_address   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'available', -- available | used | reserved | offline
    hostname     TEXT DEFAULT '',
    mac_address  TEXT DEFAULT '',
    device_type  TEXT DEFAULT '',
    dns_forward  TEXT DEFAULT '',
    dns_reverse  TEXT DEFAULT '',
    owner        TEXT DEFAULT '',
    description  TEXT DEFAULT '',
    remarks      TEXT DEFAULT '',
    last_seen    TIMESTAMPTZ,
    ping_status  TEXT DEFAULT 'unknown',            -- up | down | unknown
    ping_time    REAL,                              -- ms
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(vlan_id, ip_address)
);

CREATE TABLE IF NOT EXISTS ipam_changelog (
    id           SERIAL PRIMARY KEY,
    vlan_id      INTEGER REFERENCES ipam_vlans(id) ON DELETE SET NULL,
    ip_address   TEXT,
    field        TEXT,
    old_value    TEXT,
    new_value    TEXT,
    changed_by   TEXT DEFAULT '',
    changed_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ipam_ips_vlan    ON ipam_ips(vlan_id);
CREATE INDEX IF NOT EXISTS idx_ipam_ips_status  ON ipam_ips(status);
CREATE INDEX IF NOT EXISTS idx_ipam_ips_ip      ON ipam_ips(ip_address);
"""

# DC and DR seed VLANs
_SEED_VLANS = [
    # DC site – 172.17.x.0/24
    dict(site="DC", vlan_id=1263, name="VLAN1263", subnet="172.17.63.0/24", gateway="172.17.63.1",  description="DC VLAN 1263"),
    dict(site="DC", vlan_id=1264, name="VLAN1264", subnet="172.17.64.0/24", gateway="172.17.64.1",  description="DC VLAN 1264"),
    dict(site="DC", vlan_id=1265, name="VLAN1265", subnet="172.17.65.0/24", gateway="172.17.65.1",  description="DC VLAN 1265"),
    dict(site="DC", vlan_id=1266, name="VLAN1266", subnet="172.17.66.0/24", gateway="172.17.66.1",  description="DC VLAN 1266"),
    dict(site="DC", vlan_id=1267, name="VLAN1267", subnet="172.17.67.0/24", gateway="172.17.67.1",  description="DC VLAN 1267"),
    dict(site="DC", vlan_id=1268, name="VLAN1268", subnet="172.17.68.0/24", gateway="172.17.68.1",  description="DC VLAN 1268"),
    dict(site="DC", vlan_id=1269, name="VLAN1269", subnet="172.17.69.0/24", gateway="172.17.69.1",  description="DC VLAN 1269"),
    dict(site="DC", vlan_id=1270, name="VLAN1270", subnet="172.17.70.0/24", gateway="172.17.70.1",  description="DC VLAN 1270"),
    dict(site="DC", vlan_id=1101, name="VLAN1101", subnet="172.17.101.0/24",gateway="172.17.101.1", description="DC PROD vCenter"),
    dict(site="DC", vlan_id=1168, name="VLAN1168", subnet="172.17.168.0/24",gateway="172.17.168.1", description="DC Rookie vCenter"),
    dict(site="DC", vlan_id=1180, name="VLAN1180", subnet="172.17.80.0/24", gateway="172.17.80.1",  description="DC VCSA8 vCenter"),
    dict(site="DC", vlan_id=1173, name="VLAN1173", subnet="172.17.73.0/24", gateway="172.17.73.1",  description="DC Network vCenter"),
    dict(site="DC", vlan_id=1301, name="VLAN1301", subnet="172.17.101.0/24",gateway="172.17.101.1", description="DC VLAN 1301"),
    dict(site="DC", vlan_id=1302, name="VLAN1302", subnet="172.17.102.0/24",gateway="172.17.102.1", description="DC VLAN 1302"),
    # DR site – 172.16.x.0/24
    dict(site="DR", vlan_id=1202, name="VLAN1202", subnet="172.16.2.0/24",  gateway="172.16.2.1",   description="DR VLAN 1202"),
    dict(site="DR", vlan_id=1203, name="VLAN1203", subnet="172.16.3.0/24",  gateway="172.16.3.1",   description="DR VLAN 1203"),
    dict(site="DR", vlan_id=1204, name="VLAN1204", subnet="172.16.4.0/24",  gateway="172.16.4.1",   description="DR VLAN 1204"),
    dict(site="DR", vlan_id=1205, name="VLAN1205", subnet="172.16.5.0/24",  gateway="172.16.5.1",   description="DR VLAN 1205"),
    dict(site="DR", vlan_id=1206, name="VLAN1206", subnet="172.16.6.0/24",  gateway="172.16.6.1",   description="DR Zerto vCenter"),
]

def init_ipam_schema():
    """Create tables and seed default VLANs+IPs if not already present."""
    try:
        conn = _get_pg()
        cur = conn.cursor()
        cur.execute(_SCHEMA)
        # Migrate: add deleted_at if upgrading an existing DB without it
        cur.execute("""
            ALTER TABLE ipam_vlans ADD COLUMN IF NOT EXISTS
                deleted_at TIMESTAMPTZ DEFAULT NULL
        """)
        conn.commit()

        # Seed VLANs — skip any that were previously soft-deleted by the user
        for v in _SEED_VLANS:
            cur.execute("""
                INSERT INTO ipam_vlans (site, vlan_id, name, subnet, gateway, description)
                VALUES (%(site)s, %(vlan_id)s, %(name)s, %(subnet)s, %(gateway)s, %(description)s)
                ON CONFLICT (site, vlan_id) DO NOTHING
            """, v)
        conn.commit()

        # Seed IPs only for VLANs that are not deleted and have no IPs yet
        cur.execute("SELECT id, subnet, gateway FROM ipam_vlans WHERE deleted_at IS NULL")
        vlans = cur.fetchall()
        for vlan in vlans:
            cur.execute("SELECT COUNT(*) FROM ipam_ips WHERE vlan_id=%s", (vlan["id"],))
            cnt = cur.fetchone()
            if cnt and (cnt.get("count") or 0) > 0:
                continue
            _seed_ips_for_vlan(cur, vlan["id"], vlan["subnet"], vlan["gateway"])
        conn.commit()
        conn.close()
        log.info("[ipam_pg] Schema initialized and seeded")
    except Exception as e:
        log.error(f"[ipam_pg] init_ipam_schema failed: {e}")


def _seed_ips_for_vlan(cur, vlan_db_id: int, subnet_cidr: str, gateway: str):
    """Populate ipam_ips for every host address in a /24 (or smaller)."""
    try:
        net = ipaddress.IPv4Network(subnet_cidr, strict=False)
        hosts = list(net.hosts())
        # limit to /24 max 254 entries for safety
        for host in hosts[:254]:
            ip_str = str(host)
            is_gw  = (ip_str == gateway)
            status = "used" if is_gw else "available"
            dtype  = "Gateway" if is_gw else ""
            hname  = "" 
            cur.execute("""
                INSERT INTO ipam_ips (vlan_id, ip_address, status, hostname, device_type)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (vlan_id, ip_address) DO NOTHING
            """, (vlan_db_id, ip_str, status, hname, dtype))
    except Exception as e:
        log.error(f"[ipam_pg] _seed_ips_for_vlan {subnet_cidr}: {e}")


# ── VLAN CRUD ─────────────────────────────────────────────────────────────────
def list_vlans(site: str = None) -> list:
    conn = _get_pg()
    cur  = conn.cursor()
    sql  = """
        SELECT v.*,
               COUNT(i.id) AS total_ips,
               SUM(CASE WHEN i.status='used'      THEN 1 ELSE 0 END) AS used_ips,
               SUM(CASE WHEN i.status='available' THEN 1 ELSE 0 END) AS free_ips,
               SUM(CASE WHEN i.status='reserved'  THEN 1 ELSE 0 END) AS reserved_ips,
               SUM(CASE WHEN i.status='offline'   THEN 1 ELSE 0 END) AS offline_ips,
               SUM(CASE WHEN i.ping_status='up'   THEN 1 ELSE 0 END) AS up_ips,
               SUM(CASE WHEN i.ping_status='up'   THEN 1 ELSE 0 END) AS ping_up,
               SUM(CASE WHEN i.ping_status='down' THEN 1 ELSE 0 END) AS down_ips
        FROM ipam_vlans v
        LEFT JOIN ipam_ips i ON i.vlan_id=v.id
        WHERE v.deleted_at IS NULL
    """
    params = []
    if site:
        sql += " AND v.site=%s"
        params.append(site)
    sql += " GROUP BY v.id ORDER BY v.site, v.vlan_id"
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_vlan(vlan_db_id: int) -> dict | None:
    conn = _get_pg()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM ipam_vlans WHERE id=%s", (vlan_db_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def create_vlan(data: dict) -> dict:
    conn = _get_pg()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO ipam_vlans (site, vlan_id, name, subnet, gateway, description, notes, vrf)
        VALUES (%(site)s, %(vlan_id)s, %(name)s, %(subnet)s, %(gateway)s,
                %(description)s, %(notes)s, %(vrf)s)
        RETURNING *
    """, {
        "site":        data.get("site","DC"),
        "vlan_id":     int(data["vlan_id"]),
        "name":        data.get("name",""),
        "subnet":      data["subnet"],
        "gateway":     data.get("gateway",""),
        "description": data.get("description",""),
        "notes":       data.get("notes",""),
        "vrf":         data.get("vrf",""),
    })
    row = dict(cur.fetchone())
    # seed IPs
    _seed_ips_for_vlan(cur, row["id"], row["subnet"], row["gateway"] or "")
    conn.commit()
    conn.close()
    return row


def update_vlan(vlan_db_id: int, data: dict) -> dict | None:
    conn = _get_pg()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE ipam_vlans SET
            name=%s, description=%s, notes=%s, vrf=%s, updated_at=NOW()
        WHERE id=%s RETURNING *
    """, (data.get("name",""), data.get("description",""),
          data.get("notes",""), data.get("vrf",""), vlan_db_id))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return dict(row) if row else None


def delete_vlan(vlan_db_id: int) -> bool:
    """Soft-delete a VLAN so it survives service restarts and won't be re-seeded."""
    conn = _get_pg()
    cur  = conn.cursor()
    # Remove all IPs (changelog entries kept via ON DELETE SET NULL)
    cur.execute("DELETE FROM ipam_ips WHERE vlan_id=%s", (vlan_db_id,))
    # Tombstone the VLAN row so the seed loop won't re-create it
    cur.execute("UPDATE ipam_vlans SET deleted_at=NOW(), updated_at=NOW() WHERE id=%s",
                (vlan_db_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# ── IP Address CRUD ───────────────────────────────────────────────────────────
def list_ips(vlan_db_id: int, status: str = None, q: str = None) -> list:
    conn = _get_pg()
    cur  = conn.cursor()
    sql  = "SELECT * FROM ipam_ips WHERE vlan_id=%s"
    params = [vlan_db_id]
    if status:
        sql += " AND status=%s"; params.append(status)
    if q:
        sql += " AND (ip_address ILIKE %s OR hostname ILIKE %s OR description ILIKE %s OR owner ILIKE %s)"
        like = f"%{q}%"
        params += [like, like, like, like]
    sql += " ORDER BY inet(ip_address)"
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_ip(ip_id: int) -> dict | None:
    conn = _get_pg()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM ipam_ips WHERE id=%s", (ip_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_ip(ip_id: int, data: dict, changed_by: str = "system") -> dict | None:
    conn = _get_pg()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM ipam_ips WHERE id=%s", (ip_id,))
    old = cur.fetchone()
    if not old:
        conn.close()
        return None
    fields = ["status","hostname","mac_address","device_type","dns_forward",
              "dns_reverse","owner","description","remarks"]
    updates = []
    for f in fields:
        if f in data:
            old_val = str(old.get(f) or "")
            new_val = str(data[f] or "")
            if old_val != new_val:
                cur.execute("""
                    INSERT INTO ipam_changelog
                        (vlan_id, ip_address, field, old_value, new_value, changed_by)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (old["vlan_id"], old["ip_address"], f, old_val, new_val, changed_by))
            updates.append((f, data[f]))
    if updates:
        set_clause = ", ".join(f"{f}=%s" for f,_ in updates)
        vals       = [v for _,v in updates]
        vals.append(ip_id)
        cur.execute(f"UPDATE ipam_ips SET {set_clause}, updated_at=NOW() WHERE id=%s", vals)
    conn.commit()
    cur.execute("SELECT * FROM ipam_ips WHERE id=%s", (ip_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def bulk_update_ips(ip_ids: list, data: dict, changed_by: str = "system") -> int:
    updated = 0
    for ip_id in ip_ids:
        if update_ip(ip_id, data, changed_by):
            updated += 1
    return updated


# ── Ping helpers ──────────────────────────────────────────────────────────────
def ping_ip(ip: str) -> dict:
    """Ping a single IP once with a short timeout, return {up, time_ms}."""
    try:
        if platform.system().lower() == "windows":
            # -n 1 packet, -w 500ms timeout
            cmd = ["ping", "-n", "1", "-w", "500", ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "1", ip]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        output = result.stdout
        up = "TTL=" in output or "ttl=" in output
        time_ms = None
        try:
            for line in output.splitlines():
                if "time=" in line.lower() or "average" in line.lower():
                    import re as _re
                    m = _re.search(r"[=<](\d+(?:\.\d+)?)\s*ms", line, _re.I)
                    if m:
                        time_ms = float(m.group(1))
                        break
        except Exception:
            pass
        return {"up": up, "time_ms": time_ms}
    except Exception:
        return {"up": False, "time_ms": None}


def ping_and_save(vlan_db_id: int, ip_ids: list = None, workers: int = 50):
    """Ping all IPs in a VLAN concurrently (50 threads) and write results to DB."""
    import concurrent.futures as _cf

    conn = _get_pg()
    cur  = conn.cursor()
    if ip_ids:
        cur.execute("SELECT id, ip_address, status, device_type FROM ipam_ips WHERE vlan_id=%s AND id=ANY(%s)",
                    (vlan_db_id, ip_ids))
    else:
        cur.execute("SELECT id, ip_address, status, device_type FROM ipam_ips WHERE vlan_id=%s", (vlan_db_id,))
    ips = cur.fetchall()

    # Ping all IPs concurrently
    def _ping_row(row):
        r = ping_ip(row["ip_address"])
        return row["id"], row["ip_address"], "up" if r["up"] else "down", r["time_ms"]

    results = {}
    with _cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for ip_id, ip_addr, ps, time_ms in ex.map(_ping_row, ips):
            # Look up current record from pre-fetched list (no extra DB query)
            cur_rec        = next((r for r in ips if r["id"] == ip_id), {})
            current_status = cur_rec.get("status", "available")
            current_dtype  = (cur_rec.get("device_type") or "").strip()

            if ps == "up":
                # Ping alive → mark used; never overwrite reserved
                new_status = current_status if current_status == "reserved" else "used"
            else:
                # Ping down → revert to available only if auto-set (no device_type)
                if current_status == "used" and not current_dtype:
                    new_status = "available"
                else:
                    new_status = current_status

            cur.execute("""
                UPDATE ipam_ips
                SET ping_status=%s, ping_time=%s, status=%s,
                    last_seen=CASE WHEN %s='up' THEN NOW() ELSE last_seen END,
                    updated_at=NOW()
                WHERE id=%s
            """, (ps, time_ms, new_status, ps, ip_id))
            results[ip_addr] = {"ping": ps, "status": new_status, "time_ms": time_ms}

    conn.commit()
    conn.close()
    up_count = sum(1 for v in results.values() if v["ping"] == "up")
    log.info(f"[ipam_pg] ping_and_save vlan={vlan_db_id}: {len(results)} IPs, up={up_count}")
    return results


# ── DNS lookup ────────────────────────────────────────────────────────────────
def dns_lookup(ip: str) -> dict:
    """Reverse DNS + forward DNS lookup for a single IP."""
    result = {"ip": ip, "hostname": "", "dns_forward": "", "dns_reverse": ""}
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        result["hostname"]    = hostname
        result["dns_reverse"] = hostname
        # forward lookup
        try:
            fwd_ip = socket.gethostbyname(hostname)
            result["dns_forward"] = hostname if fwd_ip == ip else hostname
        except Exception:
            result["dns_forward"] = hostname
    except Exception:
        pass
    return result


def dns_lookup_and_save(vlan_db_id: int, ip_ids: list = None, changed_by: str = "system"):
    """Run DNS lookup for all (or selected) IPs and update records."""
    conn = _get_pg()
    cur  = conn.cursor()
    if ip_ids:
        cur.execute("SELECT id, ip_address FROM ipam_ips WHERE vlan_id=%s AND id=ANY(%s)",
                    (vlan_db_id, ip_ids))
    else:
        cur.execute("SELECT id, ip_address FROM ipam_ips WHERE vlan_id=%s", (vlan_db_id,))
    ips = cur.fetchall()
    conn.close()
    results = {}
    for row in ips:
        d = dns_lookup(row["ip_address"])
        if d["hostname"]:
            update_ip(row["id"], {
                "hostname":    d["hostname"],
                "dns_reverse": d["dns_reverse"],
                "dns_forward": d["dns_forward"],
            }, changed_by=changed_by)
        results[row["ip_address"]] = d
    return results


# ── Changelog ─────────────────────────────────────────────────────────────────
def list_changelog(vlan_db_id: int = None, limit: int = 200) -> list:
    conn = _get_pg()
    cur  = conn.cursor()
    if vlan_db_id:
        cur.execute("""
            SELECT * FROM ipam_changelog WHERE vlan_id=%s
            ORDER BY changed_at DESC LIMIT %s
        """, (vlan_db_id, limit))
    else:
        cur.execute("""
            SELECT * FROM ipam_changelog
            ORDER BY changed_at DESC LIMIT %s
        """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── Conflict detection ────────────────────────────────────────────────────────
def list_conflicts() -> list:
    """Find duplicate IPs or hostname mismatches across VLANs."""
    conn = _get_pg()
    cur  = conn.cursor()
    # Duplicate IP across different VLANs
    cur.execute("""
        SELECT i.ip_address,
               COUNT(DISTINCT i.vlan_id) AS vlan_count,
               array_agg(DISTINCT v.name) AS vlans
        FROM ipam_ips i
        JOIN ipam_vlans v ON v.id=i.vlan_id
        WHERE i.status='used'
        GROUP BY i.ip_address
        HAVING COUNT(DISTINCT i.vlan_id) > 1
    """)
    dups = [dict(r) for r in cur.fetchall()]
    # Duplicate hostname across different IPs
    cur.execute("""
        SELECT i.hostname,
               COUNT(*) AS ip_count,
               array_agg(i.ip_address) AS ips
        FROM ipam_ips i
        WHERE i.hostname != '' AND i.status='used'
        GROUP BY i.hostname
        HAVING COUNT(*) > 1
    """)
    dup_hosts = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"duplicate_ips": dups, "duplicate_hostnames": dup_hosts}


# ── Summary stats ─────────────────────────────────────────────────────────────
def get_summary() -> dict:
    conn = _get_pg()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(DISTINCT v.id) AS total_vlans,
            COUNT(i.id)          AS total_ips,
            SUM(CASE WHEN i.status='used'      THEN 1 ELSE 0 END) AS used_ips,
            SUM(CASE WHEN i.status='available' THEN 1 ELSE 0 END) AS available_ips,
            SUM(CASE WHEN i.status='available' THEN 1 ELSE 0 END) AS free_ips,
            SUM(CASE WHEN i.status='reserved'  THEN 1 ELSE 0 END) AS reserved_ips,
            SUM(CASE WHEN i.status='offline'   THEN 1 ELSE 0 END) AS offline_ips,
            SUM(CASE WHEN i.ping_status='up'   THEN 1 ELSE 0 END) AS up_ips,
            SUM(CASE WHEN i.ping_status='down' THEN 1 ELSE 0 END) AS down_ips
        FROM ipam_vlans v
        LEFT JOIN ipam_ips i ON i.vlan_id=v.id
        WHERE v.deleted_at IS NULL
    """)
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else {}
