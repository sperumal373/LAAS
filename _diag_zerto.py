import requests, base64, warnings
warnings.filterwarnings("ignore")

creds = base64.b64encode(b"admin:Wipro@123").decode()
headers = {"Authorization": "Basic " + creds, "Content-Type": "application/json"}

hosts = ["172.17.73.176", "172.17.90.216"]
# Zerto 9.x and 10.x use different API paths
paths = [
    "/management/v1/session/add",
    "/v1/session/add",
    "/api/v1/session/add",
    "/ZVMService/management/v1/session/add",
]
ports = [443, 9669, 7669]

for host in hosts:
    print("=== Testing %s ===" % host)
    # First just check if host is reachable at all
    for port in ports:
        for path in paths:
            url = "https://%s:%d%s" % (host, port, path)
            try:
                r = requests.post(url, headers=headers, verify=False, timeout=8)
                print("  [%d] %s => HTTP %d  headers=%s" % (port, path, r.status_code, dict(list(r.headers.items())[:4])))
                if r.status_code < 500:
                    print("    BODY:", r.text[:200])
            except requests.exceptions.ConnectTimeout:
                print("  [%d] %s => TIMEOUT" % (port, path))
            except requests.exceptions.ConnectionError as e:
                print("  [%d] %s => CONN ERROR: %s" % (port, path, str(e)[:80]))
            except Exception as e:
                print("  [%d] %s => ERROR: %s" % (port, path, str(e)[:80]))
    print()
