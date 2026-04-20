import requests, urllib3, json, time
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# Key test: can we PUT update schedule on an InProgress plan that is ReadyToCutover?
# The error before was "update not allowed in current state InProgress"
# But the UI JS shows postMigration("start") triggers cutover-like behavior

# Let's try POST /start on a plan that's already InProgress + ReadyToCutover
# test16Apr is someone else's plan, let's use LaaS-Test2026-13
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"  # LaaS-Test2026-13

r1 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=10)
d = r1.json()
meta = d.get("MetaData", {})
print(f"Plan: {meta.get('Name')} State: {meta.get('StateString')}")
print(f"VMStateCounts: {meta.get('VMStateCounts')}")
print(f"Schedule: {meta.get('Schedule')}")

# The Move UI JS sends: POST /move/v2/plans/{uuid}/start with {Spec:{Time:0}}
# for START, but for cutover it sends: POST /move/v2/plans/{uuid}/cutover with null
# Since /cutover doesn't exist, let's try /start with Time=0 on ReadyToCutover plan

print("\n--- Test 1: POST /start with {Spec:{Time:0}} ---")
resp = s.post(f"https://172.16.146.117/move/v2/plans/{uuid}/start", json={"Spec":{"Time":0}}, timeout=15)
print(f"Response: {resp.status_code}: {resp.text[:300]}")

print("\n--- Test 2: POST /start with null ---")
resp = s.post(f"https://172.16.146.117/move/v2/plans/{uuid}/start", json=None, timeout=15)
print(f"Response: {resp.status_code}: {resp.text[:300]}")

# Wait and check if state changed
time.sleep(5)
r2 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=10)
d2 = r2.json()
meta2 = d2.get("MetaData", {})
print(f"\nAfter /start: State={meta2.get('StateString')} VMStateCounts={meta2.get('VMStateCounts')}")
print(f"Schedule: {meta2.get('Schedule')}")
