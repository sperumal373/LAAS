import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.auth = ("pranesh", "Thinkpad@321")
PRISM = "https://172.16.144.15:9440"

r = s.get(f"{PRISM}/api/nutanix/v2.0/vms/?search_string=sdxdclrhel8-66")
print(f"Status: {r.status_code}")
if r.status_code == 200:
    vms = r.json().get("entities", [])
    print(f"VMs found: {len(vms)}")
    for v in vms:
        print(f"  Name: {v.get('name')}  Power: {v.get('power_state')}  UUID: {v.get('uuid')}")
else:
    print(r.text[:300])

# Also list all VMs with sdxdcl in name
r2 = s.get(f"{PRISM}/api/nutanix/v2.0/vms/?search_string=sdxdcl")
if r2.status_code == 200:
    vms2 = r2.json().get("entities", [])
    print(f"\nAll sdxdcl* VMs: {len(vms2)}")
    for v in vms2:
        print(f"  {v.get('name')}  power={v.get('power_state')}")
