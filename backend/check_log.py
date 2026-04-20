import sqlite3, json
db = sqlite3.connect("C:/caas-dashboard/backend/caas.db")
db.row_factory = sqlite3.Row
row = db.execute("SELECT event_log, status, progress FROM migration_plans WHERE id=13").fetchone()
print(f"Status: {row['status']}  Progress: {row['progress']}")
logs = json.loads(row["event_log"] or "[]")
for l in logs[:15]:
    print(f"  {l.get('timestamp','')}  {l.get('message','')[:120]}")
