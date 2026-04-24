import sqlite3
conn = sqlite3.connect(r'C:\caas-dashboard\backend\caas.db')
tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)
for t in tables:
    if 'hv' in t.lower() or 'hyper' in t.lower() or 'host' in t.lower():
        print(f"\n{t}:")
        rows = conn.execute(f"SELECT * FROM [{t}]").fetchall()
        cols = [d[0] for d in conn.execute(f"SELECT * FROM [{t}]").description]
        print("  Cols:", cols)
        for r in rows:
            d = dict(zip(cols, r))
            if 'password' in d: d['password'] = '***'
            if 'pwd' in d: d['pwd'] = '***'
            print(" ", d)
