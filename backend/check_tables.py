import sqlite3
c = sqlite3.connect(r'C:\caas-dashboard\backend\caas.db')
c.row_factory = sqlite3.Row

tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("ALL tables:", tables)
