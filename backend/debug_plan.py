import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.headers["Content-Type"] = "application/json"
r = s.post("https://172.16.146.117/move/v2/users/login", json={"Spec":{"UserName":"nutanix","Password":"Wipro@123"}}, timeout=15)
token = r.json().get("Status",{}).get("Token","")
s.headers["Authorization"] = f"Bearer {token}"

# Resolve VM info same way the code does
vm_uuid = "5001e7c9-4ba8-4220-c80c-4f45d35688ed"
vm_id = "vm-390210"
vm_name = "sdxdcwabott"

# Get target network
prov = s.get("https://172.16.146.117/move/v2/providers/d6b7cb76-e75d-4376-88d0-c9d5c43c8a3b", timeout=15).json()
nets = prov.get("Spec",{}).get("AOSProperties",{}).get("Networks",[])
target_net = nets[0]["UUID"] if nets else "b5144cfe-0291-4f3f-8925-a768aa5edf67"
print(f"Target network: {target_net}")

# Get source network name for this VM via vCenter
import requests as req
vc = req.Session()
vc.verify = False
r2 = vc.post("https://172.17.168.212/api/session", auth=("administrator@vsphere.local","Sdxdc@168-212"), timeout=10)
vc.headers["vmware-api-session-id"] = r2.text.strip('"')
r3 = vc.get(f"https://172.17.168.212/api/vcenter/vm/{vm_id}", timeout=10).json()
nics = r3.get("nics",{})
pg_id = ""
for _,nic in nics.items():
    pg_id = nic.get("backing",{}).get("network","")
    break
print(f"Source portgroup ID: {pg_id}")

# Get portgroup name
r4 = vc.get(f"https://172.17.168.212/api/vcenter/network/{pg_id}", timeout=10)
pg_name = r4.json().get("name", pg_id) if r4.status_code == 200 else pg_id
print(f"Source portgroup name: {pg_name}")

# Build payload with ScheduleAtEpochSec=0
payload = {
    "Spec": {
        "Name": "LaaS-debug-test",
        "SourceInfo": {"ProviderUUID": "04d468bb-3de8-4d9e-8cac-c35cfaed413d"},
        "TargetInfo": {
            "ProviderUUID": "d6b7cb76-e75d-4376-88d0-c9d5c43c8a3b",
            "AOSProviderAttrs": {
                "ClusterUUID": "00055313-e41c-5c5b-0000-00000000e8db",
                "ContainerUUID": "34f254d4-4dc3-4a2c-b389-692c1aa4092e"
            }
        },
        "Workload": {"Type": "VM", "VMs": [{
            "VMReference": {"UUID": vm_uuid, "VMID": vm_id, "VMName": vm_name},
            "GuestPrepMode": "auto",
            "VMPriority": "High"
        }]},
        "NetworkMappings": [{"SourceNetworkID": pg_name, "TargetNetworkID": target_net}],
        "Settings": {
            "GuestPrepMode": "auto",
            "NicConfigMode": "dhcp",
            "Schedule": {"ScheduleAtEpochSec": 0}
        }
    }
}

print(f"\nPayload:\n{json.dumps(payload, indent=2)}")

# Try create
print("\n--- Creating plan ---")
rc = s.post("https://172.16.146.117/move/v2/plans", json=payload, timeout=30)
print(f"Status: {rc.status_code}")
print(f"Response: {rc.text[:500]}")

# If 500, try with ScheduleAtEpochSec=-1 (known working value)
if rc.status_code >= 400:
    print("\n--- Retrying with ScheduleAtEpochSec=-1 ---")
    payload["Spec"]["Settings"]["Schedule"]["ScheduleAtEpochSec"] = -1
    payload["Spec"]["Name"] = "LaaS-debug-test2"
    rc2 = s.post("https://172.16.146.117/move/v2/plans", json=payload, timeout=30)
    print(f"Status: {rc2.status_code}")
    print(f"Response: {rc2.text[:500]}")
