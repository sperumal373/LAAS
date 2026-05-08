import psycopg2, psycopg2.extras, json, re

conn = psycopg2.connect(host="localhost", port=5433, dbname="caas_dashboard",
                        user="caas_app", password="CaaS@App2024#",
                        cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

# ── 1. Show compliance_results columns
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'compliance_results'
    ORDER BY ordinal_position
""")
print("=== compliance_results COLUMNS ===")
cols_r = []
for r in cur.fetchall():
    print(f"  {r['column_name']:<30} {r['data_type']}")
    cols_r.append(r['column_name'])

# ── 2. Sample 5 rows from the joined view
cur.execute("""
    WITH latest AS (
        SELECT DISTINCT ON (r.asset_id)
               r.asset_id, r.score, r.status, r.scanned_at,
               r.patch_age_days, r.missing_patches, r.checks
        FROM compliance_results r
        JOIN compliance_scans s ON s.id = r.scan_id
        WHERE s.status = 'completed'
        ORDER BY r.asset_id, r.scanned_at DESC
    )
    SELECT
        a.id, a.hostname, a.ip_address, a.os_name, a.os_version,
        a.asset_type, a.vcenter, a.cluster,
        a.location, a.vm_tags,
        a.missing_patches AS asset_missing_patches,
        a.ssh_auth_failed,
        r.score, r.status AS compliance_status,
        r.patch_age_days, r.missing_patches AS result_missing_patches,
        r.checks
    FROM compliance_assets a
    JOIN latest r ON r.asset_id = a.id
    LIMIT 5
""")
print("\n=== SAMPLE JOINED ROWS ===")
for row in cur.fetchall():
    d = dict(row)
    checks = d.get("checks") or []
    if isinstance(checks, str):
        try: checks = json.loads(checks)
        except: checks = []

    uptime_d = None
    for c in (checks if isinstance(checks, list) else []):
        if isinstance(c, dict) and c.get("name") == "uptime":
            m = re.search(r"(\d+)\s*d", c.get("message",""))
            if m: uptime_d = int(m.group(1))

    print(f"\n  hostname             : {d['hostname']}")
    print(f"  ip_address           : {d['ip_address']}")
    print(f"  os_name              : {d['os_name']}")
    print(f"  os_version           : {d['os_version']}")
    print(f"  vcenter              : {d['vcenter']}")
    print(f"  location             : {d['location']}")
    print(f"  vm_tags              : {d['vm_tags']}")
    print(f"  compliance_status    : {d['compliance_status']}")
    print(f"  score                : {d['score']}")
    print(f"  patch_age_days       : {d['patch_age_days']}")
    print(f"  missing_patches(res) : {d['result_missing_patches']}")
    print(f"  missing_patches(ast) : {d['asset_missing_patches']}")
    print(f"  uptime (checks)      : {str(uptime_d)+'d' if uptime_d else '(none)'}")
    check_names = [c.get("name") for c in checks if isinstance(c, dict)] if isinstance(checks, list) else []
    print(f"  checks keys          : {check_names}")

# ── 3. Coverage stats across all assets
cur.execute("""
    WITH latest AS (
        SELECT DISTINCT ON (r.asset_id)
               r.asset_id, r.score, r.status, r.scanned_at,
               r.patch_age_days, r.missing_patches, r.checks
        FROM compliance_results r
        JOIN compliance_scans s ON s.id = r.scan_id
        WHERE s.status = 'completed'
        ORDER BY r.asset_id, r.scanned_at DESC
    )
    SELECT
        COUNT(*)                                                                        AS total,
        COUNT(a.ip_address)   FILTER (WHERE a.ip_address IS NOT NULL)                  AS has_ip,
        COUNT(a.os_version)   FILTER (WHERE a.os_version IS NOT NULL AND a.os_version != '') AS has_os_version,
        COUNT(a.vm_tags)      FILTER (WHERE a.vm_tags IS NOT NULL AND array_length(a.vm_tags,1) > 0) AS has_tags,
        COUNT(r.patch_age_days) FILTER (WHERE r.patch_age_days IS NOT NULL)            AS has_patch_age,
        COUNT(r.missing_patches) FILTER (WHERE r.missing_patches IS NOT NULL)          AS has_missing_patches,
        COUNT(r.checks)       FILTER (WHERE r.checks IS NOT NULL)                      AS has_checks,
        COUNT(r.checks)       FILTER (WHERE r.checks::text LIKE '%uptime%')            AS has_uptime_check
    FROM compliance_assets a
    JOIN latest r ON r.asset_id = a.id
""")
s = cur.fetchone()
print(f"\n=== COVERAGE ({s['total']} assets with scan results) ===")
print(f"  ip_address       : {s['has_ip']} / {s['total']}")
print(f"  os_version       : {s['has_os_version']} / {s['total']}")
print(f"  vm_tags          : {s['has_tags']} / {s['total']}")
print(f"  patch_age_days   : {s['has_patch_age']} / {s['total']}")
print(f"  missing_patches  : {s['has_missing_patches']} / {s['total']}")
print(f"  checks JSON      : {s['has_checks']} / {s['total']}")
print(f"  uptime in checks : {s['has_uptime_check']} / {s['total']}")

# ── 4. Check if eol_os / tools_ok etc are in compliance_results
for col in ['eol_os', 'tools_ok', 'hw_version_ok', 'snapshot_ok']:
    print(f"  compliance_results.{col:<20}: {'YES' if col in cols_r else 'MISSING'}")

cur.close()
conn.close()
print("\nDone.")
