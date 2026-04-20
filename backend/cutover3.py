from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"

# Try the correct Move v2 cutover - it might need /migrate endpoint
for path in [
    f"/move/v2/plans/{uuid}/migrate",
    f"/move/v2/plans/{uuid}/cutover/start",
    f"/move/v2/plans/{uuid}/operations/cutover",
]:
    r = c.s.post(f"{c.base}{path}", json={"Spec":{}}, timeout=15)
    print(f"POST {path}: {r.status_code} {r.text[:200]}")

# Check what actions are available
r = c.get_plan(uuid)
md = r.get("MetaData", {})
print(f"\nAvailable Actions: {md.get('Actions')}")
print(f"State: {md.get('StateString')}  VMStateCounts: {md.get('VMStateCounts')}")
