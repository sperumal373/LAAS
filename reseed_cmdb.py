"""
Seed / re-seed the CMDB table by running collect_all_cis().
Clears asset_mgmt and storage CIs first so old (collapsed) records are replaced.
"""
import sys, os
sys.path.insert(0, r'C:\caas-dashboard\backend')
os.chdir(r'C:\caas-dashboard\backend')

import psycopg2
from dotenv import load_dotenv
load_dotenv(r'C:\caas-dashboard\backend\.env')

PG = dict(
    host=os.getenv("PG_HOST", "127.0.0.1"),
    port=int(os.getenv("PG_PORT", 5433)),
    dbname=os.getenv("PG_DB", "caas_dashboard"),
    user=os.getenv("PG_USER", "caas_app"),
    password=os.getenv("PG_PASS", "CaaS@App2024#"),
)

conn = psycopg2.connect(**PG)
cur = conn.cursor()

# Delete the old (broken) asset_mgmt and storage entries so we start fresh for those
cur.execute("DELETE FROM cmdb_ci WHERE source_platform IN ('asset_mgmt', 'storage')")
deleted = cur.rowcount
conn.commit()
print(f"Deleted {deleted} old asset_mgmt/storage CIs")

cur.execute("SELECT COUNT(*) FROM cmdb_ci")
print(f"Remaining CIs before re-collect: {cur.fetchone()[0]}")
conn.close()

# Now run the full collection
from cmdb_client import collect_all_cis
result = collect_all_cis()
print(f"\nCollection result: {result}")

# Final count
conn = psycopg2.connect(**PG)
cur = conn.cursor()
cur.execute("SELECT source_platform, COUNT(*) FROM cmdb_ci GROUP BY source_platform ORDER BY COUNT(*) DESC")
print("\nFinal CMDB breakdown:")
total = 0
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")
    total += r[1]
print(f"GRAND TOTAL: {total}")
conn.close()
