import requests, urllib3, json, time
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# This plan has errors - let's find one in ReadyToCutover
# Get full plan details for all our known plans
for uid in ["a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"]:
    resp = s.get(f"https://172.16.146.117/move/v2/plans/{uid}", timeout=10)
    d = resp.json()
    meta = d.get("MetaData", {})
    print(f"Plan: {meta.get('Name')} State: {meta.get('StateString')} Status: {meta.get('StatusString')}")
    print(f"  Errors: {meta.get('ErrorReasons')}")
    
    # Check VM statuses
    vms = d.get("Spec", {}).get("Workload", {}).get("VMs", [])
    for vm in vms:
        print(f"  VM: {vm.get('VMReference',{}).get('VMName','')} State: {vm.get('Status',{})}")

# The plan has errors. Let's create a NEW fresh migration plan to test cutover properly.
# But first - since the existing /cutover endpoint doesn't exist in v2.2, 
# the real cutover mechanism must be the schedule.
# When ScheduleAtEpochSec is set to a timestamp in the past or 0, Move should auto-cutover.

# Let's try updating the plan schedule to trigger cutover
# Use epoch in nanoseconds (Move format) - set to NOW
now_ns = int(time.time() * 1e9)
print(f"\nTrying PUT to update plan with schedule = {now_ns}")
payload = {"Spec": {"Settings": {"Schedule": {"ScheduleAtEpochSec": now_ns}}}}
resp = s.put(f"https://172.16.146.117/move/v2/plans/a8de427d-4dd1-4f03-a86f-1616b6a7e5c4", json=payload, timeout=15)
print(f"PUT response: {resp.status_code}: {resp.text[:300]}")
