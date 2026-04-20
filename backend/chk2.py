from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
# Find the LaaS plan
plans = c.list_plans()
for p in plans.get("Entities", []):
    md = p.get("MetaData", {})
    if "LaaS" in md.get("Name", ""):
        print(f"Name: {md.get('Name')}")
        print(f"State: {md.get('StateString')}")
        print(f"Status: {md.get('StatusString')}")
        print(f"Data: {md.get('MigratedDataInBytes',0)/1073741824:.1f} / {md.get('DataInBytes',0)/1073741824:.1f} GB")
        print(f"Elapsed: {md.get('ElapsedTime')}")
        print(f"VMStateCounts: {md.get('VMStateCounts')}")
        print(f"Errors: {md.get('ErrorReasons')}")
        print(f"UUID: {md.get('UUID')}")
        # Get full detail
        detail = c.get_plan(md.get("UUID"))
        vms = detail.get("Spec", {}).get("Workload", {}).get("VMs", [])
        for v in vms:
            ref = v.get("VMReference", {})
            print(f"  VM: {ref.get('VMName')} Status={v.get('Status','')} State={v.get('State','')}")
        print(json.dumps(md, indent=2)[:1000])
