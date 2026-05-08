import psycopg2, psycopg2.extras
conn = psycopg2.connect(host="localhost", port=5433, dbname="caas_dashboard",
    user="caas_app", password="CaaS@App2024#", cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute("""
    WITH latest AS (SELECT DISTINCT ON (r.asset_id) r.* FROM compliance_results r
        JOIN compliance_scans s ON s.id=r.scan_id WHERE s.status='completed'
        ORDER BY r.asset_id, r.scanned_at DESC)
    SELECT a.hostname, a.power_state, a.ip_address, r.uptime_days, r.patch_age_days, r.missing_patches, r.score
    FROM compliance_assets a JOIN latest r ON r.asset_id=a.id
    ORDER BY (CASE WHEN a.power_state='poweredOn' THEN 0 ELSE 1 END) ASC,
             r.uptime_days DESC NULLS LAST, a.hostname ASC LIMIT 8
""")
print("First 8 rows with new sort:")
for r in cur.fetchall():
    print(f"  {r['hostname']:35s}  state={r['power_state']:12s}  uptime={str(r['uptime_days']):5s}  patch={str(r['patch_age_days']):5s}  missing={r['missing_patches']}  score={r['score']}")
conn.close()
