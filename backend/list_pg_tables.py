import psycopg2, os
from dotenv import load_dotenv
load_dotenv(r'c:\caas-dashboard\backend\.env')
conn = psycopg2.connect(
    host=os.getenv('PG_HOST','127.0.0.1'),
    port=int(os.getenv('PG_PORT','5433')),
    dbname=os.getenv('PG_DB','caas_dashboard'),
    user=os.getenv('PG_USER','caas_app'),
    password=os.getenv('PG_PASS','CaaS@App2024#')
)
cur = conn.cursor()
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
print("=== PostgreSQL tables ===")
for r in cur.fetchall():
    print(' ', r[0])
conn.close()
