import requests, base64, warnings, json
warnings.filterwarnings("ignore")

host = "172.17.73.176"

# Zerto 10.x uses Keycloak. Get the token endpoint
r = requests.get("https://%s/auth/realms/zerto/.well-known/openid-configuration" % host, verify=False, timeout=8)
print("OpenID config status:", r.status_code)
if r.status_code == 200:
    cfg = r.json()
    print("  token_endpoint:", cfg.get("token_endpoint"))
    print("  auth endpoint:", cfg.get("authorization_endpoint"))

# Try password grant
print()
print("Trying password grant...")
data = {
    "client_id": "zerto-client",
    "grant_type": "password",
    "username": "admin",
    "password": "Wipro@123"
}
r2 = requests.post("https://%s/auth/realms/zerto/protocol/openid-connect/token" % host,
    data=data, verify=False, timeout=10)
print("Status:", r2.status_code)
print("Response:", r2.text[:400])
