import requests, urllib3, json
urllib3.disable_warnings()
VC = "https://172.17.168.212"
s = requests.Session()
s.verify = False
r = s.post(f"{VC}/api/session", auth=("administrator@vsphere.local", "Sdxdc@168-212"), timeout=10)
token = r.text.strip('"')
s.headers["vmware-api-session-id"] = token

# Get VM detail including identity (instance UUID)
r2 = s.get(f"{VC}/api/vcenter/vm/vm-268873")
print(json.dumps(r2.json(), indent=2)[:2000])
