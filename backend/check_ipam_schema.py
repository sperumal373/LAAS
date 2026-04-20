import psycopg2, psycopg2.extras
conn = psycopg2.connect(host='127.0.0.1',port=5433,dbname='caas_dashboard',
    user='caas_app',password='CaaS@App2024#',
    cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='snap_ipam_summary' ORDER BY ordinal_position")
cols = cur.fetchall()
print("snap_ipam_summary columns:")
for r in cols: print(" ", dict(r))
cur.execute("SELECT COUNT(*) FROM snap_ipam_summary")
print("rows:", cur.fetchone()['count'])
# Also check snapshot_runs
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='snapshot_runs' ORDER BY ordinal_position")
print("\nsnapshot_runs columns:", [r['column_name'] for r in cur.fetchall()])
conn.close()
