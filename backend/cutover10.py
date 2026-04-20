from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()

# Get the plan by name to check the exact format used in the existing completed plan
old = c.get_plan("88158af3-a456-4758-ba1d-7e5047c06c74")
old_md = old.get("MetaData",{})
print(f"Old plan schedule: {old_md.get('Schedule')}")
print(f"Old plan RWEnd: {old_md.get('Schedule',{}).get('RWEndTimeAtEpochSec')}")

uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"
# The correct format for Move v2.2 is to update the plan with schedule using the plan name
r = c.get_plan(uuid)
spec = r.get("Spec", {})

# Try: PUT with the plan name and schedule
import time
now_epoch = int(time.time())
spec["Settings"]["Schedule"] = {"ScheduleAtEpochSec": now_epoch}
r2 = c.s.put(f"{c.base}/move/v2/plans/{uuid}", json={"Spec": spec}, timeout=15)
print(f"\nPUT update schedule: {r2.status_code} {r2.text[:300]}")
