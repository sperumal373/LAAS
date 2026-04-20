import ipam_pg, psycopg2, psycopg2.extras
ipam_pg.init_ipam_schema()
print("Schema + seed done")
conn = psycopg2.connect(host='127.0.0.1',port=5433,dbname='caas_dashboard',
    user='caas_app',password='CaaS@App2024#',
    cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute("SELECT vlan_id, name, subnet FROM ipam_vlans WHERE vlan_id IN (1301,1302) AND deleted_at IS NULL ORDER BY vlan_id")
rows = cur.fetchall()
conn.close()
if rows:
    for r in rows: print(dict(r))
else:
    print("VLANs 1301/1302 not found - may already be soft-deleted or seed skipped")
