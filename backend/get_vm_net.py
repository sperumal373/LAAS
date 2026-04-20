import requests, urllib3, json
urllib3.disable_warnings()
VC = "https://172.17.168.212"
s = requests.Session()
s.verify = False
r = s.post(f"{VC}/api/session", auth=("administrator@vsphere.local", "Sdxdc@168-212"), timeout=10)
s.headers["vmware-api-session-id"] = r.text.strip('"')

# Get NIC detail
r2 = s.get(f"{VC}/api/vcenter/vm/vm-268873/hardware/ethernet/4000")
print(json.dumps(r2.json(), indent=2))
