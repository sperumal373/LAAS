from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
# Check provider structure
provs = c.list_providers()
plist = provs.get("Entities", [])
if plist:
    print("Provider[0] keys:", json.dumps(plist[0], indent=2)[:600])
# Check Test2026 plan details
plans = c.list_plans()
for pl in plans.get("Entities", []):
    md = pl.get("MetaData", {})
    if md.get("Name") == "Test2026":
        print("\nTest2026 plan:")
        print(json.dumps(pl, indent=2)[:2000])
