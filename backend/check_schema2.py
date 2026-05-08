import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect(r'C:\caas-dashboard\backend\caas.db')
# Check settings table for vcenter data
cols = c.execute("PRAGMA table_info(settings)").fetchall()
print('settings cols:', [r[1] for r in cols])
rows = c.execute("SELECT * FROM settings WHERE key LIKE '%vcenter%' OR key LIKE '%vc%' LIMIT 5").fetchall()
print('settings vc rows:', rows)
# Check bm_servers
cols2 = c.execute("PRAGMA table_info(bm_servers)").fetchall()
print('bm_servers cols:', [r[1] for r in cols2])
sample = c.execute("SELECT * FROM bm_servers LIMIT 2").fetchall()
print('bm_servers sample:', sample)
