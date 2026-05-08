import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
c = sqlite3.connect(r'C:\caas-dashboard\backend\caas.db')
# Find where vcenters are stored
rows = c.execute("SELECT * FROM settings LIMIT 20").fetchall()
print('ALL settings:')
for r in rows:
    print(' ', r[0], '=', str(r[1])[:120])
