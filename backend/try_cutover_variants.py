import requests, urllib3
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

uuid = "a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"

# Check actual status first
r1 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=15)
import json
d = r1.json()
print("Status field:", json.dumps(d.get("Status",{}), indent=2)[:500])
print()

# Try all variants
variants = [
    ("POST", f"/move/v2/plans/{uuid}/cutover", None),
    ("POST", f"/move/v2/plans/{uuid}/cutover", {}),
    ("POST", f"/move/v2/plans/{uuid}/cutover", {"Spec":{}}),
    ("PUT",  f"/move/v2/plans/{uuid}/cutover", None),
    ("POST", f"/api/v2/plans/{uuid}/cutover", None),
    ("POST", f"/move/v2/plans/{uuid}/Cutover", None),
    ("POST", f"/move/v2.0/plans/{uuid}/cutover", None),
]
for method, path, body in variants:
    url = f"https://172.16.146.117{path}"
    if method == "POST":
        resp = s.post(url, json=body, timeout=10)
    else:
        resp = s.put(url, json=body, timeout=10)
    print(f"{method} {path} -> {resp.status_code}: {resp.text[:150]}")
