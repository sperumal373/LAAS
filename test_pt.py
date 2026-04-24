import requests
requests.packages.urllib3.disable_warnings()
s = requests.Session()
s.verify = False
tok = s.post("https://localhost/api/auth/login", json={"username":"admin","password":"caas@2024"}).json()["token"]
h = {"Authorization": "Bearer " + tok}

# Get move groups first
gr = s.get("https://localhost/api/migration/move-groups", headers=h).json()
print("Move groups:", [(g["id"], g["name"]) for g in gr])

# Try post-tasks for each group
for g in gr:
    r = s.get(f"https://localhost/api/migration/move-groups/{g['id']}/post-tasks", headers=h)
    print(f"  Group {g['id']} post-tasks: status={r.status_code} body={r.text[:200]}")