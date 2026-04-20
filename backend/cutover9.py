from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"

# Try UUID in path with PUT
for action in ["PAUSE", "CUTOVER"]:
    r = c.s.put(f"{c.base}/move/v2/plans/{uuid}/action", json={"Spec":{"Action": action}}, timeout=15)
    print(f"PUT {uuid}/action={action}: {r.status_code} {r.text[:200]}")

# Try with UUID field instead of PlanUUID
r = c.s.put(f"{c.base}/move/v2/plans/action", json={"Spec":{"Action": "CUTOVER", "UUID": uuid}}, timeout=15)
print(f"PUT plans/action UUID field: {r.status_code} {r.text[:200]}")

# Try with Entities array format
r = c.s.put(f"{c.base}/move/v2/plans/action", json={"Spec":{"Entities":[{"UUID": uuid}], "Action": "CUTOVER"}}, timeout=15)
print(f"PUT Entities format: {r.status_code} {r.text[:200]}")
