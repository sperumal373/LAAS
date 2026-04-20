from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"

# In Move v2.2, cutover is triggered by updating the schedule
# Set RWEndTimeAtEpochSec to now to trigger immediate cutover
import time
now_ns = int(time.time() * 1000000000)

# Try updating the plan schedule to trigger cutover
payload = {
    "Spec": {
        "Schedule": {
            "ScheduleAtEpochSec": now_ns
        }
    }
}
r = c.s.put(f"{c.base}/move/v2/plans/{uuid}", json=payload, timeout=15)
print(f"PUT plan schedule: {r.status_code} {r.text[:300]}")

# Also try PATCH
r2 = c.s.patch(f"{c.base}/move/v2/plans/{uuid}", json=payload, timeout=15)
print(f"PATCH plan: {r2.status_code} {r2.text[:300]}")

# Try start with cutover spec
r3 = c.s.post(f"{c.base}/move/v2/plans/{uuid}/start", json={"Spec":{"Type":"Cutover"}}, timeout=15)
print(f"POST start cutover: {r3.status_code} {r3.text[:300]}")
