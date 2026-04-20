from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
# Get VM details from Test2026 plan
data = c._api("POST", "/move/v2/plans/list", json={"Spec": {}})
for pl in data.get("Entities", []):
    if pl.get("MetaData", {}).get("Name") == "Test2026":
        spec = pl.get("Spec", {})
        print("Spec keys:", list(spec.keys()))
        print(json.dumps(spec, indent=2)[:3000])
