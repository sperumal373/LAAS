import psycopg2, psycopg2.extras
conn = psycopg2.connect(host='127.0.0.1', port=5433, dbname='caas_dashboard', user='caas_app', password='CaaS@App2024#', cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()
cur.execute("SELECT id, vlan_id, subnet FROM ipam_vlans WHERE vlan_id=1263")
vlan = cur.fetchone()
print("VLAN:", dict(vlan))
vid = vlan['id']

# Check first 5 IPs
cur.execute("SELECT id, ip_address, ping_status FROM ipam_ips WHERE vlan_id=%s ORDER BY id LIMIT 5", (vid,))
for ip in cur.fetchall():
    print("  IP:", dict(ip))

# Now run actual ping_and_save on just 1 IP to test
import sys
sys.path.insert(0, r'c:\caas-dashboard\backend')
import ipam_pg

cur.execute("SELECT id FROM ipam_ips WHERE vlan_id=%s AND ip_address='172.17.63.1'", (vid,))
row = cur.fetchone()
ip_id = row['id']
print("\nRunning ping on 172.17.63.1 (id=%s)..." % ip_id)
results = ipam_pg.ping_and_save(vid, ip_ids=[ip_id])
print("Result:", results)

# Check updated status
cur.execute("SELECT ip_address, ping_status, ping_time FROM ipam_ips WHERE id=%s", (ip_id,))
print("After ping:", dict(cur.fetchone()))
conn.close()
