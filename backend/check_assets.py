import sys, os, sqlite3
sys.path.insert(0, r'C:\caas-dashboard\backend')
os.chdir(r'C:\caas-dashboard\backend')
from dotenv import load_dotenv
load_dotenv(r'C:\caas-dashboard\backend\.env')

# Check SQLite
db_path = r'C:\caas-dashboard\backend\caas.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('SQLite tables:', tables)
for t in tables:
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    print(f'  {t}: {cur.fetchone()[0]} rows')
conn.close()

print()

# Check what asset_client.get_inventory returns  
from asset_client import get_inventory, DATA_DIR
from pathlib import Path
print('DATA_DIR:', DATA_DIR)
print('Files in data dir:')
for f in Path(DATA_DIR).iterdir():
    print(f'  {f.name}: {f.stat().st_size} bytes')

print()
# Try get_inventory if it exists
try:
    inv_dc = get_inventory('dc')
    print('DC inventory rows:', len(inv_dc.get('assets', inv_dc.get('items', []))))
    inv_dr = get_inventory('dr')
    print('DR inventory rows:', len(inv_dr.get('assets', inv_dr.get('items', []))))
except Exception as e:
    print('get_inventory error:', e)

# Check what api/assets/inventory returns
import psycopg2
from psycopg2.extras import RealDictCursor
try:
    pgconn = psycopg2.connect(
        host=os.getenv('PG_HOST','127.0.0.1'),
        port=int(os.getenv('PG_PORT','5433')),
        dbname=os.getenv('PG_DB','caas_dashboard'),
        user=os.getenv('PG_USER','caas_app'),
        password=os.getenv('PG_PASS','CaaS@App2024#'),
        cursor_factory=RealDictCursor
    )
    pgcur = pgconn.cursor()
    # Check if there's an assets table in PG
    pgcur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE '%asset%'")
    print('PG asset tables:', [r['tablename'] for r in pgcur.fetchall()])
    pgconn.close()
except Exception as e:
    print('PG error:', e)
