import sqlite3
db = sqlite3.connect("C:/caas-dashboard/backend/caas.db")
# Update plan 14 to show 85% with ReadyToCutover message
db.execute("UPDATE migration_plans SET progress=85 WHERE id=14 AND status='executing'")
# Also fix plan 13
db.execute("UPDATE migration_plans SET progress=85 WHERE id=13 AND status='executing'")
db.commit()
print("Updated progress to 85% for ReadyToCutover plans")
