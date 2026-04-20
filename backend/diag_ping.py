import psycopg2, psycopg2.extras, ipam_pg

conn = psycopg2.connect(host='127.0.0.1', port=5433, dbname='caas_dashboard',
    user='caas_app', password='CaaS@App2024#',
    cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

cur.execute("SELECT id, vlan_id, subnet FROM ipam_vlans WHERE vlan_id=1263")
vlan = dict(cur.fetchone())
print('VLAN:', vlan)

cur.execute("SELECT ping_status, COUNT(*) as cnt FROM ipam_ips WHERE vlan_id=%s GROUP BY ping_status", (vlan['id'],))
for r in cur.fetchall():
    print('  ping_status dist:', dict(r))

# Check first 5 IPs
cur.execute("SELECT ip_address, status, ping_status FROM ipam_ips WHERE vlan_id=%s ORDER BY inet(ip_address) LIMIT 5", (vlan['id'],))
for r in cur.fetchall():
    print('  ip:', dict(r))

conn.close()
print()
print("--- Now running ping_and_save on VLAN", vlan['id'], "---")
# Only ping first 3 IPs to test quickly
cur2 = psycopg2.connect(host='127.0.0.1', port=5433, dbname='caas_dashboard',
    user='caas_app', password='CaaS@App2024#',
    cursor_factory=psycopg2.extras.RealDictCursor).cursor()

# test ping_ip directly
r1 = ipam_pg.ping_ip('172.17.63.1')
r2 = ipam_pg.ping_ip('172.17.63.2')
print("Direct ping 172.17.63.1:", r1)
print("Direct ping 172.17.63.2:", r2)
