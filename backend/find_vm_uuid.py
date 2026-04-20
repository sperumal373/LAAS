from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()

# The VM sdxdclrhel8-66 should be discoverable from the source provider
# Try inventory/refresh and then search
source_uuid = "04d468bb-3de8-4d9e-8cac-c35cfaed413d"

# Try various Move API endpoints to find VMs
endpoints = [
    ("POST", f"/move/v2/providers/{source_uuid}/vms/list", {"Spec":{}}),
    ("POST", f"/move/v2/providers/{source_uuid}/inventory", {"Spec":{"Search":"sdxdclrhel8-66"}}),
    ("POST", f"/move/v2/providers/{source_uuid}/search", {"Spec":{"Query":"sdxdclrhel8-66"}}),
    ("GET", f"/move/v2/providers/{source_uuid}/inventory", None),
]
for method, path, body in endpoints:
    try:
        if body:
            r = c._api(method, path, json=body)
        else:
            r = c._api(method, path)
        print(f"{method} {path}: OK")
        print(f"  {json.dumps(r, indent=2)[:500]}")
    except Exception as ex:
        print(f"{method} {path}: {ex}")
