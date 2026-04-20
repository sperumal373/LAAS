import requests, urllib3, re
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# Get UI HTML
r2 = s.get("https://172.16.146.117/api/v2", timeout=10)
scripts = re.findall(r'src="/(app\.[^"]+)"', r2.text)
print(f"Scripts found: {scripts}")
if scripts:
    r3 = s.get(f"https://172.16.146.117/{scripts[0]}", timeout=30)
    print(f"JS size: {len(r3.text)}")
    # Find cutover
    for m in re.finditer(r'cutover', r3.text, re.IGNORECASE):
        ctx = r3.text[max(0,m.start()-80):m.end()+80]
        print(f"  ...{ctx}...")
        print()
