from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"

# Check latest state
r = c.get_plan(uuid)
md = r.get("MetaData", {})
print(f"State: {md.get('StateString')} Status: {md.get('StatusString')}")
print(f"Actions: {md.get('Actions')}")
print(f"VMStateCounts: {md.get('VMStateCounts')}")
print(f"Data: {md.get('MigratedDataInBytes',0)/1073741824:.1f}/{md.get('DataInBytes',0)/1073741824:.1f} GB")
print(f"Elapsed: {md.get('ElapsedTime')}")

# Try calling start with force/cutover flags
for body in [
    {"Spec": {}},
    {"Spec": {"Force": True}},
    {"Spec": {"Cutover": True}},
    {"Spec": {"Type": "CUTOVER"}},
]:
    r2 = c.s.post(f"{c.base}/move/v2/plans/{uuid}/start", json=body, timeout=15)
    print(f"POST start {json.dumps(body)}: {r2.status_code} {r2.text[:150]}")
    if r2.status_code in (200, 201, 204):
        break
