from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"

# Try plan name based start
r = c.get_plan(uuid)
name = r.get("MetaData",{}).get("Name","")
print(f"Plan: {name}  State: {r.get('MetaData',{}).get('StateString')}")

# Try using name instead of UUID
for path in [
    f"/move/v2/plans/{name}/start",
    f"/move/v2/plans/{uuid}/start",
]:
    for body in [
        {"Spec": {"ScheduleType": "now"}},
        {"Spec": {"Action": "cutover"}},
        {"Spec": {"Force": True, "ScheduleType": "now"}},
    ]:
        r2 = c.s.post(f"{c.base}{path}", json=body, timeout=15)
        print(f"POST {path} body={json.dumps(body)}: {r2.status_code} {r2.text[:150]}")
        if r2.status_code in (200,201,204):
            print("SUCCESS!")
            break

# Try PUT to update the plan schedule while in ReadyToCutover
# First check if we can update settings
import time
r3 = c.get_plan(uuid)
spec = r3.get("Spec", {})
spec["Settings"]["Schedule"] = {"ScheduleAtEpochSec": int(time.time())}
r4 = c.s.put(f"{c.base}/move/v2/plans/{uuid}", json={"Spec": spec}, timeout=15)
print(f"\nPUT schedule update: {r4.status_code} {r4.text[:200]}")
