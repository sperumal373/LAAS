import sqlite3
db = sqlite3.connect("C:/caas-dashboard/backend/caas.db")
# Find plans that completed via simulation (check event_log for "simulated")
cur = db.execute("SELECT id, plan_name, event_log FROM migration_plans WHERE status='completed'")
for row in cur.fetchall():
    if "(simulated)" in (row[2] or ""):
        db.execute("UPDATE migration_plans SET status='failed', progress=0 WHERE id=?", (row[0],))
        print(f"  Plan {row[0]} ({row[1]}): marked FAILED (was fake simulation)")
db.commit()
print("Done")
