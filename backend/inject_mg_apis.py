f = 'main.py'
raw = open(f, 'rb').read()

# Check if already done
if b'def create_move_group' in raw:
    print('APIs already added')
    exit()

# Find insertion point - after list_move_groups (which we just added)
# Find the last move-groups endpoint we added and insert remaining after
marker = b'    return groups\r\n\r\n'
# Find it
idx = raw.find(marker)
if idx < 0:
    print('ERROR: cannot find insertion point')
    exit()
insert_at = idx + len(marker)

api_code = """
@app.post("/api/migration/move-groups")
def create_move_group(req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    name = req.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Group name is required")
    with get_conn() as c:
        c.execute("INSERT INTO move_groups (name, description, created_by) VALUES (?,?,?)",
                  (name, req.get("description",""), u.get("username","admin")))
        gid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"ok": True, "id": gid, "message": "Move group created"}

@app.delete("/api/migration/move-groups/{group_id}")
def delete_move_group(group_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    with get_conn() as c:
        c.execute("DELETE FROM move_group_vms WHERE group_id=?", (group_id,))
        c.execute("DELETE FROM move_groups WHERE id=?", (group_id,))
    return {"ok": True}

@app.post("/api/migration/move-groups/{group_id}/vms")
def add_vms_to_group(group_id: int, req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    vms = req.get("vms", [])
    vcenter_id = req.get("vcenter_id", "")
    vcenter_name = req.get("vcenter_name", "")
    added = 0
    with get_conn() as c:
        for vm in vms:
            exists = c.execute("SELECT id FROM move_group_vms WHERE group_id=? AND vm_name=? AND vcenter_id=?",
                               (group_id, vm.get("name",""), vcenter_id)).fetchone()
            if exists: continue
            c.execute('''INSERT INTO move_group_vms
                (group_id, vm_name, vm_moref, vcenter_id, vcenter_name, guest_os, cpu, memory_mb, disk_gb, power_state, ip_address, esxi_host)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
                (group_id, vm.get("name",""), vm.get("moref",""), vcenter_id, vcenter_name,
                 vm.get("guest_os",""), vm.get("cpu",0), vm.get("memory_mb",0), vm.get("disk_gb",0),
                 vm.get("power_state",""), vm.get("ip_address",""), vm.get("esxi_host","")))
            added += 1
        c.execute("UPDATE move_groups SET updated_at=datetime('now') WHERE id=?", (group_id,))
    return {"ok": True, "added": added}

@app.delete("/api/migration/move-groups/{group_id}/vms/{vm_id}")
def remove_vm_from_group(group_id: int, vm_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    with get_conn() as c:
        c.execute("DELETE FROM move_group_vms WHERE id=? AND group_id=?", (vm_id, group_id))
        c.execute("UPDATE move_groups SET updated_at=datetime('now') WHERE id=?", (group_id,))
    return {"ok": True}

@app.post("/api/migration/move-groups/{group_id}/migrate")
def migrate_move_group(group_id: int, req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    from datetime import datetime
    username = u.get("username", "admin")
    target_platform = req.get("target_platform", "")
    target_detail = req.get("target_detail", {})
    options = req.get("options", {})
    if not target_platform: raise HTTPException(400, "target_platform is required")
    with get_conn() as c:
        group = c.execute("SELECT * FROM move_groups WHERE id=?", (group_id,)).fetchone()
        if not group: raise HTTPException(404, "Move group not found")
        vms = [dict(v) for v in c.execute("SELECT * FROM move_group_vms WHERE group_id=?", (group_id,)).fetchall()]
        if not vms: raise HTTPException(400, "No VMs in this group")
        by_vc = {}
        for vm in vms:
            vc = vm.get("vcenter_id") or "unknown"
            by_vc.setdefault(vc, []).append(vm)
        plan_ids = []
        for vc_id, vc_vms in by_vc.items():
            vc_name = vc_vms[0].get("vcenter_name") or vc_id
            suffix = f" ({vc_name})" if len(by_vc) > 1 else ""
            plan_name = f"{dict(group)['name']}{suffix}"
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            init_log = _json.dumps([{"ts": ts, "msg": f"Plan from move group by {username}", "user": username}])
            vm_list = [{"name": v["vm_name"], "moref": v.get("vm_moref",""), "guest_os": v.get("guest_os",""),
                        "cpu": v.get("cpu",0), "memory_mb": v.get("memory_mb",0), "disk_gb": v.get("disk_gb",0),
                        "power_state": v.get("power_state",""), "ip_address": v.get("ip_address",""),
                        "esxi_host": v.get("esxi_host","")} for v in vc_vms]
            source_vc = {"id": vc_id, "name": vc_name}
            c.execute('''INSERT INTO migration_plans
                (plan_name, source_platform, source_vcenter, target_platform,
                 target_detail, vm_list, status, notes, created_by, event_log, options)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (plan_name, "vmware", _json.dumps(source_vc), target_platform,
                 _json.dumps(target_detail), _json.dumps(vm_list),
                 "planned", f"From move group: {dict(group)['name']}", username, init_log, _json.dumps(options)))
            pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            plan_ids.append(pid)
    return {"ok": True, "plan_ids": plan_ids, "plans_created": len(plan_ids)}

"""
# Convert to CRLF bytes
api_bytes = api_code.replace('\n', '\r\n').encode('utf-8')
raw = raw[:insert_at] + api_bytes + raw[insert_at:]
open(f, 'wb').write(raw)
print('All move group APIs added! Size:', len(raw))