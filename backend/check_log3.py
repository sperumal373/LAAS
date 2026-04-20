import sqlite3, json
db = sqlite3.connect(r"C:\caas-dashboard\backend\caas.db")
cur = db.execute("SELECT event_log FROM migration_plans WHERE id=13")
row = cur.fetchone()
if row and row[0]:
    logs = json.loads(row[0])
    print(f"Total log entries: {len(logs)}")
    for i, l in enumerate(logs):
        print(f"[{i}] {l}")
else:
    print("No event_log data")
