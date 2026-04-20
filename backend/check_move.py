from nutanix_move_client import MoveClient, is_move_reachable
import json
print("Reachable:", is_move_reachable())
c = MoveClient()
print("Login:", c.login())
provs = c.list_providers()
plist = provs.get("Entities", [])
print(f"Providers ({len(plist)}):")
for p in plist:
    md = p.get("MetaData", {})
    print(f"  Name: {md.get('Name')}  Type: {md.get('Type')}  IP: {md.get('IP','')}")
plans = c.list_plans()
entities = plans.get("Entities", [])
print(f"Plans ({len(entities)}):")
for pl in entities:
    md = pl.get("MetaData", {})
    name = md.get("Name", "")
    if "test2026" in name.lower() or "sdxdcl" in name.lower():
        print(f"  MATCH: {name}  Status: {md.get('Status')}")
