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

# Find plansV2 definition
for m in re.findall(r'plansV2["\s]*:["\s]*[^,}"]+', txt):
    print(f"plansV2: {m}")

# Also find plansListV2
for m in re.findall(r'plansListV2["\s]*:["\s]*[^,}"]+', txt):
    print(f"plansListV2: {m}")

# Find all route constants
for m in re.findall(r'plans[A-Za-z0-9]*["\s]*:["\s]*/[^,}"]+', txt):
    print(f"route: {m}")
