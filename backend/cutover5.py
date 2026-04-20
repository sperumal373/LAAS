from nutanix_move_client import MoveClient
import json, time
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"

# Get full plan detail to send back with updated schedule
r = c.get_plan(uuid)
spec = r.get("Spec", {})
print(f"Current spec keys: {list(spec.keys())}")

# Update schedule to trigger cutover now
now_ns = int(time.time() * 1000000000)
spec["Schedule"] = {"ScheduleAtEpochSec": now_ns}

payload = {"Spec": spec}
r2 = c.s.put(f"{c.base}/move/v2/plans/{uuid}", json=payload, timeout=15)
print(f"PUT with full spec: {r2.status_code}")
print(r2.text[:500])
