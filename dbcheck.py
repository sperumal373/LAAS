import sqlite3
c=sqlite3.connect("caas.db")
print("TABLES:")
for r in c.execute("SELECT name FROM sqlite_master WHERE type=?",("table",)).fetchall():
    print(" ",r[0])
# try vcenter-like tables
for t in ["vmware_connections","vcenter_connections","connections","vmware","vc_connections"]:
    try:
        rows=c.execute(f"SELECT * FROM {t} LIMIT 3").fetchall()
        cols=[d[0] for d in c.execute(f"SELECT * FROM {t} LIMIT 0").description or []]
        print(f"TABLE {t}: cols={cols}, rows={len(rows)}")
        for r in rows: print("  ",dict(zip(cols,r)))
    except: pass

