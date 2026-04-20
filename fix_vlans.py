"""
fix_vlans.py – Clean up bad octets and reseed DC VLANs 1271-1299 with proper subnets
Logic: DC VLANs use 172.17.x.0/24 where x cycles through available octets.
1263->63, 1264->64, ... 1270->70, 1271->71, ..., 1299->99  (mod 256 or wrap)
Actually for VLANs >1255, mod 256 wraps. The real network is:
  VLAN 1271 -> 172.17.71.0/24 (271 mod 256 = 15, but logical is 71)
  VLAN 1280 -> 172.17.80.0/24 (but 80 is already VLAN1180)

The user's VLANs for DC are 1263-1299. The subnets should be:
  Last 2 digits: VLAN1263 -> 172.17.63.0/24
                 VLAN1264 -> 172.17.64.0/24
                 ...
                 VLAN1270 -> 172.17.70.0/24
                 VLAN1271 -> 172.17.71.0/24
                 ...
                 VLAN1299 -> 172.17.99.0/24  (last two digits, but 63..99)
So all from 1263..1299 use octet = (vlan_id - 1200).
  1263 - 1200 = 63 ✓, 1270 - 1200 = 70 ✓, 1299 - 1200 = 99 ✓
"""
import sys
sys.path.insert(0, r'c:\caas-dashboard\backend')
import ipam_pg

def _get_pg():
    import psycopg2, psycopg2.extras, os
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(r'c:\caas-dashboard\backend') / ".env")
    return psycopg2.connect(
        host=os.getenv("PG_HOST","127.0.0.1"),
        port=int(os.getenv("PG_PORT","5433")),
        dbname=os.getenv("PG_DB","caas_dashboard"),
        user=os.getenv("PG_USER","caas_app"),
        password=os.getenv("PG_PASS","CaaS@App2024#"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

# Step 1: Delete all DC VLANs 1271-1299 (they have bad IPs seeded)
print("Step 1: Delete bad DC VLANs 1271-1299...")
conn = _get_pg()
conn.autocommit = False
cur = conn.cursor()
cur.execute("SELECT id, vlan_id, subnet FROM ipam_vlans WHERE site='DC' AND vlan_id BETWEEN 1271 AND 1299")
bad = cur.fetchall()
for r in bad:
    cur.execute("DELETE FROM ipam_ips WHERE vlan_id=%s", (r['id'],))
    cur.execute("DELETE FROM ipam_vlans WHERE id=%s", (r['id'],))
    print(f"  Deleted VLAN{r['vlan_id']} {r['subnet']}")
conn.commit()

# Also fix DR: 1207-1209 have octets 207-209 which are valid. But 1202-1206 already existed with correct octets.
# Check DR:
cur.execute("SELECT id, vlan_id, subnet FROM ipam_vlans WHERE site='DR' ORDER BY vlan_id")
dr = cur.fetchall()
print(f"\nDR VLANs: {[(r['vlan_id'], r['subnet']) for r in dr]}")
conn.close()

# Step 2: Reseed DC VLANs 1263-1299 with correct subnets
print("\nStep 2: Reseed DC VLANs 1263-1299 with correct subnets...")
for vid in range(1263, 1300):
    octet = vid - 1200  # 1263->63, 1264->64, ..., 1299->99
    subnet = f"172.17.{octet}.0/24"
    gateway = f"172.17.{octet}.1"
    try:
        row = ipam_pg.create_vlan(dict(
            site="DC", vlan_id=vid, name=f"VLAN{vid}",
            subnet=subnet, gateway=gateway,
            description=f"DC VLAN {vid}"
        ))
        print(f"  ADDED  DC VLAN{vid} {subnet}")
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"  EXISTS DC VLAN{vid} {subnet} (skipped)")
        else:
            print(f"  ERROR  DC VLAN{vid}: {e}")

# Step 3: Seed DR VLANs 1202-1209 with correct subnets
print("\nStep 3: Seed DR VLANs 1202-1209...")
for vid in range(1202, 1210):
    octet = vid - 1000  # 1202->202 (too large) - use vid-1000 = 202 is invalid
    # DR uses 172.16.x.0/24: VLAN 1202 -> 172.16.2.0/24 (last digit pattern)
    # From the image: 1202->172.16.2.0/24, 1203->172.16.3.0/24
    # So octet = vid - 1200: 1202->2, 1203->3, ..., 1209->9
    octet = vid - 1200  # 2,3,4,5,6,7,8,9
    subnet = f"172.16.{octet}.0/24"
    gateway = f"172.16.{octet}.1"
    try:
        row = ipam_pg.create_vlan(dict(
            site="DR", vlan_id=vid, name=f"VLAN{vid}",
            subnet=subnet, gateway=gateway,
            description=f"DR VLAN {vid}"
        ))
        print(f"  ADDED  DR VLAN{vid} {subnet}")
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            print(f"  EXISTS DR VLAN{vid} {subnet} (skipped)")
        else:
            print(f"  ERROR  DR VLAN{vid}: {e}")

# Step 4: Final count
vlans = ipam_pg.list_vlans()
dc_v = [v for v in vlans if v['site']=='DC']
dr_v = [v for v in vlans if v['site']=='DR']
print(f"\nFinal: {len(vlans)} VLANs  (DC={len(dc_v)}, DR={len(dr_v)})")
print(f"DC range: {min(v['vlan_id'] for v in dc_v)} - {max(v['vlan_id'] for v in dc_v)}")
print(f"DR range: {min(v['vlan_id'] for v in dr_v)} - {max(v['vlan_id'] for v in dr_v)}")
