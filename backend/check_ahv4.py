import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.auth = ("pranesh", "Thinkpad@321")
PRISM = "https://172.16.144.15:9440"

r = s.post(f"{PRISM}/api/nutanix/v3/vms/list", json={"kind":"vm","filter":"vm_name==sdxdclrhel8-66","length":50})
print(f"Exact match: {r.status_code}")
if r.status_code == 200:
    entities = r.json().get("entities", [])
    print(f"Found: {len(entities)}")
    for e in entities:
        name = e.get("spec",{}).get("name","")
        power = e.get("status",{}).get("resources",{}).get("power_state","")
        cluster = e.get("status",{}).get("cluster_reference",{}).get("name","")
        print(f"  Name: {name}  Power: {power}  Cluster: {cluster}  UUID: {e.get('metadata',{}).get('uuid','')}")
else:
    print(r.text[:300])

# Broader search
r2 = s.post(f"{PRISM}/api/nutanix/v3/vms/list", json={"kind":"vm","filter":"vm_name=~sdxdclrhel8","length":50})
if r2.status_code == 200:
    entities2 = r2.json().get("entities", [])
    print(f"\nBroader sdxdclrhel8* : {len(entities2)}")
    for e in entities2:
        name = e.get("spec",{}).get("name","")
        power = e.get("status",{}).get("resources",{}).get("power_state","")
        cluster = e.get("status",{}).get("cluster_reference",{}).get("name","")
        print(f"  {name}  power={power}  cluster={cluster}")
