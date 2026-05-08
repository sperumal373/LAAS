import psycopg2, psycopg2.extras
conn = psycopg2.connect(host="localhost", port=5433, dbname="caas_dashboard",
    user="caas_app", password="CaaS@App2024#", cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute("""
    SELECT COUNT(*) total, COUNT(uptime_days) has_uptime, 
           MAX(uptime_days) max_uptime, AVG(uptime_days)::int avg_uptime 
    FROM compliance_results 
    WHERE scan_id = (SELECT MAX(id) FROM compliance_scans WHERE status='completed')
""")
r = cur.fetchone()
print("uptime_days column stats:", dict(r))

# Also show a few sample rows with uptime
cur.execute("""
    SELECT a.hostname, a.ip_address, r.uptime_days, r.patch_age_days, r.missing_patches
    FROM compliance_results r JOIN compliance_assets a ON a.id = r.asset_id
    WHERE r.scan_id = (SELECT MAX(id) FROM compliance_scans WHERE status='completed')
      AND r.uptime_days IS NOT NULL
    ORDER BY r.uptime_days DESC LIMIT 10
""")
print("\nTop uptime VMs:")
for row in cur.fetchall():
    print(f"  {row['hostname']:35s}  ip={str(row['ip_address']):18s}  uptime={row['uptime_days']}d")
conn.close()
