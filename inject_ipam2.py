"""inject_ipam2.py – Inject IPAM2 (PostgreSQL) routes into main.py"""
import re

MAIN = r"c:\caas-dashboard\backend\main.py"
content = open(MAIN, encoding="utf-8").read()

# Check if already injected
if "ipam2" in content:
    print("Already injected, skipping.")
    exit(0)

# ── New import line to add ────────────────────────────────────────────────────
OLD_IMPORT = "from ipam_client import get_ipam_subnets, get_ipam_subnet_ips"
NEW_IMPORT = (
    "from ipam_client import get_ipam_subnets, get_ipam_subnet_ips\n"
    "import ipam_pg as _ipam_pg"
)
content = content.replace(OLD_IMPORT, NEW_IMPORT, 1)

# ── New routes to inject ──────────────────────────────────────────────────────
INJECT_AFTER = "    _save_manual_subnets(entries)\n    return {\"status\": \"ok\"}"

NEW_ROUTES = r'''    _save_manual_subnets(entries)
    return {"status": "ok"}


# ────────────────────────────────────────────────────────────────────────────────
#  IPAM v2 — Self-hosted PostgreSQL IPAM  (DC / DR VLANs + IP management)
# ────────────────────────────────────────────────────────────────────────────────
# Initialize schema once on startup
try:
    _ipam_pg.init_ipam_schema()
except Exception as _e:
    log.warning(f"[ipam2] Schema init deferred: {_e}")

class IPAMv2UpdateIP(BaseModel):
    status:       str = None
    hostname:     str = None
    mac_address:  str = None
    device_type:  str = None
    dns_forward:  str = None
    dns_reverse:  str = None
    owner:        str = None
    description:  str = None
    remarks:      str = None

class IPAMv2BulkUpdate(BaseModel):
    ip_ids: list
    update: IPAMv2UpdateIP

class IPAMv2CreateVLAN(BaseModel):
    site:        str
    vlan_id:     int
    name:        str = ""
    subnet:      str
    gateway:     str = ""
    description: str = ""
    notes:       str = ""
    vrf:         str = ""

class IPAMv2UpdateVLAN(BaseModel):
    name:        str = ""
    description: str = ""
    notes:       str = ""
    vrf:         str = ""

@app.get("/api/ipam2/summary")
def ipam2_summary(u=Depends(get_current_user)):
    """Overall IPAM statistics."""
    try:
        return _ipam_pg.get_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ipam2/vlans")
def ipam2_vlans(site: str = None, u=Depends(get_current_user)):
    """List all VLANs with IP counts per status."""
    try:
        return _ipam_pg.list_vlans(site=site)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ipam2/vlans")
def ipam2_create_vlan(body: IPAMv2CreateVLAN, u=Depends(require_role("admin"))):
    """Create a new VLAN and seed its IPs."""
    try:
        row = _ipam_pg.create_vlan(body.dict())
        audit(u["username"], "IPAM2_VLAN_CREATE", detail=f"{body.site} VLAN {body.vlan_id} {body.subnet}")
        return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/ipam2/vlans/{vlan_db_id}")
def ipam2_update_vlan(vlan_db_id: int, body: IPAMv2UpdateVLAN, u=Depends(require_role("admin"))):
    """Update VLAN metadata."""
    try:
        row = _ipam_pg.update_vlan(vlan_db_id, body.dict())
        if not row:
            raise HTTPException(status_code=404, detail="VLAN not found")
        audit(u["username"], "IPAM2_VLAN_UPDATE", detail=f"id={vlan_db_id}")
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/ipam2/vlans/{vlan_db_id}")
def ipam2_delete_vlan(vlan_db_id: int, u=Depends(require_role("admin"))):
    """Delete a VLAN and all its IPs."""
    try:
        ok = _ipam_pg.delete_vlan(vlan_db_id)
        if not ok:
            raise HTTPException(status_code=404, detail="VLAN not found")
        audit(u["username"], "IPAM2_VLAN_DELETE", detail=f"id={vlan_db_id}")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ipam2/vlans/{vlan_db_id}/ips")
def ipam2_list_ips(vlan_db_id: int, status: str = None, q: str = None, u=Depends(get_current_user)):
    """List IP addresses in a VLAN."""
    try:
        return _ipam_pg.list_ips(vlan_db_id, status=status, q=q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/ipam2/ips/{ip_id}")
def ipam2_update_ip(ip_id: int, body: IPAMv2UpdateIP, u=Depends(require_role("admin", "operator"))):
    """Update a single IP address record."""
    try:
        data = {k: v for k, v in body.dict().items() if v is not None}
        row = _ipam_pg.update_ip(ip_id, data, changed_by=u["username"])
        if not row:
            raise HTTPException(status_code=404, detail="IP not found")
        audit(u["username"], "IPAM2_IP_UPDATE", detail=f"id={ip_id} {data}")
        return row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ipam2/ips/bulk-update")
def ipam2_bulk_update(body: IPAMv2BulkUpdate, u=Depends(require_role("admin", "operator"))):
    """Bulk-update multiple IP records."""
    try:
        data = {k: v for k, v in body.update.dict().items() if v is not None}
        count = _ipam_pg.bulk_update_ips(body.ip_ids, data, changed_by=u["username"])
        audit(u["username"], "IPAM2_BULK_UPDATE", detail=f"{count} IPs {data}")
        return {"updated": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ipam2/vlans/{vlan_db_id}/ping")
def ipam2_ping(vlan_db_id: int, u=Depends(require_role("admin", "operator"))):
    """Ping all IPs in a VLAN and update ping status (runs in background)."""
    import threading as _threading
    def _do_ping():
        try:
            _ipam_pg.ping_and_save(vlan_db_id)
        except Exception as e:
            log.error(f"[ipam2] ping failed: {e}")
    t = _threading.Thread(target=_do_ping, daemon=True)
    t.start()
    return {"status": "started", "vlan_db_id": vlan_db_id}

@app.post("/api/ipam2/vlans/{vlan_db_id}/dns-lookup")
def ipam2_dns_lookup(vlan_db_id: int, u=Depends(require_role("admin", "operator"))):
    """Run DNS lookups for all IPs in a VLAN (runs in background)."""
    import threading as _threading
    def _do_dns():
        try:
            _ipam_pg.dns_lookup_and_save(vlan_db_id, changed_by=u["username"])
        except Exception as e:
            log.error(f"[ipam2] dns lookup failed: {e}")
    t = _threading.Thread(target=_do_dns, daemon=True)
    t.start()
    return {"status": "started", "vlan_db_id": vlan_db_id}

@app.get("/api/ipam2/changelog")
def ipam2_changelog(vlan_db_id: int = None, limit: int = 200, u=Depends(get_current_user)):
    """Return IPAM change history."""
    try:
        return _ipam_pg.list_changelog(vlan_db_id=vlan_db_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ipam2/conflicts")
def ipam2_conflicts(u=Depends(get_current_user)):
    """Detect duplicate IPs or hostname conflicts."""
    try:
        return _ipam_pg.list_conflicts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))'''

content = content.replace(INJECT_AFTER, NEW_ROUTES, 1)

open(MAIN, "w", encoding="utf-8").write(content)
print("DONE – ipam2 routes injected into main.py")
'''
# Verify
import subprocess
result = subprocess.run(["python", "-c", f"import ast; ast.parse(open(r'{MAIN}').read()); print('Syntax OK')"], capture_output=True, text=True)
print(result.stdout or result.stderr)
'''
