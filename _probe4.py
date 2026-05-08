import requests, warnings, json
warnings.filterwarnings("ignore")

host = "172.17.73.176"
data = {"client_id": "zerto-client", "grant_type": "password", "username": "admin", "password": "Wipro@123"}
r = requests.post("https://%s/auth/realms/zerto/protocol/openid-connect/token" % host, data=data, verify=False, timeout=10)
token = r.json()["access_token"]
headers = {"Authorization": "Bearer " + token}

# Fetch the real data
for ep in ["/v1/localsite", "/v1/vpgs", "/v1/vms", "/v1/alerts", "/v1/tasks", "/v1/events", "/v1/peersites", "/v1/serviceprofiles", "/v1/reports/stats"]:
    r2 = requests.get("https://%s%s" % (host, ep), headers=headers, verify=False, timeout=10)
    try:
        body = r2.json()
        if isinstance(body, list):
            print("%s => list of %d items" % (ep, len(body)))
            if body: print("  keys:", list(body[0].keys())[:8])
        else:
            print("%s => %s" % (ep, str(body)[:200]))
    except:
        print("%s => HTTP %d  %s" % (ep, r2.status_code, r2.text[:100]))
