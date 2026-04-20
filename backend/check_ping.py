import psycopg2, psycopg2.extras
conn = psycopg2.connect(host='127.0.0.1', port=5433, dbname='caas_dashboard',
    user='caas_app', password='CaaS@App2024#',
    cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

cur.execute("""
    SELECT v.vlan_id, v.subnet,
        SUM(CASE WHEN i.ping_status='up'      THEN 1 ELSE 0 END) AS ping_up,
        SUM(CASE WHEN i.ping_status='down'    THEN 1 ELSE 0 END) AS ping_down,
        SUM(CASE WHEN i.ping_status='unknown' THEN 1 ELSE 0 END) AS ping_unknown
    FROM ipam_vlans v JOIN ipam_ips i ON i.vlan_id=v.id
    GROUP BY v.id, v.vlan_id, v.subnet ORDER BY v.vlan_id LIMIT 10
""")
for r in cur.fetchall():
    print(dict(r))
conn.close()
