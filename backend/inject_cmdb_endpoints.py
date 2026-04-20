"""
Append CMDB API endpoints to main.py
"""

CMDB_ENDPOINTS = '''
    return {"ok": True, "message": "IPAM collection started in background"}


# ═══════════════════════════════════════════════════════════════════════════════
# CMDB – Configuration Management Database
# ═══════════════════════════════════════════════════════════════════════════════

import cmdb_client as _cmdb

# Init CMDB tables on first import
try:
    _cmdb.init_cmdb_db()
except Exception as _e:
    logging.warning(f"CMDB DB init warning: {_e}")


class _SNConfig(BaseModel):
    instance_url:    str
    username:        str
    password:        str
    client_id:       str = ""
    client_secret:   str = ""
    default_company: str = "SDx-COE"
    default_bu:      str = "SDx-COE"
    push_vm:         bool = True
    push_host:       bool = True
    push_storage:    bool = True
    push_network:    bool = True
    push_physical:   bool = True


class _CIEdit(BaseModel):
    name:               str | None = None
    operational_status: str | None = None
    environment:        str | None = None
    department:         str | None = None
    business_unit:      str | None = None
    company:            str | None = None
    location:           str | None = None
    ip_address:         str | None = None
    fqdn:               str | None = None
    os:                 str | None = None
    os_version:         str | None = None
    serial_number:      str | None = None
    model_id:           str | None = None
    manufacturer:       str | None = None
    asset_tag:          str | None = None
    cpu_count:          int | None = None
    cpu_core_count:     int | None = None
    ram_mb:             int | None = None
    disk_space_gb:      float | None = None


@app.get("/api/cmdb/summary")
def cmdb_summary(u=Depends(get_current_user)):
    """Overall CMDB statistics."""
    try:
        return _cmdb.get_ci_summary()
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/api/cmdb/cis")
def cmdb_list_cis(
    cls: str = None, platform: str = None, search: str = None,
    limit: int = 500, offset: int = 0,
    u=Depends(get_current_user)
):
    """List CIs with optional filters."""
    try:
        return {"items": _cmdb.list_cis(cls, platform, search, limit, offset)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/cmdb/collect")
def cmdb_collect_now(u=Depends(require_role("admin", "operator"))):
    """Trigger CMDB CI collection from all platforms in background."""
    import threading

    def _run():
        try:
            result = _cmdb.collect_all_cis()
            logging.info(f"CMDB manual collect: {result['total']} CIs collected")
        except Exception as e:
            logging.error(f"CMDB collect background: {e}")

    threading.Thread(target=_run, daemon=True).start()
    audit(u["username"], "CMDB_COLLECT", target="manual", role=u["role"])
    return {"ok": True, "message": "CMDB collection started in background"}


@app.patch("/api/cmdb/cis/{ci_id}")
def cmdb_update_ci(ci_id: int, body: _CIEdit, u=Depends(require_role("admin"))):
    """Admin-only: update a CI record."""
    fields = {k: v for k, v in body.dict().items() if v is not None}
    result = _cmdb.update_ci(ci_id, fields)
    audit(u["username"], "CMDB_CI_EDIT", target=str(ci_id), role=u["role"])
    return result


@app.get("/api/cmdb/sn-config")
def cmdb_get_sn_config(u=Depends(require_role("admin"))):
    """Get ServiceNow integration config (password masked)."""
    cfg = _cmdb.get_sn_config()
    if "password" in cfg:
        cfg["password"] = "••••••••" if cfg["password"] else ""
    return cfg


@app.post("/api/cmdb/sn-config")
def cmdb_save_sn_config(body: _SNConfig, u=Depends(require_role("admin"))):
    """Save ServiceNow integration credentials."""
    result = _cmdb.save_sn_config(body.dict())
    audit(u["username"], "CMDB_SN_CONFIG", target=body.instance_url, role=u["role"])
    return result


@app.post("/api/cmdb/push-to-sn")
def cmdb_push_to_sn(
    dry_run: bool = False,
    u=Depends(require_role("admin", "operator"))
):
    """Push all CIs to ServiceNow via Table API."""
    try:
        result = _cmdb.push_to_servicenow(dry_run=dry_run)
        audit(u["username"], "CMDB_SN_PUSH", target="servicenow",
              detail=f"pushed={result.get('pushed')}, errors={result.get('errors')}",
              role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))
'''

with open(r'c:\caas-dashboard\backend\main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the last return statement of collect_ipam_now
OLD_TAIL = '    threading.Thread(target=_run, daemon=True).start()\n    audit(u["username"], "IPAM_COLLECT", target="manual", role=u["role"])'
NEW_TAIL = CMDB_ENDPOINTS.strip()

# The file ends without a return after audit(), add it and then the CMDB block
REPLACEMENT = '''    threading.Thread(target=_run, daemon=True).start()
    audit(u["username"], "IPAM_COLLECT", target="manual", role=u["role"])
    return {"ok": True, "message": "IPAM collection started in background"}


# ═══════════════════════════════════════════════════════════════════════════════
# CMDB – Configuration Management Database
# ═══════════════════════════════════════════════════════════════════════════════

import cmdb_client as _cmdb

# Init CMDB tables on first import
try:
    _cmdb.init_cmdb_db()
except Exception as _e:
    logging.warning(f"CMDB DB init warning: {_e}")


class _SNConfig(BaseModel):
    instance_url:    str
    username:        str
    password:        str
    client_id:       str = ""
    client_secret:   str = ""
    default_company: str = "SDx-COE"
    default_bu:      str = "SDx-COE"
    push_vm:         bool = True
    push_host:       bool = True
    push_storage:    bool = True
    push_network:    bool = True
    push_physical:   bool = True


class _CIEdit(BaseModel):
    name:               str | None = None
    operational_status: str | None = None
    environment:        str | None = None
    department:         str | None = None
    business_unit:      str | None = None
    company:            str | None = None
    location:           str | None = None
    ip_address:         str | None = None
    fqdn:               str | None = None
    os:                 str | None = None
    os_version:         str | None = None
    serial_number:      str | None = None
    model_id:           str | None = None
    manufacturer:       str | None = None
    asset_tag:          str | None = None
    cpu_count:          int | None = None
    cpu_core_count:     int | None = None
    ram_mb:             int | None = None
    disk_space_gb:      float | None = None


@app.get("/api/cmdb/summary")
def cmdb_summary(u=Depends(get_current_user)):
    try:
        return _cmdb.get_ci_summary()
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/api/cmdb/cis")
def cmdb_list_cis(
    cls: str = None, platform: str = None, search: str = None,
    limit: int = 500, offset: int = 0,
    u=Depends(get_current_user)
):
    try:
        return {"items": _cmdb.list_cis(cls, platform, search, limit, offset)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/cmdb/collect")
def cmdb_collect_now(u=Depends(require_role("admin", "operator"))):
    import threading
    def _run():
        try:
            result = _cmdb.collect_all_cis()
            logging.info(f"CMDB manual collect: {result['total']} CIs")
        except Exception as e:
            logging.error(f"CMDB collect background: {e}")
    threading.Thread(target=_run, daemon=True).start()
    audit(u["username"], "CMDB_COLLECT", target="manual", role=u["role"])
    return {"ok": True, "message": "CMDB collection started in background"}


@app.patch("/api/cmdb/cis/{ci_id}")
def cmdb_update_ci(ci_id: int, body: _CIEdit, u=Depends(require_role("admin"))):
    fields = {k: v for k, v in body.dict().items() if v is not None}
    result = _cmdb.update_ci(ci_id, fields)
    audit(u["username"], "CMDB_CI_EDIT", target=str(ci_id), role=u["role"])
    return result


@app.get("/api/cmdb/sn-config")
def cmdb_get_sn_config(u=Depends(require_role("admin"))):
    cfg = _cmdb.get_sn_config()
    if cfg.get("password"):
        cfg["password"] = "••••••••"
    return cfg


@app.post("/api/cmdb/sn-config")
def cmdb_save_sn_config(body: _SNConfig, u=Depends(require_role("admin"))):
    result = _cmdb.save_sn_config(body.dict())
    audit(u["username"], "CMDB_SN_CONFIG", target=body.instance_url, role=u["role"])
    return result


@app.post("/api/cmdb/push-to-sn")
def cmdb_push_to_sn(dry_run: bool = False, u=Depends(require_role("admin", "operator"))):
    try:
        result = _cmdb.push_to_servicenow(dry_run=dry_run)
        audit(u["username"], "CMDB_SN_PUSH", target="servicenow",
              detail=f"pushed={result.get('pushed')}, errors={result.get('errors')}",
              role=u["role"])
        return result
    except Exception as e:
        raise HTTPException(500, detail=str(e))
'''

if OLD_TAIL in content:
    content = content.replace(OLD_TAIL, REPLACEMENT, 1)
    with open(r'c:\caas-dashboard\backend\main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    lines = content.count('\n') + 1
    print(f"SUCCESS: CMDB endpoints injected. New line count: {lines}")
else:
    print("OLD_TAIL not found - checking last 10 lines:")
    print(repr(content[-400:]))
