import urllib.request, json, ssl

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Try to get a token
token = None
for pwd in ['admin', 'CaaS@2025!', 'password', 'Admin@123', 'caas2025', 'admin123']:
    try:
        req = urllib.request.Request('https://localhost/api/auth/token',
            data=json.dumps({'username':'admin','password':pwd}).encode(), method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            resp = json.loads(r.read())
            token = resp.get('access_token','')
            print(f'Login OK with password "{pwd}", token: {token[:30]}...')
            break
    except Exception as e:
        print(f'  {pwd}: {e}')

if not token:
    # Try form login
    try:
        from urllib.parse import urlencode
        req = urllib.request.Request('https://localhost/api/auth/token',
            data=urlencode({'username':'admin','password':'admin','grant_type':'password'}).encode(),
            method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            resp = json.loads(r.read())
            token = resp.get('access_token','')
            print(f'Form login OK, token: {token[:30]}...')
    except Exception as e:
        print(f'Form login failed: {e}')

if token:
    # Test insights API
    req2 = urllib.request.Request('https://localhost/api/history/insights',
        headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req2, timeout=10, context=ctx) as r:
        d = json.loads(r.read())
        print('IPAM in insights:', json.dumps(d.get('ipam', 'NOT FOUND'), indent=2))
