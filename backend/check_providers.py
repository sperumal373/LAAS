from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()

# Get full provider details
provs = c.list_providers()
for p in provs.get("Entities", []):
    md = p.get("MetaData", {})
    spec = p.get("Spec", {})
    print(f"\n--- Provider UUID: {md.get('UUID')} ---")
    print(f"  Workloads: {md.get('NumDiscoveredWorkloads')}")
    # Check for vCenter info
    aos = spec.get("AOSAccessInfo", {})
    if aos:
        print(f"  AOS IP: {aos.get('IPorFQDN')}")
        for vc in aos.get("RegisteredVCAccessInfo", []):
            print(f"  vCenter: {vc.get('IPAddress')}  User: {vc.get('Username')}")
        print(f"  AOS User: {aos.get('Username')}")
    vc_info = spec.get("VCAccessInfo", {})
    if vc_info:
        print(f"  vCenter IP: {vc_info.get('IPorFQDN')}")
        print(f"  vCenter User: {vc_info.get('Username')}")
    # Print type hints
    print(f"  Spec keys: {list(spec.keys())}")

# Also get source provider workloads to find VM UUID
source_uuid = "475d2544-10e2-41b3-814f-2175c971a44b"
try:
    r = c._api("POST", f"/move/v2/providers/{source_uuid}/workloads", json={"Spec":{}})
    entities = r.get("Entities", [])
    print(f"\nSource workloads: {len(entities)}")
    for e in entities[:3]:
        print(json.dumps(e, indent=2)[:300])
except Exception as ex:
    # Try alternate endpoint
    try:
        r = c._api("GET", f"/move/v2/providers/{source_uuid}/vms")
        print(f"GET vms: {json.dumps(r, indent=2)[:500]}")
    except Exception as ex2:
        print(f"Workloads error: {ex}, GET vms error: {ex2}")
