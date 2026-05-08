import psycopg2, psycopg2.extras, json, urllib.request

conn = psycopg2.connect(host="localhost", port=5433, dbname="caas_dashboard",
    user="caas_app", password="CaaS@App2024#", cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

# 1. Check how many of the FIRST 50 rows (sorted by score ASC) have uptime
cur.execute("""
    WITH latest AS (
        SELECT DISTINCT ON (r.asset_id) r.*
        FROM compliance_results r
        JOIN compliance_scans s ON s.id = r.scan_id
        WHERE s.status = 'completed'
        ORDER BY r.asset_id, r.scanned_at DESC
    )
    SELECT a.hostname, a.ip_address, a.power_state,
           r.score, r.uptime_days, r.patch_age_days, r.missing_patches
    FROM compliance_assets a
    JOIN latest r ON r.asset_id = a.id
    ORDER BY r.score ASC, a.hostname
    LIMIT 50
""")
rows = cur.fetchall()
has_uptime = sum(1 for r in rows if r["uptime_days"] is not None)
has_ip     = sum(1 for r in rows if r["ip_address"])
print(f"First 50 rows (score ASC order):")
print(f"  has uptime_days : {has_uptime} / 50")
print(f"  has ip_address  : {has_ip} / 50")
print(f"  power_states    : {set(r['power_state'] for r in rows)}")

# 2. Check sample rows with uptime
cur.execute("""
    WITH latest AS (
        SELECT DISTINCT ON (r.asset_id) r.*
        FROM compliance_results r
        JOIN compliance_scans s ON s.id = r.scan_id
        WHERE s.status = 'completed'
        ORDER BY r.asset_id, r.scanned_at DESC
    )
    SELECT a.hostname, a.ip_address, r.uptime_days, r.patch_age_days, r.missing_patches, r.score
    FROM compliance_assets a
    JOIN latest r ON r.asset_id = a.id
    WHERE r.uptime_days IS NOT NULL
    ORDER BY r.score ASC, a.hostname
    LIMIT 5
""")
print("\nSample rows WITH uptime (score ASC):")
for r in cur.fetchall():
    print(f"  {r['hostname']:35s}  ip={str(r['ip_address']):18s}  uptime={r['uptime_days']}d  score={r['score']}")

# 3. Check patch_age and missing patches breakdown
cur.execute("""
    WITH latest AS (
        SELECT DISTINCT ON (r.asset_id) r.*
        FROM compliance_results r
        JOIN compliance_scans s ON s.id = r.scan_id
        WHERE s.status = 'completed'
        ORDER BY r.asset_id, r.scanned_at DESC
    )
    SELECT
        COUNT(*) total,
        COUNT(r.uptime_days) has_uptime,
        COUNT(r.patch_age_days) has_patch_age,
        COUNT(r.missing_patches) FILTER (WHERE r.missing_patches > 0) has_real_missing
    FROM compliance_assets a JOIN latest r ON r.asset_id = a.id
""")
s = cur.fetchone()
print(f"\nOverall coverage:")
print(f"  uptime_days     : {s['has_uptime']} / {s['total']}")
print(f"  patch_age_days  : {s['has_patch_age']} / {s['total']}")
print(f"  missing > 0     : {s['has_real_missing']} / {s['total']}")

# 4. Check field name returned by API
cur.execute("""
    WITH latest AS (
        SELECT DISTINCT ON (r.asset_id) r.*
        FROM compliance_results r
        JOIN compliance_scans s ON s.id = r.scan_id
        WHERE s.status = 'completed'
        ORDER BY r.asset_id, r.scanned_at DESC
    )
    SELECT a.id, a.hostname, a.ip_address, a.os_name, a.os_version,
           a.os_family, a.asset_type, a.vcenter, a.cluster,
           a.hypervisor_host, a.cpu_count, a.memory_gb, a.disk_gb,
           a.power_state, a.tools_status, a.hw_version,
           a.environment, a.owner_team, a.last_seen,
           a.ssh_auth_failed, a.vm_tags, a.location,
           r.score, r.status AS compliance_status,
           r.patch_age_days, r.uptime_days, r.eol_os, r.missing_patches,
           r.tools_ok, r.hw_version_ok, r.snapshot_ok,
           r.scanned_at AS last_scanned
    FROM compliance_assets a
    JOIN latest r ON r.asset_id = a.id
    WHERE r.uptime_days IS NOT NULL
    LIMIT 1
""")
row = cur.fetchone()
if row:
    print(f"\nAPI query column check (row with uptime):")
    print(f"  hostname    = {row['hostname']}")
    print(f"  uptime_days = {row['uptime_days']}")
    print(f"  patch_age   = {row['patch_age_days']}")
    print(f"  missing     = {row['missing_patches']}")
    print(f"  Columns returned: {list(row.keys())}")

conn.close()
print("\nDone.")
