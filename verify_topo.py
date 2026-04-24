import requests; requests.packages.urllib3.disable_warnings()
s = requests.Session(); s.verify = False
tok = s.post('https://localhost/api/auth/login', json={'username':'admin','password':'caas@2024'}).json()['token']
h = {'Authorization': 'Bearer ' + tok}
vms = s.get('https://localhost/api/vmware/vms', headers=h).json().get('vms', [])
print(f"Total: {len(vms)}")
if vms and 'topology' in vms[0]:
    clustered = [v for v in vms if v.get('topology') == 'Cluster']
    standalone = [v for v in vms if v.get('topology') == 'Standalone']
    print(f"Cluster: {len(clustered)} | Standalone: {len(standalone)}")
    types = {}
    for v in clustered:
        ct = v.get('cluster_type') or 'Unknown'
        types[ct] = types.get(ct, 0) + 1
    print("Cluster types:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
else:
    print("NO topology field - backend not updated")
    if vms:
        print("Keys:", list(vms[0].keys())[:20])
