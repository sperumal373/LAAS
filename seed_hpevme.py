import sqlite3, json
conn = sqlite3.connect(r'C:\caas-dashboard\backend\caas.db')
conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
hosts = [{"id": "1", "host": "172.17.65.80", "name": "HPE VME", "username": "user1", "password": "Wipro@123"}]
conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("hpevme_hosts", json.dumps(hosts)))
conn.commit()
conn.close()
print("HPE VME host seeded OK")
