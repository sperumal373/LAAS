import requests
requests.packages.urllib3.disable_warnings()
s = requests.Session()
s.verify = False
tok = s.post('https://localhost/api/auth/login', json={'username':'admin','password':'caas@2024'}).json()['token']
r = s.get('https://localhost/api/ansible/instances', headers={'Authorization': 'Bearer ' + tok})
print(r.status_code)
data = r.json()
instances = data.get('instances', [])
print(len(instances), 'instances')
ok = [i for i in instances if i.get('status') == 'ok']
print(len(ok), 'ok instances')
for i in ok: print(i.get('id'), i.get('name'), i.get('url'), i.get('status'))