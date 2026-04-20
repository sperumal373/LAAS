import sqlite3, json
db = sqlite3.connect("C:/caas-dashboard/backend/caas.db")
row = db.execute("SELECT status, progress, event_log FROM migration_plans WHERE id=13").fetchone()
print(f"Status: {row[0]}  Progress: {row[1]}")
logs = json.loads(row[2] or "[]")
print(f"Log entries: {len(logs)}")
for l in logs[-10:]:
    print(f"  {l.get('ts','')}  {l.get('msg','')[:150]}")
