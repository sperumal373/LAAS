from nutanix_move_client import MoveClient
import json, time
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"

# Pause and then resume with cutover
print("Pausing plan...")
r = c.s.post(f"{c.base}/move/v2/plans/{uuid}/pause", json={"Spec":{}}, timeout=15)
print(f"Pause: {r.status_code} {r.text[:200]}")

time.sleep(5)

# Check state after pause
r2 = c.get_plan(uuid)
md = r2.get("MetaData",{})
print(f"State after pause: {md.get('StateString')}  Actions: {md.get('Actions')}")

# Now try start again
r3 = c.s.post(f"{c.base}/move/v2/plans/{uuid}/start", json={"Spec":{}}, timeout=15)
print(f"Start after pause: {r3.status_code} {r3.text[:200]}")

time.sleep(3)

# Check again
r4 = c.get_plan(uuid)
md4 = r4.get("MetaData",{})
print(f"State now: {md4.get('StateString')}  Actions: {md4.get('Actions')}  VMStateCounts: {md4.get('VMStateCounts')}")
