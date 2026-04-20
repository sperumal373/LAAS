"""
seed_vlans.py – Add missing DC (1263-1299) and DR (1202-1209) VLANs to PostgreSQL
Skips any that already exist.
"""
import sys
sys.path.insert(0, r'c:\caas-dashboard\backend')
import ipam_pg

# Build full DC VLAN list 1263–1299
dc_vlans = []
for vid in range(1263, 1300):
    third_octet = vid - 1000  # 1263 -> 63, 1299 -> 299 (wrap doesn't matter, use mod)
    # Use vid last two/three digits for octet: 1263->63, 1270->70, 1299->99
    octet = vid % 1000  # last 3 digits = same as vid-1000 for 1263-1299
    subnet = f"172.17.{octet}.0/24"
    gateway = f"172.17.{octet}.1"
    dc_vlans.append(dict(
        site="DC", vlan_id=vid, name=f"VLAN{vid}",
        subnet=subnet, gateway=gateway,
        description=f"DC VLAN {vid}"
    ))

# Build full DR VLAN list 1202–1209
dr_vlans = []
for vid in range(1202, 1210):
    octet = vid % 1000  # 202,203,...209
    subnet = f"172.16.{octet}.0/24"
    gateway = f"172.16.{octet}.1"
    dr_vlans.append(dict(
        site="DR", vlan_id=vid, name=f"VLAN{vid}",
        subnet=subnet, gateway=gateway,
        description=f"DR VLAN {vid}"
    ))

all_vlans = dc_vlans + dr_vlans
added = 0
skipped = 0

for v in all_vlans:
    try:
        row = ipam_pg.create_vlan(v)
        print(f"  ADDED  {v['site']} VLAN{v['vlan_id']} {v['subnet']}")
        added += 1
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower() or "already exists" in str(e).lower():
            skipped += 1
        else:
            print(f"  ERROR  {v['site']} VLAN{v['vlan_id']}: {e}")

print(f"\nDone. Added={added}, Skipped={skipped}")

# Verify
vlans = ipam_pg.list_vlans()
dc_count = sum(1 for v in vlans if v['site'] == 'DC')
dr_count = sum(1 for v in vlans if v['site'] == 'DR')
print(f"Total VLANs: {len(vlans)}  (DC={dc_count}, DR={dr_count})")
