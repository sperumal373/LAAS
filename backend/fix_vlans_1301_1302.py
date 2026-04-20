import psycopg2, psycopg2.extras
conn = psycopg2.connect(host='127.0.0.1',port=5433,dbname='caas_dashboard',
    user='caas_app',password='CaaS@App2024#',
    cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

# Restore 1301 with correct subnet
cur.execute("""UPDATE ipam_vlans
    SET subnet='172.17.101.0/24', gateway='172.17.101.1',
        description='DC VLAN 1301', deleted_at=NULL, updated_at=NOW()
    WHERE vlan_id=1301""")

# Restore 1302 with correct subnet
cur.execute("""UPDATE ipam_vlans
    SET subnet='172.17.102.0/24', gateway='172.17.102.1',
        description='DC VLAN 1302', deleted_at=NULL, updated_at=NOW()
    WHERE vlan_id=1302""")

conn.commit()

# Seed IPs for each if empty
import ipam_pg
for vlan_id, subnet, gw in [(1301,'172.17.101.0/24','172.17.101.1'),
                              (1302,'172.17.102.0/24','172.17.102.1')]:
    cur.execute("SELECT id FROM ipam_vlans WHERE vlan_id=%s", (vlan_id,))
    row = cur.fetchone()
    if not row:
        print(f"VLAN {vlan_id} not found!")
        continue
    db_id = row['id']
    cur.execute("SELECT COUNT(*) FROM ipam_ips WHERE vlan_id=%s", (db_id,))
    cnt = cur.fetchone()['count']
    if cnt == 0:
        ipam_pg._seed_ips_for_vlan(cur, db_id, subnet, gw)
        conn.commit()
        print(f"Seeded {vlan_id}: {subnet} ({254} IPs)")
    else:
        # Update IPs to correct subnet if they were wrong
        cur.execute("DELETE FROM ipam_ips WHERE vlan_id=%s", (db_id,))
        ipam_pg._seed_ips_for_vlan(cur, db_id, subnet, gw)
        conn.commit()
        print(f"Re-seeded {vlan_id}: {subnet}")

cur.execute("SELECT vlan_id, subnet, deleted_at FROM ipam_vlans WHERE vlan_id IN (1301,1302)")
for r in cur.fetchall(): print(dict(r))
conn.close()
print("Done")
