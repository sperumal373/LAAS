import sqlite3
db = sqlite3.connect("C:/caas-dashboard/backend/caas.db")
db.execute("UPDATE migration_plans SET status='approved', progress=0, event_log='[]', completed_at=NULL WHERE id=13")
db.commit()
print("Plan 13 reset to approved")
