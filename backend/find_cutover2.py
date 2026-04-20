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

# Find postMigration function - search around it
idx = txt.find("postMigration")
while idx != -1:
    print(f"=== offset {idx}: {txt[max(0,idx-100):idx+300]}\n")
    idx = txt.find("postMigration", idx+1)
    if idx > 0 and idx < len(txt):
        continue
    break
