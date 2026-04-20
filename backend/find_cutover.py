import requests, urllib3, re
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"
r2 = s.get("https://172.16.146.117/app.689739f824a9d803ef40.js", timeout=30)
txt = r2.text

# Search for cutover/start/action related API calls
for pattern in [r'plansV2\}[^"]*?/[^"]*?"', r'\.post\([^)]*plan[^)]*\)', r'cutover[^}]{0,300}', r'/start"[^}]{0,200}']:
    matches = re.findall(pattern, txt, re.IGNORECASE)
    for m in matches[:5]:
        print(f"--- {m[:300]}\n")
