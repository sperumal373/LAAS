import requests, urllib3, json
urllib3.disable_warnings()

# Try different creds for Prism
PRISM = "https://172.16.144.15:9440"
creds = [("admin","Wipro@123"), ("admin","Nutanix.123"), ("admin","nutanix/4u"), ("nutanix","Wipro@123")]
s = requests.Session()
s.verify = False

for u,p in creds:
    r = s.get(f"{PRISM}/api/nutanix/v2.0/cluster/", auth=(u,p))
    print(f"  {u}/{p[:4]}***: {r.status_code}")
    if r.status_code == 200:
        c = r.json()
        print(f"  Cluster: {c.get('name')}")
        # Now search VMs
        r2 = s.get(f"{PRISM}/api/nutanix/v2.0/vms/?search_string=sdxdclrhel8-66", auth=(u,p))
        if r2.status_code == 200:
            vms = r2.json().get("entities",[])
            print(f"  VMs found: {len(vms)}")
            for v in vms:
                print(f"    {v.get('name')} power={v.get('power_state')} uuid={v.get('uuid')}")
        break
