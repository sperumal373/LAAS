import sqlite3, json
db = sqlite3.connect("C:/caas-dashboard/backend/caas.db")
db.row_factory = sqlite3.Row
row = db.execute("SELECT event_log FROM migration_plans WHERE id=13").fetchone()
logs = json.loads(row["event_log"] or "[]")
for l in logs:
    msg = l.get("message","")[:150]
    ts = l.get("timestamp","")
    print(f"{ts}  {msg}")
