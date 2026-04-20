from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"

# PUT on plans/action with the plan UUID
for action in ["PAUSE", "CUTOVER", "START", "RESUME"]:
    r = c.s.put(f"{c.base}/move/v2/plans/action", json={"Spec":{"Action": action, "PlanUUID": uuid}}, timeout=15)
    print(f"PUT plans/action Action={action}: {r.status_code} {r.text[:200]}")
    if r.status_code in (200, 201, 204):
        print("  SUCCESS!")
        break
