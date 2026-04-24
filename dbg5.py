import requests
requests.packages.urllib3.disable_warnings()

tests = [
    ('172.17.92.62', 'admin', 'Wiprosdxcoe@321'),
    ('172.17.92.62', 'admin', 'password'),
    ('172.17.74.74', 'admin', 'Wiprosdxcoe@321'),
    ('172.17.74.74', 'admin', 'Wipro@123'),
    ('172.17.92.40', 'admin', 'Wipro@123'),
]
for host, user, pw in tests:
    url = f'https://{host}/api/v2/me/'
    try:
        r = requests.get(url, auth=(user, pw), verify=False, timeout=10)
        if r.status_code == 200:
            me = r.json().get('results',[{}])[0]
            print(f'{host} user={user} pw={pw[:4]}*** -> OK (user={me.get("username","")})')
        else:
            print(f'{host} user={user} pw={pw[:4]}*** -> {r.status_code}')
    except Exception as e:
        print(f'{host} user={user} pw={pw[:4]}*** -> ERR: {e}')