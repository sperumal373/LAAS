import sys, re
sys.stdout.reconfigure(encoding="utf-8")

#  1. zerto_client.py: add get_virt_site_vms + update create_vpg 
with open(r"C:\caas-dashboard\backend\zerto_client.py","rb") as f:
    zt = f.read().decode("utf-8-sig")

# Add get_virt_site_vms after get_local_site
ADD_FN = """
def get_virt_site_vms(site_id, virt_site_id):
    \"\"\"List all VMs visible to Zerto at a virtualization site (vCenter inventory).\"\"\"
    try:
        return _zapi(site_id, "/virtualizationsites/%s/vms" % virt_site_id) or []
    except Exception as e:
        return {"error": str(e)}

def get_virt_sites(site_id):
    \"\"\"List all virtualization sites (vCenters) known to this ZVM.\"\"\"
    try:
        return _zapi(site_id, "/virtualizationsites") or []
    except Exception as e:
        return {"error": str(e)}

"""

zt = zt.replace(
    "def get_peer_sites(site_id):\n    try: return _zapi(site_id, \"/peersites\") or []\n    except Exception as e: return {\"error\":str(e)}\n\ndef list_checkpoints",
    "def get_peer_sites(site_id):\n    try: return _zapi(site_id, \"/peersites\") or []\n    except Exception as e: return {\"error\":str(e)}\n" + ADD_FN + "def list_checkpoints"
)

# Update create_vpg to accept vms list (first occurrence only)
OLD_VMS = '"Vms": []\n        }\n        result = _zapi(site_id, "vpgsettings", method="POST", body=body)'
NEW_VMS = (
    '"Vms": [{"VmIdentifier": vid} for vid in payload.get("vm_ids", [])]\n'
    '        }\n'
    '        result = _zapi(site_id, "vpgsettings", method="POST", body=body)'
)
zt = zt.replace(OLD_VMS, NEW_VMS, 1)

with open(r"C:\caas-dashboard\backend\zerto_client.py","wb") as f:
    f.write(zt.encode("utf-8-sig"))
print("zerto_client patched:", "get_virt_site_vms" in zt, "vm_ids" in zt)

#  2. main.py: add /virtualizationsites + /localsite routes 
with open(r"C:\caas-dashboard\backend\main.py","rb") as f:
    mt = f.read().decode("utf-8-sig")

NEW_ROUTES = """
@app.get("/api/zerto/sites/{site_id}/localsite")
async def zerto_localsite(site_id: int, current_user=Depends(get_current_user)):
    from zerto_client import get_local_site
    return get_local_site(site_id)

@app.get("/api/zerto/sites/{site_id}/virtualizationsites")
async def zerto_virtsites(site_id: int, current_user=Depends(get_current_user)):
    from zerto_client import get_virt_sites
    return get_virt_sites(site_id)

@app.get("/api/zerto/sites/{site_id}/virtualizationsites/{virt_site_id}/vms")
async def zerto_virt_vms(site_id: int, virt_site_id: str, current_user=Depends(get_current_user)):
    from zerto_client import get_virt_site_vms
    return get_virt_site_vms(site_id, virt_site_id)

"""

# Insert before the audit route
mt = mt.replace(
    '@app.get("/api/zerto/sites/{site_id}/audit")',
    NEW_ROUTES + '@app.get("/api/zerto/sites/{site_id}/audit")'
)

with open(r"C:\caas-dashboard\backend\main.py","wb") as f:
    f.write(mt.encode("utf-8-sig"))
print("main.py patched:", "virtualizationsites" in mt)