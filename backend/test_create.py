from nutanix_move_client import MoveClient
import json, time
c = MoveClient()
c.login()

# Correct provider mapping:
# VMware-rookie (172.17.168.212) UUID=04d468bb-3de8-4d9e-8cac-c35cfaed413d
# AHV-T10 (172.16.144.100) UUID=d6b7cb76-e75d-4376-88d0-c9d5c43c8a3b
# Cluster SDxDC2-AHV UUID=00055313-e41c-5c5b-0000-00000000e8db
# Container UUID=34f254d4-4dc3-4a2c-b389-692c1aa4092e (from existing plan)

# Try creating plan with proper format (matching existing Test2026 structure)
plan_name = f"LaaS-Test-{int(time.time())}"
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
                        "VMName": "sdxdclrhel8-66"
                    }
                }
            ]
        },
        "Settings": {
            "GuestPrepMode": "auto",
            "NicConfigMode": "dhcp"
        }
    }
}

print(f"Creating plan: {plan_name}")
print(f"Payload: {json.dumps(payload, indent=2)}")
try:
    r = c.s.post(f"{c.base}/move/v2/plans", json=payload, timeout=15)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:1000]}")
except Exception as ex:
    print(f"Error: {ex}")
