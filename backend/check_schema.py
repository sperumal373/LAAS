import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect(r'C:\caas-dashboard\backend\caas.db')
rows = c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print('TABLES:', [r[0] for r in rows])
for t in ['vcenters','vcenter_connections','vc_connections']:
    try:
        cols = c.execute(f"PRAGMA table_info({t})").fetchall()
        if cols:
            print(f'{t} cols:', [r[1] for r in cols])
            sample = c.execute(f"SELECT * FROM {t} LIMIT 2").fetchall()
            print(f'{t} sample:', sample)
    except: pass
