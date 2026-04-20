import requests, urllib3, json, time
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"

# Login
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"
print("Logged in.\n")

# 1. Check all plans and their schedule settings
r2 = s.post("https://172.16.146.117/move/v2/plans/list", json={}, timeout=15)
plans = r2.json().get("Entities", [])

print(f"Total plans: {len(plans)}\n")

# Find plans with various states
for p in plans:
    meta = p.get("MetaData", {})
    name = meta.get("Name", "?")
    state_str = meta.get("StateString", "")
    status_str = meta.get("StatusString", "")
    sched = meta.get("Schedule", {})
    uuid = meta.get("UUID", "")
    
    # Only show interesting ones (InProgress, ReadyToCutover, Completed recently, or our LaaS plans)
    if "LaaS" in name or "InProgress" in state_str or "ReadyToCutover" in state_str or "Cutover" in state_str:
        print(f"Plan: {name}")
        print(f"  UUID: {uuid}")
        print(f"  State: {state_str} | Status: {status_str}")
        print(f"  Schedule: {json.dumps(sched)}")
        print(f"  Errors: {meta.get('ErrorReasons', [])}")
        print()

# 2. Get full details of one plan to understand schedule structure
print("="*60)
print("DETAILED PLAN INSPECTION")
print("="*60)

# Get a completed plan to see what schedule looks like after cutover
for p in plans:
    meta = p.get("MetaData", {})
    state_str = meta.get("StateString", "")
    if "Completed" in state_str:
        uuid = meta.get("UUID", "")
        r3 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=10)
        d = r3.json()
        sched = d.get("MetaData", {}).get("Schedule", {})
        settings = d.get("Spec", {}).get("Settings", {})
        print(f"\nCompleted plan: {meta.get('Name', '?')} ({uuid})")
        print(f"  MetaData.Schedule: {json.dumps(sched)}")
        print(f"  Spec.Settings.Schedule: {json.dumps(settings.get('Schedule', {}))}")
        print(f"  Spec.Settings keys: {list(settings.keys())}")
        break

# 3. Get an InProgress plan to compare
for p in plans:
    meta = p.get("MetaData", {})
    state_str = meta.get("StateString", "")
    if "InProgress" in state_str or "Paused" in state_str:
        uuid = meta.get("UUID", "")
        r3 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=10)
        d = r3.json()
        sched = d.get("MetaData", {}).get("Schedule", {})
        settings = d.get("Spec", {}).get("Settings", {})
        print(f"\nInProgress/Paused plan: {meta.get('Name', '?')} ({uuid})")
        print(f"  MetaData.Schedule: {json.dumps(sched)}")
        print(f"  Spec.Settings.Schedule: {json.dumps(settings.get('Schedule', {}))}")
        print(f"  Spec.Settings keys: {list(settings.keys())}")
        
        # Check VM states within this plan
        vms = d.get("Spec", {}).get("Workload", {}).get("VMs", [])
        for vm in vms:
            ref = vm.get("VMReference", {})
            status = vm.get("Status", {})
            print(f"  VM: {ref.get('VMName', '?')} Status: {json.dumps(status)[:200]}")
        break

# 4. Test what ScheduleAtEpochSec values mean
print("\n" + "="*60)
print("SCHEDULE SEMANTICS TEST")
print("="*60)
print("ScheduleAtEpochSec = -1  -> Manual cutover (user must click)")
print("ScheduleAtEpochSec = 0   -> Immediate auto-cutover after seeding")
print("ScheduleAtEpochSec = N   -> Scheduled cutover at epoch N (nanoseconds)")

# 5. Test API endpoints systematically on a paused plan
print("\n" + "="*60)
print("API ENDPOINT DISCOVERY")
print("="*60)

# Find our paused plan
test_uuid = "a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"

# Try every plausible action endpoint
actions = ["start", "cutover", "cancel", "suspend", "resume", "abort", 
           "retry", "complete", "finalize", "migrate", "switchover",
           "action/cutover", "actions/cutover", "vm/cutover"]

for action in actions:
    url = f"https://172.16.146.117/move/v2/plans/{test_uuid}/{action}"
    try:
        resp = s.post(url, json=None, timeout=5)
        code = resp.status_code
        body = resp.text[:120]
        marker = "***" if code not in [404, 405] else "   "
        print(f"{marker} POST .../{action} -> {code}: {body}")
    except:
        pass

# Also try PUT with schedule update
print("\n--- PUT schedule update test ---")
now_ns = int(time.time() * 1e9)
# First resume the plan so it's not paused
s.post(f"https://172.16.146.117/move/v2/plans/{test_uuid}/resume", json=None, timeout=5)
time.sleep(2)

# Now try PUT with full plan spec to change schedule
r_get = s.get(f"https://172.16.146.117/move/v2/plans/{test_uuid}", timeout=10)
plan_data = r_get.json()
if "Spec" in plan_data:
    spec = plan_data["Spec"]
    if "Settings" in spec and "Schedule" in spec["Settings"]:
        print(f"  Current Schedule: {spec['Settings']['Schedule']}")
        # Try setting to immediate cutover
        spec["Settings"]["Schedule"]["ScheduleAtEpochSec"] = 0
        resp = s.put(f"https://172.16.146.117/move/v2/plans/{test_uuid}", json={"Spec": spec}, timeout=15)
        print(f"  PUT with Schedule=0: {resp.status_code}: {resp.text[:200]}")
