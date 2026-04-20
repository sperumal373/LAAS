import psycopg2, psycopg2.extras
conn = psycopg2.connect(host='127.0.0.1',port=5433,dbname='caas_dashboard',
    user='caas_app',password='CaaS@App2024#',
    cursor_factory=psycopg2.extras.RealDictCursor)
cur=conn.cursor()

# Check VLAN 1263 (db_id=1)
cur.execute("""
    SELECT v.vlan_id,
        SUM(CASE WHEN i.ping_status='up'      THEN 1 ELSE 0 END) AS up,
        SUM(CASE WHEN i.ping_status='down'    THEN 1 ELSE 0 END) AS down,
        SUM(CASE WHEN i.ping_status='unknown' THEN 1 ELSE 0 END) AS unknown
    FROM ipam_vlans v JOIN ipam_ips i ON i.vlan_id=v.id
    WHERE v.vlan_id=1263 GROUP BY v.vlan_id
""")
print("VLAN 1263 ping:", dict(cur.fetchone()))

# First 5 IPs of 1263
cur.execute("SELECT ip_address, ping_status FROM ipam_ips WHERE vlan_id=1 ORDER BY inet(ip_address) LIMIT 5")
for r in cur.fetchall(): print(" ", dict(r))

conn.close()
