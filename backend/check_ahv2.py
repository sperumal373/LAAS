from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()

# Get workloads from target provider to see if VM exists
uuid = "88158af3-a456-4758-ba1d-7e5047c06c74"

# Try to get VM details from the completed plan
try:
    r = c._api("GET", f"/move/v2/plans/{uuid}")
    md = r.get("MetaData",{})
    spec = r.get("Spec",{})
    vms = spec.get("Workload",{}).get("VMs",[])
    print(f"Plan State: {md.get('StateString')}")
    print(f"Plan Status: {md.get('StatusString')}")
    print(f"VM count: {md.get('NumVMs')}")
    print(f"VMStateCounts: {md.get('VMStateCounts')}")
    for v in vms:
        ref = v.get("VMReference",{})
        print(f"  VM UUID: {ref.get('UUID')}")
        print(f"  VM ID: {ref.get('VMID')}")
        print(f"  VM Name: {ref.get('VMName','N/A')}")
except Exception as e:
    print(f"Error: {e}")

# Check target provider for discovered workloads
target_uuid = "d6b7cb76-e75d-4376-88d0-c9d5c43c8a3b"
try:
    r = c._api("POST", f"/move/v2/providers/{target_uuid}/vms/list", json={"Spec":{}})
    entities = r.get("Entities",[])
    print(f"\nTarget provider VMs: {len(entities)}")
    for e in entities:
        name = e.get("MetaData",{}).get("VMName","") or e.get("VMName","")
        if "sdxdcl" in str(e).lower():
            print(f"  FOUND: {json.dumps(e, indent=2)[:500]}")
except Exception as ex:
    print(f"Target VM list error: {ex}")

# Also check source provider for the VM
source_uuid = "475d2544-10e2-41b3-814f-2175c971a44b"
try:
    r = c._api("POST", f"/move/v2/providers/{source_uuid}/vms/list", json={"Spec":{}})
    entities = r.get("Entities",[])
    print(f"\nSource provider VMs: {len(entities)}")
    for e in entities:
        if "sdxdcl" in str(e).lower()[:500]:
            print(f"  FOUND: {json.dumps(e, indent=2)[:500]}")
except Exception as ex:
    print(f"Source VM list error: {ex}")
