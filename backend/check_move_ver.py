import requests, urllib3
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# Check version
for path in ["/move/v2/about", "/move/v2/version", "/move/v2/health"]:
    resp = s.get(f"https://172.16.146.117{path}", timeout=10)
    print(f"GET {path} -> {resp.status_code}: {resp.text[:300]}")

# Find a plan that's actually InProgress/ReadyToCutover
# Try the known ones
for uid in ["a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"]:
    resp = s.get(f"https://172.16.146.117/move/v2/plans/{uid}", timeout=10)
    import json
    d = resp.json()
    # Print full status
    print(f"\nPlan {uid}:")
    print(json.dumps(d, indent=2)[:1000])

# Try start a new test - first check what actions ARE available
for action in ["start","cutover","cancel","suspend","resume","abort","pause","retry","complete"]:
    resp = s.post(f"https://172.16.146.117/move/v2/plans/{uid}/{action}", json=None, timeout=5)
    print(f"POST .../{action} -> {resp.status_code}: {resp.text[:100]}")
