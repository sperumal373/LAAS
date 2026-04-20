from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"
# Try different cutover endpoints
for method, path, body in [
    ("POST", f"/move/v2/plans/{uuid}/cutover", {"Spec":{}}),
    ("POST", f"/move/v2/plans/{uuid}/start", {"Spec":{}}),
    ("PUT", f"/move/v2/plans/{uuid}/cutover", {"Spec":{}}),
    ("POST", f"/move/v2/plans/{uuid}/action/cutover", {"Spec":{}}),
]:
    try:
        r = c.s.request(method, f"{c.base}{path}", json=body, timeout=15)
        print(f"{method} {path}: {r.status_code} {r.text[:300]}")
        if r.status_code in (200, 201, 204):
            break
    except Exception as e:
        print(f"{method} {path}: {e}")
