from nutanix_move_client import MoveClient
import json, time
c = MoveClient()
c.login()

plan_name = f"LaaS-{int(time.time())}"

payload = {
    "Spec": {
        "Name": plan_name,
        "SourceInfo": {
            "ProviderUUID": "04d468bb-3de8-4d9e-8cac-c35cfaed413d"
        },
        "TargetInfo": {
            "ProviderUUID": "d6b7cb76-e75d-4376-88d0-c9d5c43c8a3b",
            "AOSProviderAttrs": {
                "ClusterUUID": "00055313-e41c-5c5b-0000-00000000e8db",
                "ContainerUUID": "34f254d4-4dc3-4a2c-b389-692c1aa4092e"
            }
        },
        "Workload": {
            "Type": "VM",
            "VMs": [
                {
                    "VMReference": {
                        "UUID": "50015261-66ba-2f07-c92b-d6d89aace9eb",
                        "VMID": "vm-268873",
                        "VMName": "sdxdclrhel8-66"
                    },
                    "GuestPrepMode": "auto",
                    "VMPriority": "High"
                }
            ]
        },
        "NetworkMappings": [
            {
                "SourceNetworkID": "DPortGroup1285",
                "TargetNetworkID": "b5144cfe-0291-4f3f-8925-a768aa5edf67"
            }
        ],
        "Settings": {
            "GuestPrepMode": "auto",
            "NicConfigMode": "dhcp",
            "Schedule": {"ScheduleAtEpochSec": -1}
        }
    }
}

print(f"Creating plan: {plan_name}")
r = c.s.post(f"{c.base}/move/v2/plans", json=payload, timeout=15)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:1000]}")

if r.status_code in (200, 201):
    # Get the created plan
    plan_data = r.json()
    print(f"\nPlan created successfully!")
    print(json.dumps(plan_data, indent=2)[:500])
