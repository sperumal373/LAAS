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

# Find postMigration function definition
for pattern in [r'postMigration[^{]*\{[^}]{0,500}', r'performMigrationAction[^{]*\{[^}]{0,800}']:
    matches = re.findall(pattern, txt)
    for m in matches[:3]:
        print(f"=== {m[:500]} ===\n")

# Find the URL patterns for plans with actions
for pattern in [r'/move/v2/plans/[^"]*action[^"]*', r'plans/.*?/(?:start|cutover|action)"']:
    matches = re.findall(pattern, txt)
    for m in matches[:5]:
        print(f"URL: {m}")
