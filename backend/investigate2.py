import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# Check ALL completed plans - see if any used ScheduleAtEpochSec != -1
r2 = s.post("https://172.16.146.117/move/v2/plans/list", json={}, timeout=15)
plans = r2.json().get("Entities", [])

print("=== ALL COMPLETED PLANS - Schedule check ===")
for p in plans:
    meta = p.get("MetaData", {})
    state_str = meta.get("StateString", "")
    if "Completed" in state_str:
        sched = meta.get("Schedule", {})
        epoch = sched.get("ScheduleAtEpochSec", "?")
        print(f"  {meta.get('Name','?'):30s} Schedule={epoch}")

# Check VM-level state for InProgress plans 
print("\n=== INPROGRESS PLANS - VM state details ===")
for p in plans:
    meta = p.get("MetaData", {})
    state_str = meta.get("StateString", "")
    name = meta.get("Name", "")
    if "InProgress" in state_str and ("LaaS" in name or "test16" in name):
        uuid = meta.get("UUID", "")
        vm_counts = meta.get("VMStateCounts", {})
        print(f"  {name}: VMStateCounts={json.dumps(vm_counts)}")
        
        # Get detailed plan
        r3 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=10)
        d = r3.json()
        vms = d.get("Spec", {}).get("Workload", {}).get("VMs", [])
        for vm in vms:
            ref = vm.get("VMReference", {})
            st = vm.get("Status", {})
            print(f"    VM: {ref.get('VMName','?')} -> {json.dumps(st)[:300]}")

# Key question: does POST /start on a ReadyToCutover plan trigger cutover?
# test16Apr is InProgress with ScheduleAtEpochSec=-1
# Let's check if it's in ReadyToCutover
print("\n=== Checking test16Apr VM state ===")
uuid_16 = "098a4de3-db3d-4d29-864f-95589ebeca67"
r3 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid_16}", timeout=10)
d = r3.json()
meta = d.get("MetaData", {})
print(f"  State: {meta.get('StateString')} Status: {meta.get('StatusString')}")
print(f"  VMStateCounts: {json.dumps(meta.get('VMStateCounts', {}))}")
print(f"  Schedule: {json.dumps(meta.get('Schedule', {}))}")
vms = d.get("Spec", {}).get("Workload", {}).get("VMs", [])
for vm in vms:
    ref = vm.get("VMReference", {})
    st = vm.get("Status", {})
    print(f"  VM '{ref.get('VMName','?')}': {json.dumps(st)[:500]}")
