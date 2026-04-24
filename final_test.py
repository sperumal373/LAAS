import requests
requests.packages.urllib3.disable_warnings()
s = requests.Session()
s.verify = False

# 1. Login
tok = s.post("https://localhost/api/auth/login", json={"username":"admin","password":"caas@2024"}).json()["token"]

# 2. Fetch /api/ansible/instances exactly as the frontend does
r = s.get("https://localhost/api/ansible/instances", headers={"Authorization": "Bearer " + tok})
print("Status:", r.status_code)
print("Content-Type:", r.headers.get("content-type"))
print("Body length:", len(r.text))

data = r.json()
instances = data.get("instances", [])
print("Total instances:", len(instances))
ok = [i for i in instances if i.get("status") == "ok"]
print("OK instances:", len(ok))
for i in ok:
    print(f"  id={i['id']} name={i['name']} url={i['url']} env={i['env']}")