import psycopg2, os
from dotenv import load_dotenv
load_dotenv(r"C:\caas-dashboard\backend\.env")

conn = psycopg2.connect(host="127.0.0.1", port=5433, dbname="caas_dashboard", user="caas_app", password=os.getenv("PG_PASSWORD","caas_secure_pass"))
cur = conn.cursor()

cur.execute("SELECT source_platform, COUNT(*) FROM cmdb_ci GROUP BY source_platform ORDER BY COUNT(*) DESC")
print("All CIs by platform:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

cur.execute("SELECT COUNT(*) FROM cmdb_ci")
print("TOTAL:", cur.fetchone()[0])
conn.close()
