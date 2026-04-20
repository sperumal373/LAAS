import requests, urllib3, json, time
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# Check what the plan got
plan_uuid = None
r2 = s.post("https://172.16.146.117/move/v2/plans/list", json={}, timeout=15)
for p in r2.json().get("Entities",[]):
    if p.get("MetaData",{}).get("Name") == "LaaS-debug-retry":
        plan_uuid = p["MetaData"]["UUID"]
        sched = p["MetaData"].get("Schedule",{})
        print(f"Found plan: {plan_uuid}")
        print(f"Schedule from list: {json.dumps(sched)}")
        break

if plan_uuid:
    # Get full details
    r3 = s.get(f"https://172.16.146.117/move/v2/plans/{plan_uuid}", timeout=10)
    d = r3.json()
    settings = d.get("Spec",{}).get("Settings",{})
    print(f"Spec.Settings.Schedule: {json.dumps(settings.get('Schedule',{}))}")
    
    # Delete test plan
    s.delete(f"https://172.16.146.117/move/v2/plans/{plan_uuid}", timeout=15)
    print("Deleted test plan")

# Try with a future scheduled time to confirm that works
future_ns = int((time.time() + 3600) * 1e9)  # 1 hour from now
print(f"\nTesting with future schedule: {future_ns}")
payload = {
    "Spec": {
        "Name": "LaaS-sched-test",
        "SourceInfo": {"ProviderUUID": "04d468bb-3de8-4d9e-8cac-c35cfaed413d"},
        "TargetInfo": {
            "ProviderUUID": "d6b7cb76-e75d-4376-88d0-c9d5c43c8a3b",
            "AOSProviderAttrs": {
                "ClusterUUID": "00055313-e41c-5c5b-0000-00000000e8db",
                "ContainerUUID": "34f254d4-4dc3-4a2c-b389-692c1aa4092e"
            }
        },
        "Workload": {"Type": "VM", "VMs": [{
            "VMReference": {"UUID": "5001e7c9-4ba8-4220-c80c-4f45d35688ed", "VMID": "vm-390210", "VMName": "sdxdcwabott"},
            "GuestPrepMode": "auto", "VMPriority": "High"
        }]},
        "NetworkMappings": [{"SourceNetworkID": "network-388401", "TargetNetworkID": "b5144cfe-0291-4f3f-8925-a768aa5edf67"}],
        "Settings": {"GuestPrepMode": "auto", "NicConfigMode": "dhcp", "Schedule": {"ScheduleAtEpochSec": future_ns}}
    }
}
rc = s.post("https://172.16.146.117/move/v2/plans", json=payload, timeout=30)
print(f"Create with future schedule: {rc.status_code}")
if rc.status_code == 201:
    d2 = rc.json()
    sched2 = d2.get("MetaData",{}).get("Schedule",{})
    print(f"Returned schedule: {json.dumps(sched2)}")
    uid2 = d2.get("MetaData",{}).get("UUID","")
    s.delete(f"https://172.16.146.117/move/v2/plans/{uid2}", timeout=15)
    print("Deleted test plan")
else:
    print(f"Response: {rc.text[:300]}")
