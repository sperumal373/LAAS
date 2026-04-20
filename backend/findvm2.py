import requests, urllib3
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
r = s.post("https://172.17.168.212/api/session", auth=("administrator@vsphere.local", "Sdxdc@168-212"), timeout=10)
s.headers["vmware-api-session-id"] = r.text.strip('"')

# Search all VMs with "training" in name
r2 = s.get("https://172.17.168.212/api/vcenter/vm")
vms = r2.json()
matches = [v for v in vms if "training" in v.get("name","").lower()]
print(f"Total VMs: {len(vms)}, 'training' matches: {len(matches)}")
for v in matches:
    print(f"  {v['name']}  vm={v['vm']}  power={v['power_state']}")
