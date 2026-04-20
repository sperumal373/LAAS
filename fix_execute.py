"""Replace fake execute endpoints with real MTV integration."""
import os

M = r"C:\caas-dashboard\backend\main.py"
data = open(M, "r", encoding="utf-8").read()

# Find boundaries
# Both duplicate execute endpoints span from byte 323343 to 331258
idx1 = data.find('@app.post("/api/migration/plans/{plan_id}/execute")')
idx_events = data.find('@app.get("/api/migration/plans/{plan_id}/events")')
idx_events_start = data.rfind('\n', 0, idx_events)

old_section = data[idx1:idx_events_start+1]
print(f"Removing {len(old_section)} bytes of fake execute code (byte {idx1} to {idx_events_start})")

DT = "date" + "time"

new_execute = f'''@app.post("/api/migration/plans/{{plan_id}}/execute")
def execute_migration(plan_id: int, u=Depends(require_role("admin","operator"))):
    from db import get_conn
    import json as _json
    import threading
    username = u.get("username", "?")
    with get_conn() as c:
        row = c.execute("SELECT * FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
        if not row:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=404, content={{"error": "Plan not found"}})
        plan = dict(row)
        if plan["status"] not in ("approved",):
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=400, content={{"error": "Plan must be approved to execute"}})
    target = plan.get("target_platform", "")

    def _run_mtv():
        """Background thread: orchestrate real MTV migration + poll status."""
        from db import get_conn as _gc
        import time as _time
        with _gc() as c:
            c.execute("UPDATE migration_plans SET status=\'executing\', progress=0, started_at={DT}(\'now\'), updated_at={DT}(\'now\') WHERE id=?", (plan_id,))
        _migration_log(plan_id, f"Migration execution started by {{username}}", username)
        try:
            from mtv_client import orchestrate_migration, poll_mtv_status
            mtv_plan_name = orchestrate_migration(plan, log_fn=_migration_log)
            # Now poll MTV until done
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status=\'migrating\', progress=10, updated_at={DT}(\'now\') WHERE id=?", (plan_id,))
            _migration_log(plan_id, "MTV migration in progress. Polling real status from OpenShift...", "system")
            while True:
                _time.sleep(15)
                try:
                    st = poll_mtv_status(plan)
                except Exception as pe:
                    _migration_log(plan_id, f"Poll error: {{pe}}", "system")
                    _time.sleep(15)
                    continue
                phase = st.get("phase", "unknown")
                progress = st.get("progress", 0)
                # Log VM-level progress
                for vm in st.get("vms", []):
                    vn = vm.get("name", "?")
                    vphase = vm.get("phase", "Pending")
                    for step in vm.get("pipeline", []):
                        if step.get("name") == "DiskTransfer" and step.get("total", 0) > 0:
                            pct = int(step["completed"] / step["total"] * 100) if step["total"] else 0
                            _migration_log(plan_id, f"[{{vn}}] Disk transfer: {{step[\'completed\']}} / {{step[\'total\']}} MB ({{pct}}%) - {{step[\'phase\']}}", "system")
                with _gc() as c:
                    c.execute("UPDATE migration_plans SET progress=?, updated_at={DT}(\'now\') WHERE id=?", (min(progress, 99), plan_id))
                if phase == "completed":
                    with _gc() as c:
                        c.execute("UPDATE migration_plans SET status=\'completed\', progress=100, completed_at={DT}(\'now\'), updated_at={DT}(\'now\') WHERE id=?", (plan_id,))
                    # Log final VM results
                    for vm in st.get("vms", []):
                        _migration_log(plan_id, f"[OK] \'{{vm[\'name\']}}\' migration {{vm.get(\'phase\',\'?\')}}", "system")
                    total_mb = st.get("total_disk_mb", 0)
                    _migration_log(plan_id, f"Migration completed! Total disk transferred: {{total_mb}} MB. Started: {{st.get(\'started\',\'?\')}}, Completed: {{st.get(\'completed\',\'?\')}}", "system")
                    break
                elif phase == "failed":
                    with _gc() as c:
                        c.execute("UPDATE migration_plans SET status=\'failed\', updated_at={DT}(\'now\') WHERE id=?", (plan_id,))
                    errs = [c.get("message","") for c in st.get("conditions",[]) if c.get("type") in ("Failed",)]
                    _migration_log(plan_id, f"Migration FAILED: {{'; '.join(errs)}}", "system")
                    break
        except Exception as ex:
            import traceback
            _migration_log(plan_id, f"MTV orchestration error: {{ex}}", "system")
            _migration_log(plan_id, traceback.format_exc()[:500], "system")
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status=\'failed\', updated_at={DT}(\'now\') WHERE id=?", (plan_id,))

    if target == "openshift":
        threading.Thread(target=_run_mtv, daemon=True).start()
    else:
        # For non-openshift targets, keep simple simulation for now
        def _run_sim():
            from db import get_conn as _gc
            import time as _time, random
            tool_name = {{"nutanix": "Nutanix Move", "hyperv": "StarWind V2V"}}.get(target, "Migration Tool")
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status=\'executing\', progress=0, started_at={DT}(\'now\'), updated_at={DT}(\'now\') WHERE id=?", (plan_id,))
            _migration_log(plan_id, f"Simulated migration via {{tool_name}} (non-OCP target)", username)
            _time.sleep(5)
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status=\'completed\', progress=100, completed_at={DT}(\'now\'), updated_at={DT}(\'now\') WHERE id=?", (plan_id,))
            _migration_log(plan_id, "Simulation complete.", "system")
        threading.Thread(target=_run_sim, daemon=True).start()

    _migration_log(plan_id, f"Execution triggered by {{username}} (target={{target}})", username)
    return {{"ok": True, "message": f"Migration execution started (target={{target}})"}}

'''

# Also replace the events endpoint to include real MTV polling
idx_events_end = data.find('\n@app.', idx_events + 10)
old_events = data[idx_events:idx_events_end]
print(f"Events endpoint: {len(old_events)} bytes")

new_events = f'''@app.get("/api/migration/plans/{{plan_id}}/events")
def get_plan_events(plan_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    import json as _json
    with get_conn() as c:
        row = c.execute("SELECT status, progress, event_log, updated_at, target_platform, target_detail, plan_name FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={{"error": "Plan not found"}})
    d = dict(row)
    try:
        d["event_log"] = _json.loads(d["event_log"] or "[]")
    except:
        d["event_log"] = []
    # If migration is active and target is openshift, include live MTV status
    if d["status"] in ("executing", "migrating", "validating") and d.get("target_platform") == "openshift":
        try:
            from mtv_client import poll_mtv_status
            mtv = poll_mtv_status(d)
            d["mtv_status"] = mtv
            # Use MTV progress if available
            if mtv.get("progress", 0) > d.get("progress", 0):
                d["progress"] = mtv["progress"]
        except Exception as e:
            d["mtv_error"] = str(e)
    return d

'''

result = data[:idx1] + new_execute + new_events + data[idx_events_end:]
open(M, "w", encoding="utf-8").write(result)
print(f"Done. Old size: {len(data)}, New size: {len(result)}")