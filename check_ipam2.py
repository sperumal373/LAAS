import sys
sys.path.insert(0, r'c:\caas-dashboard\backend')
import ipam_pg

vlans = ipam_pg.list_vlans()
print(f'Total VLANs: {len(vlans)}')
for v in vlans[:8]:
    site = v["site"]
    vid = v["vlan_id"]
    sn = v["subnet"]
    ti = v["total_ips"]
    ui = v["used_ips"]
    fi = v["free_ips"]
    print(f'  {site} VLAN{vid} {sn} - total={ti} used={ui} free={fi}')
s = ipam_pg.get_summary()
print(f'Summary: {s}')
