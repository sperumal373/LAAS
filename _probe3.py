import requests, base64, warnings, json
warnings.filterwarnings("ignore")

host = "172.17.73.176"

# Get token
data = {"client_id": "zerto-client", "grant_type": "password", "username": "admin", "password": "Wipro@123"}
r = requests.post("https://%s/auth/realms/zerto/protocol/openid-connect/token" % host, data=data, verify=False, timeout=10)
token = r.json()["access_token"]
print("Got token:", token[:40] + "...")
headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

# Try API paths with bearer token
paths = [
    "/v1/localsite",
    "/v1/vpgs",
    "/management/api/v1/localsite",
    "/management/api/v1/vpgs",
    "/ZvmService/management/v1/localsite",
    "/ZvmService/management/v1/vpgs",
    "/api/v1/localsite",
    "/api/v1/vpgs",
    # Try to find swagger
    "/v1/swagger.json",
    "/management/api/v1/swagger",
]
for path in paths:
    url = "https://%s%s" % (host, path)
    try:
        r2 = requests.get(url, headers=headers, verify=False, timeout=8)
        body = r2.text[:150].replace("\n"," ")
        print("  %d  %s  =>  %s" % (r2.status_code, path, body))
    except Exception as e:
        print("  ERR %s => %s" % (path, str(e)[:60]))
