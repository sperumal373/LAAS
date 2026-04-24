import requests
requests.packages.urllib3.disable_warnings()

base = 'https://172.17.92.62'
s = requests.Session()
s.verify = False

# Step 1: Get CSRF token from login page
lr = s.get(base + '/api/login/')
csrf = s.cookies.get('csrftoken', '')
print(f'CSRF: {csrf[:20]}...')

# Step 2: POST login with CSRF
r = s.post(base + '/api/login/', 
    data={'username': 'admin', 'password': 'Wiprosdxcoe@321', 'next': '/api/v2/'},
    headers={'Referer': base + '/api/login/', 'X-CSRFToken': csrf},
    allow_redirects=False)
print(f'Login: {r.status_code} Location={r.headers.get("Location","")}')

# Step 3: Now try to fetch templates with session cookies
r2 = s.get(base + '/api/v2/job_templates/?page_size=3')
print(f'Templates: {r2.status_code}')
if r2.status_code == 200:
    data = r2.json()
    print(f'Count: {data.get("count",0)}')
    for t in data.get('results', [])[:5]:
        print(f'  {t["id"]}: {t["name"]}')
else:
    print(r2.text[:200])