from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()

# Try the provider detail endpoint
source_uuid = "04d468bb-3de8-4d9e-8cac-c35cfaed413d"
try:
    r = c._api("GET", f"/move/v2/providers/{source_uuid}")
    spec = r.get("Spec", {})
    print(f"Provider name: {spec.get('Name')}")
    print(f"ESX IP: {spec.get('ESXAccessInfo',{}).get('IPorFQDN')}")
except Exception as ex:
    print(f"Provider detail: {ex}")

# Try workloads/list with POST body
try:
    r = c._api("POST", f"/move/v2/workloads/list", json={"Spec":{"ProviderUUID":source_uuid,"Type":"VM"}})
    entities = r.get("Entities", [])
    print(f"Workloads: {len(entities)}")
    for e in entities:
        if "sdxdcl" in json.dumps(e).lower():
            print(f"  FOUND: {json.dumps(e, indent=2)[:500]}")
except Exception as ex:
    print(f"workloads/list: {ex}")

# Try the existing Test2026 plan to see how it references the VM  
r = c._api("GET", "/move/v2/plans/88158af3-a456-4758-ba1d-7e5047c06c74")
vms = r.get("Spec",{}).get("Workload",{}).get("VMs",[])
print(f"\nTest2026 VMs:")
for v in vms:
    ref = v.get("VMReference",{})
    print(f"  UUID: {ref.get('UUID')}")
    print(f"  VMID: {ref.get('VMID')}")
    print(json.dumps(v, indent=2)[:500])
