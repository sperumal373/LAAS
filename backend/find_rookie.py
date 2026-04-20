from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
plans = c.list_plans()
for p in plans.get("Entities", []):
    md = p.get("MetaData", {})
    src = md.get("SourceInfo", {})
    if src.get("Name") == "VMware-rookie":
        print(f"  {md.get('Name'):30s} State={md.get('StateString'):40s} VMs={md.get('NumVMs')} Data={md.get('DataInBytes',0)/1073741824:.1f}GB")
