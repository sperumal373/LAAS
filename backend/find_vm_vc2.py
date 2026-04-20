import requests, urllib3, json
urllib3.disable_warnings()
VC = "https://172.17.168.212"
USER = "administrator@vsphere.local"
PASS = "Sdxdc@168-212"
s = requests.Session()
s.verify = False
r = s.post(f"{VC}/api/session", auth=(USER, PASS), timeout=10)
print(f"Login: {r.status_code}")
if r.status_code in (200, 201):
    token = r.text.strip('"')
    s.headers["vmware-api-session-id"] = token
    r2 = s.get(f"{VC}/api/vcenter/vm?names=sdxdclrhel8-66")
    print(f"VM search: {r2.status_code}")
    print(r2.text[:1000])
