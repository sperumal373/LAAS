import requests, urllib3
urllib3.disable_warnings()
base = 'https://172.17.63.21'

# Get versions
vr = requests.get(f'{base}/api/api_version', verify=False, timeout=10)
versions = vr.json().get('version', [])
v2 = [v for v in versions if str(v).startswith('2.')]
api_ver = str(sorted(v2, key=lambda x: [int(i) for i in str(x).split('.')])[-1])
print(f'Array reachable. Highest REST API: {api_ver}')

# Verify /api/{api_ver}/login endpoint exists (OPTIONS or HEAD)
try:
    r = requests.options(f'{base}/api/{api_ver}/login', verify=False, timeout=5)
    print(f'  /api/{api_ver}/login OPTIONS -> {r.status_code}')
except Exception as e:
    print(f'  /api/{api_ver}/login OPTIONS -> ERROR: {e}')

# Test username/password with dummy creds - should get 401 not 404
s = requests.Session()
s.verify = False
s.headers.update({'Content-Type': 'application/json'})
lr = s.post(f'{base}/api/{api_ver}/login', json={'username': '__test__', 'password': '__test__'}, timeout=10)
print(f'  Username/pass login test -> {lr.status_code} (401=endpoint OK, 404=wrong path)')
print(f'  Body: {lr.text[:150]}')

# Test api-token header with dummy token
s2 = requests.Session()
s2.verify = False
lr2 = s2.post(f'{base}/api/{api_ver}/login', headers={'api-token': 'T-DUMMY'}, timeout=10)
print(f'  API token header test -> {lr2.status_code} (400=endpoint OK, 404=wrong path)')
print(f'  Body: {lr2.text[:150]}')
