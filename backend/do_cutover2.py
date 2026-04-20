import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# Known plan UUID
plan_uuid = "a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"

# First check status
r1 = s.get(f"https://172.16.146.117/move/v2/plans/{plan_uuid}", timeout=15)
d = r1.json()
print(f"Plan: {d.get('Spec',{}).get('Name','')} | Status: {d.get('Status',{}).get('Status','')}")

# Try cutover
print("\nAttempting POST cutover...")
rc = s.post(f"https://172.16.146.117/move/v2/plans/{plan_uuid}/cutover", json=None, timeout=30)
print(f"Response: {rc.status_code} {rc.text[:500]}")
