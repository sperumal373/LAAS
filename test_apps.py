import requests; requests.packages.urllib3.disable_warnings()
s = requests.Session(); s.verify = False
tok = s.post('https://localhost/api/auth/login', json={'username':'admin','password':'caas@2024'}).json()['token']
h = {'Authorization': 'Bearer ' + tok}
r = s.get('https://localhost/api/vmware/vms', headers=h)
data = r.json()
print(type(data).__name__)
if isinstance(data, dict):
    for k, v in data.items():
        if isinstance(v, list) and len(v) > 0:
            print(f"  Key '{k}': {len(v)} items, first keys: {list(v[0].keys())[:15]}")
            for vm in v[:10]:
                apps = vm.get('applications', [])
                name = vm.get('name','?')
                app_names = [a['app'] for a in apps] if apps else []
                print(f"    {name:30s} apps={app_names}")
            with_apps = [x for x in v if x.get('applications')]
            print(f"  VMs with apps: {len(with_apps)} / {len(v)}")
