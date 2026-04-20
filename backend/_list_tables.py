import sqlite3
conn = sqlite3.connect("caas.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print([r[0] for r in cur.fetchall()])
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%aws%'")
print("AWS tables:", [r[0] for r in cur.fetchall()])
