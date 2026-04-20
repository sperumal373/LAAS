import requests, urllib3, json
urllib3.disable_warnings()
base = 'https://172.17.63.21'

vr = requests.get(f'{base}/api/api_version', verify=False, timeout=10)
versions = vr.json().get('version', [])
v2 = [v for v in versions if str(v).startswith('2.')]
api_ver = str(sorted(v2, key=lambda x: [int(i) for i in str(x).split('.')])[-1])
print('Best API version:', api_ver)

# Correct method: api_token as a HEADER, not JSON body
for ver in [api_ver, '2.0']:
    print(f'\n=== POST /api/{ver}/login with api-token HEADER ===')
    s = requests.Session()
    s.verify = False
    try:
        lr = s.post(f'{base}/api/{ver}/login',
                    headers={'api-token': 'T-TESTONLY', 'Content-Type': 'application/json'},
                    timeout=10)
        print('Status:', lr.status_code)
        print('x-auth-token:', lr.headers.get('x-auth-token', 'MISSING'))
        print('Body:', lr.text[:300])
    except Exception as e:
        print('FAILED:', e)


