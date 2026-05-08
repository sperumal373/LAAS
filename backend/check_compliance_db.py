import psycopg2, psycopg2.extras, json
conn = psycopg2.connect(host="127.0.0.1",port=5433,dbname="caas_dashboard",
    user="caas_app",password="CaaS@App2024#",cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute("SELECT * FROM compliance_assets LIMIT 1")
row = dict(cur.fetchone())
print("SAMPLE ROW:")
for k,v in row.items(): print(f"  {k}: {repr(v)[:80]}")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='compliance_assets' ORDER BY ordinal_position")
cols = [r["column_name"] for r in cur.fetchall()]
print("\nCOLUMNS:", cols)

# check latest result row
cur.execute("SELECT * FROM compliance_results LIMIT 1")
r2 = cur.fetchone()
if r2:
    r2 = dict(r2)
    print("\nRESULT SAMPLE:")
    for k,v in r2.items():
        if k == "checks": print(f"  checks[0]: {json.loads(v)[0] if isinstance(v,str) else v[0] if v else 'empty'}")
        else: print(f"  {k}: {repr(v)[:80]}")
conn.close()
