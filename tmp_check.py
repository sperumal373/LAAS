import psycopg2
conn = psycopg2.connect(host="127.0.0.1", port=5433, dbname="caas_dashboard", user="caas_app", password="CaaS@App2024#")
cur = conn.cursor()
cur.execute("SELECT correlation_id FROM cmdb_ci WHERE source_platform='asset_mgmt' ORDER BY correlation_id LIMIT 10")
print("Sample asset_mgmt correlation_ids in DB:")
for r in cur.fetchall():
    print("  " + r[0])
cur.execute("SELECT COUNT(*) FROM cmdb_ci WHERE source_platform='asset_mgmt'")
print("Total asset_mgmt in DB: " + str(cur.fetchone()[0]))
conn.close()

