import requests
requests.packages.urllib3.disable_warnings()
s = requests.Session()
s.verify = False
tok = s.post("https://localhost/api/auth/login", json={"username":"admin","password":"caas@2024"}).json()["token"]
h = {"Authorization": "Bearer " + tok}
r = s.get("https://localhost/api/migration/move-groups/4/post-tasks/playbooks?aap_id=1", headers=h)
d = r.json()
print(f"PROD playbooks: {len(d.get('playbooks', []))}")
r2 = s.get("https://localhost/api/migration/move-groups/4/post-tasks/playbooks?aap_id=2", headers=h)
d2 = r2.json()
print(f"PROD1 playbooks: {len(d2.get('playbooks', []))}")
r3 = s.get("https://localhost/api/migration/move-groups/4/post-tasks/playbooks?aap_id=3", headers=h)
d3 = r3.json()
print(f"TEST playbooks: {len(d3.get('playbooks', []))}")