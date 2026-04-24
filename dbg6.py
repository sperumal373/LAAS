import requests
requests.packages.urllib3.disable_warnings()

tests = [
    ('PROD', '172.17.92.62', 'password'),
    ('PROD1', '172.17.74.74', 'Wipro@123'),
    ('TEST', '172.17.92.40', 'Wipro@123'),
]
for name, host, pw in tests:
    url = f'https://{host}/api/v2/job_templates/?page_size=5'
    try:
        r = requests.get(url, auth=('admin', pw), verify=False, timeout=15)
        data = r.json()
        cnt = data.get('count', 0)
        print(f'{name} ({host}): {cnt} templates')
        for t in data.get('results', [])[:5]:
            print(f'  {t["id"]}: {t["name"]} ({t.get("playbook","")})')
    except Exception as e:
        print(f'{name} ({host}): ERR {e}')