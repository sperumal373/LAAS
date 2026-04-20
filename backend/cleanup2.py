import requests, urllib3, json, time
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

uuid = "a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"
r1 = s.get(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=10)
state = r1.json().get("MetaData",{}).get("StateString","")
print(f"LaaS-laas-20 state: {state}")

if "Cancel" in state or "Completed" in state:
    print("Already cancelled/completed. Trying delete...")
    rd = s.delete(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=30)
    print(f"Delete: {rd.status_code} {rd.text[:200]}")
else:
    # Try cancel again
    print("Trying cancel...")
    rc = s.post(f"https://172.16.146.117/move/v2/plans/{uuid}/cancel", json=None, timeout=60)
    print(f"Cancel: {rc.status_code} {rc.text[:200]}")
    time.sleep(5)
    # Then delete
    rd = s.delete(f"https://172.16.146.117/move/v2/plans/{uuid}", timeout=30)
    print(f"Delete: {rd.status_code} {rd.text[:200]}")

# Now try creating the plan again
time.sleep(3)
print("\n--- Retry plan creation ---")
payload = {
    "Spec": {
        "Name": "LaaS-debug-retry",
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
        "Settings": {"GuestPrepMode": "auto", "NicConfigMode": "dhcp", "Schedule": {"ScheduleAtEpochSec": 0}}
    }
}
rc2 = s.post("https://172.16.146.117/move/v2/plans", json=payload, timeout=30)
print(f"Create: {rc2.status_code} {rc2.text[:400]}")
