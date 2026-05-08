import sqlite3
c = sqlite3.connect(r'C:\caas-dashboard\backend\caas.db')
c.row_factory = sqlite3.Row

# Find vCenter table
tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
vc_tables = [t for t in tables if 'center' in t.lower() or t.lower().startswith('vc')]
print("VC-related tables:", vc_tables)

# Show columns of first vc table
for t in vc_tables[:2]:
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
    print(f"  {t} columns:", cols)
    rows = c.execute(f"SELECT * FROM {t} LIMIT 2").fetchall()
    for r in rows:
        print("   row:", dict(r))
