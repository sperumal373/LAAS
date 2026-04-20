from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"

# The Move UI likely uses a different internal API - try /move/v2/plans/{uuid}/schedule
for method in ["POST", "PUT"]:
    for path_suffix in ["schedule", "cutover/schedule", "ops/cutover", "startcutover"]:
        path = f"/move/v2/plans/{uuid}/{path_suffix}"
        r = c.s.request(method, f"{c.base}{path}", json={"Spec":{}}, timeout=10)
        if r.status_code != 404:
            print(f"{method} {path}: {r.status_code} {r.text[:200]}")

# Try the internal websocket/graphql style endpoint the UI might use
r2 = c.s.post(f"{c.base}/move/v2/plans/{uuid}/retry", json={"Spec":{}}, timeout=10)
print(f"retry: {r2.status_code} {r2.text[:200]}")

# Check if there's a v1 API
r3 = c.s.post(f"{c.base}/move/v1/plans/{uuid}/start", json={}, timeout=10)
print(f"v1 start: {r3.status_code} {r3.text[:200]}")

# Try abort then restart
print("\n--- Trying ABORT then re-start ---")
r4 = c.s.post(f"{c.base}/move/v2/plans/{uuid}/abort", json={"Spec":{}}, timeout=10)
print(f"abort: {r4.status_code} {r4.text[:200]}")
