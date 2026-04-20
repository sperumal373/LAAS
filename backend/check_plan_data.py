import sqlite3, json
db = sqlite3.connect(r"C:\caas-dashboard\backend\caas.db")
row = db.execute("SELECT * FROM migration_plans WHERE id=13").fetchone()
cols = [d[0] for d in db.execute("SELECT * FROM migration_plans WHERE id=13").description]
for c, v in zip(cols, row):
    print(f"{c}: {v}")
