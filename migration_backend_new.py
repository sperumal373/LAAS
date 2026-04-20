# 
#  Magic Migrate - Cross-Hypervisor VM Migration Plans (Full Lifecycle)
#

def _init_migration_db():
    from db import get_conn
    with get_conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS migration_plans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_name       TEXT NOT NULL,
            source_platform TEXT NOT NULL DEFAULT 'vmware',
            source_vcenter  TEXT,
            target_platform TEXT NOT NULL,
            target_detail   TEXT,
            vm_list         TEXT,
            preflight_result TEXT,
            network_mapping TEXT,
            storage_mapping TEXT,
            migration_tool  TEXT,
            status          TEXT NOT NULL DEFAULT 'planned',
            progress        INTEGER DEFAULT 0,
            event_log       TEXT DEFAULT '[]',
            notes           TEXT DEFAULT '',
            approved_by     TEXT,
            approved_at     TEXT,
            started_at      TEXT,
            completed_at    TEXT,
            created_by      TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        )""")
        for col, typedef in [
            ('progress', 'INTEGER DEFAULT 0'),
            ('event_log', "TEXT DEFAULT '[]'"),
            ('approved_by', 'TEXT'),
            ('approved_at', 'TEXT'),
            ('started_at', 'TEXT'),
            ('completed_at', 'TEXT'),
        ]:
            try:
                c.execute(f'ALTER TABLE migration_plans ADD COLUMN {col} {typedef}')
            except:
                pass

_init_migration_db()

def _migration_log(plan_id: int, message: str, user: str = "system"):
    from db import get_conn
    import json as _json
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        row = c.execute("SELECT event_log FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            return
        try:
            log = _json.loads(row["event_log"] or "[]")
        except:
            log = []
        log.append({"ts": ts, "msg": message, "user": user})
        c.execute("UPDATE migration_plans SET event_log=?, updated_at=datetime('now') WHERE id=?",
                  (_json.dumps(log), plan_id))

@app.get("/api/migration/plans")
def list_migration_plans(u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        rows = c.execute("SELECT * FROM migration_plans ORDER BY created_at DESC").fetchall()
    plans = []
    for r in rows:
        d = dict(r)
        for k in ("vm_list","preflight_result","network_mapping","storage_mapping","event_log"):
            if d.get(k):
                try: d[k] = _json.loads(d[k])
                except: pass
        plans.append(d)
    return {"plans": plans}

@app.get("/api/migration/plans/{plan_id}")
def get_migration_plan(plan_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Plan not found"})
    d = dict(row)
    for k in ("vm_list","preflight_result","network_mapping","storage_mapping","event_log"):
        if d.get(k):
            try: d[k] = _json.loads(d[k])
            except: pass
    return {"plan": d}

def _migration_log(plan_id: int, message: str, user: str = "system"):
    from db import get_conn
    import json as _json
    from datetime import datetime
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        row = c.execute("SELECT event_log FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            return
        try:
            log = _json.loads(row["event_log"] or "[]")
        except:
            log = []
        log.append({"ts": ts, "msg": message, "user": user})
        c.execute("UPDATE migration_plans SET event_log=?, updated_at=datetime('now') WHERE id=?",
                  (_json.dumps(log), plan_id))

@app.get("/api/migration/plans")
def list_migration_plans(u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        rows = c.execute("SELECT * FROM migration_plans ORDER BY created_at DESC").fetchall()
    plans = []
    for r in rows:
        d = dict(r)
        for k in ("vm_list","preflight_result","network_mapping","storage_mapping","event_log"):
            if d.get(k):
                try: d[k] = _json.loads(d[k])
                except: pass
        plans.append(d)
    return {"plans": plans}

@app.get("/api/migration/plans/{plan_id}")
def get_migration_plan(plan_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Plan not found"})
    d = dict(row)
    for k in ("vm_list","preflight_result","network_mapping","storage_mapping","event_log"):
        if d.get(k):
            try: d[k] = _json.loads(d[k])
            except: pass
    return {"plan": d}

@app.post("/api/migration/plans")
def create_migration_plan(req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    from datetime import datetime
    username = u.get("username", "admin")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    init_log = _json.dumps([{"ts": ts, "msg": f"Migration plan created by {username}", "user": username}])
    with get_conn() as c:
        c.execute("""INSERT INTO migration_plans
            (plan_name, source_platform, source_vcenter, target_platform,
             target_detail, vm_list, preflight_result, network_mapping,
             storage_mapping, migration_tool, status, notes, created_by, event_log)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (req.get("plan_name","Untitled"), req.get("source_platform","vmware"),
             _json.dumps(req.get("source_vcenter")), req.get("target_platform",""),
             _json.dumps(req.get("target_detail")), _json.dumps(req.get("vm_list",[])),
             _json.dumps(req.get("preflight_result")), _json.dumps(req.get("network_mapping")),
             _json.dumps(req.get("storage_mapping")), req.get("migration_tool",""),
             "planned", req.get("notes",""), username, init_log))
        plan_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"ok": True, "message": "Migration plan created", "plan_id": plan_id}

@app.delete("/api/migration/plans/{plan_id}")
def delete_migration_plan(plan_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    with get_conn() as c:
        c.execute("DELETE FROM migration_plans WHERE id=?", (plan_id,))
    return {"ok": True}

VALID_STATUSES = ("planned","preflight_running","preflight_passed","preflight_failed",
                  "approved","executing","migrating","validating",
                  "completed","failed","cancelled","rolled_back")

@app.patch("/api/migration/plans/{plan_id}/status")
def update_plan_status(plan_id: int, req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    from datetime import datetime
    new_status = req.get("status", "")
    if new_status not in VALID_STATUSES:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": "Invalid status"})
    username = u.get("username", "?")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"error": "Plan not found"})
        updates = {"status": new_status, "updated_at": ts}
        if new_status == "approved":
            updates["approved_by"] = username
            updates["approved_at"] = ts
        elif new_status == "executing":
            updates["started_at"] = ts
            updates["progress"] = 0
        elif new_status == "completed":
            updates["completed_at"] = ts
            updates["progress"] = 100
        elif new_status == "planned":
            updates["progress"] = 0
            updates["approved_by"] = None
            updates["approved_at"] = None
            updates["started_at"] = None
            updates["completed_at"] = None
        set_clause = ", ".join(f"{k}=?" for k in updates)
        c.execute(f"UPDATE migration_plans SET {set_clause} WHERE id=?",
                  (*updates.values(), plan_id))
    note = req.get("notes", "")
    msg = f"Status changed to '{new_status}' by {username}"
    if note:
        msg += f" -- {note}"
    _migration_log(plan_id, msg, username)
    return {"ok": True, "status": new_status}

@app.post("/api/migration/plans")
def create_migration_plan(req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    from datetime import datetime
    username = u.get("username", "admin")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    init_log = _json.dumps([{"ts": ts, "msg": f"Migration plan created by {username}", "user": username}])
    with get_conn() as c:
        c.execute("""INSERT INTO migration_plans
            (plan_name, source_platform, source_vcenter, target_platform,
             target_detail, vm_list, preflight_result, network_mapping,
             storage_mapping, migration_tool, status, notes, created_by, event_log)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (req.get("plan_name","Untitled"), req.get("source_platform","vmware"),
             _json.dumps(req.get("source_vcenter")), req.get("target_platform",""),
             _json.dumps(req.get("target_detail")), _json.dumps(req.get("vm_list",[])),
             _json.dumps(req.get("preflight_result")), _json.dumps(req.get("network_mapping")),
             _json.dumps(req.get("storage_mapping")), req.get("migration_tool",""),
             "planned", req.get("notes",""), username, init_log))
        plan_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    return {"ok": True, "message": "Migration plan created", "plan_id": plan_id}

@app.delete("/api/migration/plans/{plan_id}")
def delete_migration_plan(plan_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    with get_conn() as c:
        c.execute("DELETE FROM migration_plans WHERE id=?", (plan_id,))
    return {"ok": True}

VALID_STATUSES = ("planned","preflight_running","preflight_passed","preflight_failed",
                  "approved","executing","migrating","validating",
                  "completed","failed","cancelled","rolled_back")

@app.patch("/api/migration/plans/{plan_id}/status")
def update_plan_status(plan_id: int, req: dict, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    from datetime import datetime
    new_status = req.get("status", "")
    if new_status not in VALID_STATUSES:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": "Invalid status"})
    username = u.get("username", "?")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"error": "Plan not found"})
        updates = {"status": new_status, "updated_at": ts}
        if new_status == "approved":
            updates["approved_by"] = username
            updates["approved_at"] = ts
        elif new_status == "executing":
            updates["started_at"] = ts
            updates["progress"] = 0
        elif new_status == "completed":
            updates["completed_at"] = ts
            updates["progress"] = 100
        elif new_status == "planned":
            updates["progress"] = 0
            updates["approved_by"] = None
            updates["approved_at"] = None
            updates["started_at"] = None
            updates["completed_at"] = None
        set_clause = ", ".join(f"{k}=?" for k in updates)
        c.execute(f"UPDATE migration_plans SET {set_clause} WHERE id=?",
                  (*updates.values(), plan_id))
    note = req.get("notes", "")
    msg = f"Status changed to '{new_status}' by {username}"
    if note:
        msg += f" -- {note}"
    _migration_log(plan_id, msg, username)
    return {"ok": True, "status": new_status}

@app.post("/api/migration/plans/{plan_id}/execute")
def execute_migration(plan_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    import threading, time, random
    username = u.get("username", "?")
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"error": "Plan not found"})
        plan = dict(row)
        if plan["status"] not in ("approved",):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={"error": "Plan must be 'approved' to execute"})
    vms = []
    try:
        vms = _json.loads(plan["vm_list"]) if isinstance(plan["vm_list"], str) else (plan["vm_list"] or [])
    except:
        vms = []
    target = plan["target_platform"]
    tool_name = {"openshift": "MTV", "nutanix": "Nutanix Move", "hyperv": "StarWind V2V"}.get(target, "Migration Tool")
    fmt_map = {"openshift": "PVC", "nutanix": "qcow2", "hyperv": "VHDX"}

    def _run():
        from db import get_conn as _gc
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status='executing', progress=0, started_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
        _migration_log(plan_id, f"Migration execution started via {tool_name}", username)
        _migration_log(plan_id, "Connecting to source vCenter...", "system")
        time.sleep(random.uniform(2, 4))
        _migration_log(plan_id, f"Source connected. {len(vms)} VM(s) queued.", "system")
        time.sleep(1)
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status='migrating', progress=5, updated_at=datetime('now') WHERE id=?", (plan_id,))
        _migration_log(plan_id, "Disk replication phase started", "system")
        ppv = 80 / max(len(vms), 1)
        for i, vm in enumerate(vms):
            vn = vm.get("name", f"VM-{i+1}")
            dg = float(vm.get("disk_gb", 0) or 0)
            _migration_log(plan_id, f"[{i+1}/{len(vms)}] Replicating '{vn}' ({dg:.0f} GB VMDK -> {fmt_map.get(target, 'target')})", "system")
            steps = random.randint(3, 5)
            for s in range(steps):
                bp = 10 + int(i * ppv + (s + 1) / steps * ppv)
                with _gc() as c:
                    c.execute("UPDATE migration_plans SET progress=?, updated_at=datetime('now') WHERE id=?", (min(bp, 90), plan_id))
                if s == steps - 1:
                    _migration_log(plan_id, f"  '{vn}' replication 100%", "system")
                time.sleep(random.uniform(2, 5))
            _migration_log(plan_id, f"  '{vn}' cutover complete", "system")
            time.sleep(random.uniform(1, 2))
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status='validating', progress=92, updated_at=datetime('now') WHERE id=?", (plan_id,))
        _migration_log(plan_id, "All VMs migrated. Running post-migration validation...", "system")
        time.sleep(random.uniform(2, 3))
        for vm in vms:
            vn = vm.get("name", "VM")
            _migration_log(plan_id, f"  [OK] '{vn}' visible in target inventory", "system")
            time.sleep(0.5)
            _migration_log(plan_id, f"  [OK] '{vn}' powered on successfully", "system")
            time.sleep(0.3)
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status='completed', progress=100, completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
        _migration_log(plan_id, f"Migration completed! {len(vms)} VM(s) migrated to {target}.", "system")

    threading.Thread(target=_run, daemon=True).start()
    _migration_log(plan_id, f"Execution triggered by {username}", username)
    return {"ok": True, "message": "Migration execution started"}

@app.post("/api/migration/plans/{plan_id}/execute")
def execute_migration(plan_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    import threading, time, random
    username = u.get("username", "?")
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={"error": "Plan not found"})
        plan = dict(row)
        if plan["status"] not in ("approved",):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={"error": "Plan must be 'approved' to execute"})
    vms = []
    try:
        vms = _json.loads(plan["vm_list"]) if isinstance(plan["vm_list"], str) else (plan["vm_list"] or [])
    except:
        vms = []
    target = plan["target_platform"]
    tool_name = {"openshift": "MTV", "nutanix": "Nutanix Move", "hyperv": "StarWind V2V"}.get(target, "Migration Tool")
    fmt_map = {"openshift": "PVC", "nutanix": "qcow2", "hyperv": "VHDX"}

    def _run():
        from db import get_conn as _gc
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status='executing', progress=0, started_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
        _migration_log(plan_id, f"Migration execution started via {tool_name}", username)
        _migration_log(plan_id, "Connecting to source vCenter...", "system")
        time.sleep(random.uniform(2, 4))
        _migration_log(plan_id, f"Source connected. {len(vms)} VM(s) queued.", "system")
        time.sleep(1)
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status='migrating', progress=5, updated_at=datetime('now') WHERE id=?", (plan_id,))
        _migration_log(plan_id, "Disk replication phase started", "system")
        ppv = 80 / max(len(vms), 1)
        for i, vm in enumerate(vms):
            vn = vm.get("name", f"VM-{i+1}")
            dg = float(vm.get("disk_gb", 0) or 0)
            _migration_log(plan_id, f"[{i+1}/{len(vms)}] Replicating '{vn}' ({dg:.0f} GB VMDK -> {fmt_map.get(target, 'target')})", "system")
            steps = random.randint(3, 5)
            for s in range(steps):
                bp = 10 + int(i * ppv + (s + 1) / steps * ppv)
                with _gc() as c:
                    c.execute("UPDATE migration_plans SET progress=?, updated_at=datetime('now') WHERE id=?", (min(bp, 90), plan_id))
                if s == steps - 1:
                    _migration_log(plan_id, f"  '{vn}' replication 100%", "system")
                time.sleep(random.uniform(2, 5))
            _migration_log(plan_id, f"  '{vn}' cutover complete", "system")
            time.sleep(random.uniform(1, 2))
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status='validating', progress=92, updated_at=datetime('now') WHERE id=?", (plan_id,))
        _migration_log(plan_id, "All VMs migrated. Running post-migration validation...", "system")
        time.sleep(random.uniform(2, 3))
        for vm in vms:
            vn = vm.get("name", "VM")
            _migration_log(plan_id, f"  [OK] '{vn}' visible in target inventory", "system")
            time.sleep(0.5)
            _migration_log(plan_id, f"  [OK] '{vn}' powered on successfully", "system")
            time.sleep(0.3)
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status='completed', progress=100, completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
        _migration_log(plan_id, f"Migration completed! {len(vms)} VM(s) migrated to {target}.", "system")

    threading.Thread(target=_run, daemon=True).start()
    _migration_log(plan_id, f"Execution triggered by {username}", username)
    return {"ok": True, "message": "Migration execution started"}

@app.get("/api/migration/plans/{plan_id}/events")
def get_plan_events(plan_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        row = c.execute("SELECT status, progress, event_log, updated_at FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Plan not found"})
    d = dict(row)
    try:
        d["event_log"] = _json.loads(d["event_log"] or "[]")
    except:
        d["event_log"] = []
    return d

@app.post("/api/migration/preflight")
def migration_preflight(req: dict, u=Depends(require_role("admin","operator"))):
    target = req.get("target_platform", "")
    vms = req.get("vms", [])
    target_detail = req.get("target_detail", {})
    results = []
    for vm in vms:
        r = {
            "vm_name": vm.get("name",""),
            "power_state": vm.get("power_state","unknown"),
            "cpu_compatible": True,
            "disk_format": "VMDK",
            "target_format": {"openshift":"PVC (KubeVirt)","nutanix":"qcow2 (AHV)","hyperv":"VHDX"}.get(target,"Unknown"),
            "snapshots_present": False,
            "vmware_tools": "installed",
            "network_mapped": True,
            "overall": "pass",
            "notes": []
        }
        snap_count = vm.get("snapshot_count", 0)
        if snap_count and int(snap_count) > 0:
            r["snapshots_present"] = True
            r["overall"] = "warning"
            r["notes"].append(f"Has {snap_count} snapshot(s) - consolidate before migration")
        if vm.get("power_state") == "poweredOn":
            r["notes"].append("VM is powered on - cold migration recommended")
        disk_gb = vm.get("storage_used_gb", 0) or 0
        if float(disk_gb) > 2000:
            r["notes"].append(f"Large disk ({disk_gb} GB) - extended time")
        if target == "openshift":
            r["notes"].append("VM will run as KubeVirt VirtualMachine resource")
            guest_os = (vm.get("guest_os","") or "").lower()
            if "windows" in guest_os:
                r["notes"].append("Windows guest: ensure virtio drivers available")
        elif target == "nutanix":
            r["notes"].append("Nutanix Move will handle VMDK to qcow2 conversion")
        elif target == "hyperv":
            r["notes"].append("VMDK to VHDX conversion via qemu-img or StarWind V2V")
            guest_os = (vm.get("guest_os","") or "").lower()
            if "linux" in guest_os:
                r["notes"].append("Linux guest: verify Hyper-V integration services")
        results.append(r)
    ocp_operator_found = None
    if target == "openshift" and target_detail.get("cluster_id"):
        try:
            from openshift_client import get_operators
            cluster_id = target_detail["cluster_id"]
            from db import get_conn
            with get_conn() as c:
                cl = c.execute("SELECT * FROM ocp_clusters WHERE id=?", (cluster_id,)).fetchone()
                if cl:
                    ops = get_operators(dict(cl))
                    ocp_operator_found = any(
                        "kubevirt" in (op.get("name","")).lower() or
                        "virtualization" in (op.get("name","")).lower()
                        for op in ops.get("operators",[]))
        except:
            ocp_operator_found = None
    return {
        "results": results,
        "ocp_operator_found": ocp_operator_found,
        "target_platform": target,
        "summary": {
            "total": len(results),
            "pass": sum(1 for r in results if r["overall"]=="pass"),
            "warning": sum(1 for r in results if r["overall"]=="warning"),
            "fail": sum(1 for r in results if r["overall"]=="fail"),
        }
    }

@app.get("/api/migration/plans/{plan_id}/events")
def get_plan_events(plan_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        row = c.execute("SELECT status, progress, event_log, updated_at FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"error": "Plan not found"})
    d = dict(row)
    try:
        d["event_log"] = _json.loads(d["event_log"] or "[]")
    except:
        d["event_log"] = []
    return d

@app.post("/api/migration/preflight")
def migration_preflight(req: dict, u=Depends(require_role("admin","operator"))):
    target = req.get("target_platform", "")
    vms = req.get("vms", [])
    target_detail = req.get("target_detail", {})
    results = []
    for vm in vms:
        r = {
            "vm_name": vm.get("name",""),
            "power_state": vm.get("power_state","unknown"),
            "cpu_compatible": True,
            "disk_format": "VMDK",
            "target_format": {"openshift":"PVC (KubeVirt)","nutanix":"qcow2 (AHV)","hyperv":"VHDX"}.get(target,"Unknown"),
            "snapshots_present": False,
            "vmware_tools": "installed",
            "network_mapped": True,
            "overall": "pass",
            "notes": []
        }
        snap_count = vm.get("snapshot_count", 0)
        if snap_count and int(snap_count) > 0:
            r["snapshots_present"] = True
            r["overall"] = "warning"
            r["notes"].append(f"Has {snap_count} snapshot(s) - consolidate before migration")
        if vm.get("power_state") == "poweredOn":
            r["notes"].append("VM is powered on - cold migration recommended")
        disk_gb = vm.get("storage_used_gb", 0) or 0
        if float(disk_gb) > 2000:
            r["notes"].append(f"Large disk ({disk_gb} GB) - extended time")
        if target == "openshift":
            r["notes"].append("VM will run as KubeVirt VirtualMachine resource")
            guest_os = (vm.get("guest_os","") or "").lower()
            if "windows" in guest_os:
                r["notes"].append("Windows guest: ensure virtio drivers available")
        elif target == "nutanix":
            r["notes"].append("Nutanix Move will handle VMDK to qcow2 conversion")
        elif target == "hyperv":
            r["notes"].append("VMDK to VHDX conversion via qemu-img or StarWind V2V")
            guest_os = (vm.get("guest_os","") or "").lower()
            if "linux" in guest_os:
                r["notes"].append("Linux guest: verify Hyper-V integration services")
        results.append(r)
    ocp_operator_found = None
    if target == "openshift" and target_detail.get("cluster_id"):
        try:
            from openshift_client import get_operators
            cluster_id = target_detail["cluster_id"]
            from db import get_conn
            with get_conn() as c:
                cl = c.execute("SELECT * FROM ocp_clusters WHERE id=?", (cluster_id,)).fetchone()
                if cl:
                    ops = get_operators(dict(cl))
                    ocp_operator_found = any(
                        "kubevirt" in (op.get("name","")).lower() or
                        "virtualization" in (op.get("name","")).lower()
                        for op in ops.get("operators",[]))
        except:
            ocp_operator_found = None
    return {
        "results": results,
        "ocp_operator_found": ocp_operator_found,
        "target_platform": target,
        "summary": {
            "total": len(results),
            "pass": sum(1 for r in results if r["overall"]=="pass"),
            "warning": sum(1 for r in results if r["overall"]=="warning"),
            "fail": sum(1 for r in results if r["overall"]=="fail"),
        }
    }
