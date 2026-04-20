from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
provs = c.list_providers()
for p in provs.get("Entities", []):
    md = p.get("MetaData", {})
    spec = p.get("Spec", {})
    name = spec.get("Name", "?")
    ptype = spec.get("Type", "?")
    uuid = spec.get("UUID") or md.get("UUID")
    # Get IP
    ip = ""
    esx = spec.get("ESXAccessInfo", {})
    aos = spec.get("AOSAccessInfo", {})
    if esx:
        ip = esx.get("IPorFQDN", "")
    if aos:
        ip = aos.get("IPorFQDN", "")
    print(f"  {name:20s} Type={ptype:30s} IP={ip:20s} UUID={uuid}  Workloads={md.get('NumDiscoveredWorkloads',0)}")

# Find VM sdxdclrhel8-66 in source provider
print("\n--- Searching for sdxdclrhel8-66 in source provider ---")
source_uuid = "475d2544-10e2-41b3-814f-2175c971a44b"
try:
    r = c._api("POST", f"/move/v2/providers/{source_uuid}/workloads", json={"Spec":{"WorkloadType":"VM"}})
    entities = r.get("Entities", [])
    print(f"Total VMs: {len(entities)}")
    for e in entities:
        md = e.get("MetaData", {})
        vm_name = md.get("Name", "")
        if "sdxdcl" in vm_name.lower():
            print(f"  VM: {vm_name}  UUID={md.get('UUID')}  MoRef={md.get('VMwareVMID','')}")
except Exception as ex:
    print(f"Error: {ex}")
