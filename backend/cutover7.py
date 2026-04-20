from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"

# The Actions say PAUSE is available - maybe it's an action endpoint
for path in [
    f"/move/v2/plans/{uuid}/action",
    f"/move/v2/plans/action",
]:
    for action in ["PAUSE", "CUTOVER", "START_CUTOVER"]:
        r = c.s.post(f"{c.base}{path}", json={"Spec":{"Action": action, "PlanUUID": uuid}}, timeout=15)
        print(f"POST {path} Action={action}: {r.status_code} {r.text[:150]}")

# Also check - maybe the old Test2026 plan used a different API version
# Check Move API version
r = c.s.get(f"{c.base}/move/v2/version", timeout=10)
print(f"\nMove version: {r.status_code} {r.text[:200]}")
