import psycopg2, psycopg2.extras, json
conn = psycopg2.connect(host="localhost", port=5433, dbname="caas_dashboard",
    user="caas_app", password="CaaS@App2024#", cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute("""
    SELECT a.hostname, a.ip_address, r.checks
    FROM compliance_results r
    JOIN compliance_assets a ON a.id = r.asset_id
    WHERE r.checks::text NOT LIKE '%unknown%'
      AND r.checks::text LIKE '%uptime%'
    LIMIT 10
""")
for row in cur.fetchall():
    checks = row["checks"]
    if isinstance(checks, str): checks = json.loads(checks)
    for c in checks:
        if c.get("name") == "uptime":
            print(f"{row['hostname']:30s}  ip={row['ip_address']}  uptime_check={c}")
conn.close()
