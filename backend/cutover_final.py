import requests, urllib3, re, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# Get app JS and find performAction
r2 = s.get("https://172.16.146.117/app.689739f824a9d803ef40.js", timeout=30)
txt = r2.text

# Search for performAction function and the API call it makes
for pattern in [r'performAction.*?/move/v2', r'action.*?/move/v2/plans.*?(?:cutover|start|action)', r'CUTOVER.*?\.(?:post|put|patch)\(', r'\.(?:post|put)\([^)]*plans[^)]*(?:cutover|action|start)']:
    matches = re.findall(pattern, txt)
    for m in matches[:3]:
        print(f"Pattern match: ...{m[:200]}...")

# Also search for the specific API helper
for pattern in [r'performAction[^}]{0,500}', r'CUTOVER[^}]{0,300}url']:
    matches = re.findall(pattern, txt)
    for m in matches[:2]:
        print(f"\n=== {m[:400]} ===")
