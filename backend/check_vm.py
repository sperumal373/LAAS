from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()

# The source vCenter is 172.17.168.212 = VMware-rookie
source_uuid = "04d468bb-3de8-4d9e-8cac-c35cfaed413d"

# Try different endpoints to list VMs
for path in [
    f"/move/v2/providers/{source_uuid}/vms",
    f"/move/v2/providers/vms/list",
]:
    try:
        r = c._api("POST", path, json={"Spec":{"ProviderUUID": source_uuid}})
        print(f"POST {path}: OK, keys={list(r.keys())[:5]}")
        entities = r.get("Entities", [])
        print(f"  Entities: {len(entities)}")
        for e in entities[:2]:
            print(f"  Sample: {json.dumps(e, indent=2)[:300]}")
        # Search for our VM
        for e in entities:
            s = json.dumps(e).lower()
            if "sdxdcl" in s:
                print(f"  FOUND VM: {json.dumps(e, indent=2)[:500]}")
        break
    except Exception as ex:
        print(f"POST {path}: {ex}")

# Try GET
try:
    r = c._api("GET", f"/move/v2/providers/{source_uuid}/vms")
    print(f"GET vms: {type(r)}")
    if isinstance(r, dict):
        entities = r.get("Entities", [])
        print(f"  Entities: {len(entities)}")
except Exception as ex:
    print(f"GET vms: {ex}")
