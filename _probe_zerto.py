import requests, base64, warnings
warnings.filterwarnings("ignore")

creds = base64.b64encode(b"admin:Wipro@123").decode()
headers_basic = {"Authorization": "Basic " + creds, "Content-Type": "application/json"}
host = "172.17.73.176"

# The 405 on management/v1/session/add means path exists but wrong method
# Try GET to see what's there, and try known Zerto 10.x paths

tests = [
    ("GET",  "/management/v1/session/add"),
    ("GET",  "/management/v1/localsite"),
    ("GET",  "/management/v1/vpgs"),
    ("GET",  "/management/v1/"),
    ("POST", "/management/v1/authToken"),
    ("POST", "/management/v1/auth"),
    ("GET",  "/management/v1/auth"),
    # Zerto 10 keycloak-based auth
    ("GET",  "/auth/realms/zerto"),
    ("POST", "/auth/realms/zerto/protocol/openid-connect/token"),
    # Try without version
    ("GET",  "/management/localsite"),
    # Try swagger to discover API
    ("GET",  "/management/v1/swagger"),
    ("GET",  "/management/swagger"),
    ("GET",  "/management/v1/swagger.json"),
    ("GET",  "/swagger"),
    ("GET",  "/api-docs"),
]

for method, path in tests:
    url = "https://%s%s" % (host, path)
    try:
        r = requests.request(method, url, headers=headers_basic, verify=False, timeout=6, allow_redirects=False)
        print("  %s %s => %d  %s" % (method, path, r.status_code, r.text[:120].replace("\n"," ")))
    except Exception as e:
        print("  %s %s => ERR: %s" % (method, path, str(e)[:60]))
