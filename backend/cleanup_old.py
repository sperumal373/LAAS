import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# Cancel LaaS-laas-20
uuid = "a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"
print("Cancelling LaaS-laas-20...")
rc = s.post(f"https://172.16.146.117/move/v2/plans/{uuid}/cancel", json=None, timeout=30)
print(f"Cancel: {rc.status_code} {rc.text[:200]}")

# Also check/cancel other stuck LaaS plans
for name, uid in [("LaaS-laastest-14", "ece9a675-ed90-40ba-9d14-4a7c9b29ec2e"),
                   ("LaaS-Test2026-13", "29c8edc7-c4c4-4f71-a564-b3869c3df8c1")]:
    r2 = s.get(f"https://172.16.146.117/move/v2/plans/{uid}", timeout=10)
    d = r2.json()
    state = d.get("MetaData",{}).get("StateString","")
    print(f"\n{name}: {state}")
    if "Completed" not in state:
        rc2 = s.post(f"https://172.16.146.117/move/v2/plans/{uid}/cancel", json=None, timeout=30)
        print(f"  Cancel: {rc2.status_code} {rc2.text[:200]}")
