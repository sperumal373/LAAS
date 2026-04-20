from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "88158af3-a456-4758-ba1d-7e5047c06c74"
try:
    r = c._api("GET", f"/move/v2/plans/{uuid}")
    print(json.dumps(r, indent=2)[:3000])
except Exception as e:
    print(f"GET plan failed: {e}")
try:
    r = c._api("POST", f"/move/v2/plans/{uuid}/vms", json={"Spec":{}})
    print(json.dumps(r, indent=2)[:3000])
except Exception as e:
    print(f"POST vms failed: {e}")
