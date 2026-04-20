import sys, os, sqlite3
sys.path.insert(0, r'C:\caas-dashboard\backend')
os.chdir(r'C:\caas-dashboard\backend')
from dotenv import load_dotenv
load_dotenv(r'C:\caas-dashboard\backend\.env')

import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host=os.getenv('PG_HOST','127.0.0.1'),
    port=int(os.getenv('PG_PORT','5433')),
    dbname=os.getenv('PG_DB','caas_dashboard'),
    user=os.getenv('PG_USER','caas_app'),
    password=os.getenv('PG_PASS','CaaS@App2024#'),
    cursor_factory=RealDictCursor
)
cur = conn.cursor()

print("=== Current CMDB breakdown ===")
cur.execute("SELECT sys_class_name, source_platform, COUNT(*) as cnt FROM cmdb_ci GROUP BY sys_class_name, source_platform ORDER BY cnt DESC")
rows = cur.fetchall()
total = 0
for r in rows:
    cls = r['sys_class_name']
    plat = r['source_platform']
    cnt = r['cnt']
    print(f"  {cls:35s} | {plat:15s} | {cnt}")
    total += cnt
print(f"  TOTAL: {total}")

conn.close()

print()
print("=== Storage arrays in SQLite ===")
dbconn = sqlite3.connect(r'C:\caas-dashboard\backend\caas.db')
dbconn.row_factory = sqlite3.Row
dbcur = dbconn.cursor()
dbcur.execute("SELECT id, name, host, type, username FROM storage_arrays")
for r in dbcur.fetchall():
    print(f"  id={r['id']} name={r['name']} host={r['host']} type={r['type']}")
dbconn.close()

print()
print("=== storage_client.list_arrays() ===")
from storage_client import list_arrays
arrays = list_arrays()
print(f"Total storage arrays: {len(arrays)}")
for a in arrays:
    print(f"  id={a.get('id')} name={a.get('name')} host={a.get('host')} type={a.get('type')}")
