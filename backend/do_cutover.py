import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"
print(f"Logged in, token: {token[:20]}...")

# List plans to find ones in ReadyToCutover
r2 = s.post("https://172.16.146.117/move/v2/plans/list", json={}, timeout=15)
plans = r2.json()
for p in plans.get("Entities", []):
    name = p.get("Spec",{}).get("Name","")
    state = p.get("Status",{}).get("Status","")
    uuid = p.get("MetaData",{}).get("UUID","")
    print(f"Plan: {name} | State: {state} | UUID: {uuid}")
    
    if "ReadyToCutover" in state or "InProgress" in state:
        print(f"  >> Attempting cutover on {name}...")
        rc = s.post(f"https://172.16.146.117/move/v2/plans/{uuid}/cutover", json=None, timeout=30)
        print(f"  >> Response: {rc.status_code} {rc.text[:300]}")
