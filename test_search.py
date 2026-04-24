import requests; requests.packages.urllib3.disable_warnings()
s = requests.Session(); s.verify = False
tok = s.post('https://localhost/api/auth/login', json={'username':'admin','password':'caas@2024'}).json()['token']
h = {'Authorization': 'Bearer ' + tok}
r = s.get('https://localhost/api/migration/move-groups/4/post-tasks/playbooks?aap_id=1&search=linux', headers=h)
print(f'Status: {r.status_code}')
d = r.json()
pbs = d.get('playbooks', [])
print(f'PROD playbooks matching linux: {len(pbs)}')
for p in pbs[:5]:
    print(f"  - {p['name']}")
r2 = s.get('https://localhost/api/migration/move-groups/4/post-tasks/playbooks?aap_id=3&search=test', headers=h)
print(f"TEST matching test: {len(r2.json().get('playbooks', []))}")
