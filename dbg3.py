import requests, json
requests.packages.urllib3.disable_warnings()

base = 'https://172.17.92.62'
# Method 1: Create personal access token via /api/v2/tokens/
r = requests.post(base + '/api/v2/tokens/',
    auth=('admin', 'Wiprosdxcoe@321'),
    json={}, verify=False, timeout=15,
    headers={'Content-Type': 'application/json'})
print(f"Token create: {r.status_code}")
print(r.text[:300])

# Method 2: Try OAuth2 token
r2 = requests.post(base + '/api/o/token/',
    data={'grant_type': 'password', 'username': 'admin', 'password': 'Wiprosdxcoe@321'},
    verify=False, timeout=15)
print(f"\nOAuth: {r2.status_code}")
print(r2.text[:300])

# Method 3: Session login
s = requests.Session()
s.verify = False
lr = s.get(base + '/api/login/')
print(f"\nLogin page: {lr.status_code}")
# Try basic auth with explicit header
import base64
creds = base64.b64encode(b'admin:Wiprosdxcoe@321').decode()
r3 = requests.get(base + '/api/v2/job_templates/?page_size=2',
    headers={'Authorization': f'Basic {creds}'},
    verify=False, timeout=15)
print(f"\nExplicit Basic: {r3.status_code}")
print(r3.text[:300])