import requests
requests.packages.urllib3.disable_warnings()
s = requests.Session()
s.verify = False
tok = s.post('https://localhost/api/auth/login', json={'username':'admin','password':'caas@2024'}).json()['token']
h = {'Authorization': 'Bearer ' + tok}
r = s.get('https://localhost/api/migration/move-groups/4/post-tasks/playbooks?aap_id=1', headers=h)
data = r.json()
pbs = data.get('playbooks', [])
print(len(pbs),'playbooks')
for p in pbs[:5]: print(p.get('id'), p.get('name'))