import re

p = r"C:\caas-dashboard\backend\main.py"
t = open(p, "r", encoding="utf-8").read()

# Find the else block that handles Hyper-V simulation and replace it
old_block = '''    else:
        # Hyper-V / other targets: realistic phased simulation
        def _run_sim():
            from db import get_conn as _gc
            from nutanix_move_client import _run_realistic_simulation
            import json as _json
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status='executing', progress=0, started_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
                row = c.execute("SELECT vm_list, options FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
            vms = _json.loads((dict(row) if row else {}).get("vm_list") or "[]")
            options = _json.loads((dict(row) if row else {}).get("options") or "{}")
            def _db_upd(pid, status, progress):
                with _gc() as c:
                    if status == "completed":
                        c.execute("UPDATE migration_plans SET status=?, progress=?, completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (status, progress, pid))
                    else:
                        c.execute("UPDATE migration_plans SET status=?, progress=?, updated_at=datetime('now') WHERE id=?", (status, progress, pid))
            _migration_log(plan_id, f"Hyper-V migration via StarWind V2V (simulated)", username)
            _run_realistic_simulation(plan_id, vms, options, _db_upd, _migration_log)
        threading.Thread(target=_run_sim, daemon=True).start()'''

new_block = '''    elif target == "hyperv":
        # Real VMware -> Hyper-V migration (VMDK export + convert + import)
        def _run_hyperv():
            from db import get_conn as _gc
            from hyperv_migrate import orchestrate_hyperv_migration
            import json as _json
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status='executing', progress=0, started_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
                row = c.execute("SELECT plan_name, source_vcenter, target_detail, vm_list, options FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
            plan_data = dict(row) if row else {}
            def _db_upd(pid, status, progress):
                with _gc() as c:
                    if status == "completed":
                        c.execute("UPDATE migration_plans SET status=?, progress=?, completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (status, progress, pid))
                    else:
                        c.execute("UPDATE migration_plans SET status=?, progress=?, updated_at=datetime('now') WHERE id=?", (status, progress, pid))
            orchestrate_hyperv_migration(plan_id, plan_data, _db_upd, _migration_log)
        threading.Thread(target=_run_hyperv, daemon=True).start()
    else:
        # Other targets: realistic phased simulation
        def _run_sim():
            from db import get_conn as _gc
            from nutanix_move_client import _run_realistic_simulation
            import json as _json
            with _gc() as c:
                c.execute("UPDATE migration_plans SET status='executing', progress=0, started_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (plan_id,))
                row = c.execute("SELECT vm_list, options FROM migration_plans WHERE id=?", (plan_id,)).fetchone()
            vms = _json.loads((dict(row) if row else {}).get("vm_list") or "[]")
            options = _json.loads((dict(row) if row else {}).get("options") or "{}")
            def _db_upd(pid, status, progress):
                with _gc() as c:
                    if status == "completed":
                        c.execute("UPDATE migration_plans SET status=?, progress=?, completed_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (status, progress, pid))
                    else:
                        c.execute("UPDATE migration_plans SET status=?, progress=?, updated_at=datetime('now') WHERE id=?", (status, progress, pid))
            _migration_log(plan_id, f"Migration (simulated) for target={target}", username)
            _run_realistic_simulation(plan_id, vms, options, _db_upd, _migration_log)
        threading.Thread(target=_run_sim, daemon=True).start()'''

if old_block in t:
    t = t.replace(old_block, new_block)
    open(p, "w", encoding="utf-8").write(t)
    print("PATCHED OK")
else:
    # Try to find the block with flexible whitespace
    # Look for the marker text
    idx = t.find("Hyper-V / other targets: realistic phased simulation")
    if idx > 0:
        print(f"Found marker at position {idx}")
        # Show context
        start = max(0, idx-100)
        print("CONTEXT:", repr(t[start:idx+60]))
    else:
        print("Marker not found")
        idx2 = t.find("_run_realistic_simulation")
        if idx2 > 0:
            print(f"Found _run_realistic_simulation at {idx2}")
            print("CONTEXT:", repr(t[idx2-200:idx2+50]))
