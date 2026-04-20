import requests, urllib3
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
r = s.post("https://172.17.168.212/api/session", auth=("administrator@vsphere.local", "Sdxdc@168-212"), timeout=10)
s.headers["vmware-api-session-id"] = r.text.strip('"')

# Search exact name
r2 = s.get("https://172.17.168.212/api/vcenter/vm?names=sdxdcwtraining1")
print(f"Exact: {r2.status_code} {r2.text[:300]}")

# Try partial search
r3 = s.get("https://172.17.168.212/api/vcenter/vm?names=sdxdcwtraining")
print(f"Partial: {r3.status_code} {r3.text[:300]}")

# Broader
r4 = s.get("https://172.17.168.212/api/vcenter/vm?filter.names.1=sdxdcwtraining1&filter.names.2=SDxDCWTraining1")
print(f"Case variants: {r4.status_code} {r4.text[:300]}")
