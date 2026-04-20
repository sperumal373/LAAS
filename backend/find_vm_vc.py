# Query vCenter REST API for VM UUID
import requests, urllib3, json
urllib3.disable_warnings()

VC = "https://172.17.168.212"
USER = "sdxtest\\yogesh"
PASS = "Wipro@12345"

s = requests.Session()
s.verify = False

# Try vSphere REST API login
try:
    r = s.post(f"{VC}/api/session", auth=(USER, PASS), timeout=10)
    print(f"vSphere API login: {r.status_code}")
    if r.status_code == 200:
        token = r.json() if r.text.startswith('"') else r.text.strip('"')
        s.headers["vmware-api-session-id"] = token
        # Search for VM
        r2 = s.get(f"{VC}/api/vcenter/vm?names=sdxdclrhel8-66")
        print(f"VM search: {r2.status_code}")
        print(r2.text[:500])
except Exception as ex:
    print(f"vSphere API error: {ex}")

# Try older SOAP-style REST
try:
    r = s.post(f"{VC}/rest/com/vmware/cis/session", auth=(USER, PASS), timeout=10)
    print(f"\nREST login: {r.status_code}")
    if r.status_code == 200:
        token = r.json().get("value", "")
        s.headers["vmware-api-session-id"] = token
        r2 = s.get(f"{VC}/rest/vcenter/vm?filter.names=sdxdclrhel8-66")
        print(f"VM: {r2.status_code}")
        print(r2.text[:500])
except Exception as ex:
    print(f"REST error: {ex}")
