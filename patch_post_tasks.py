"""
Patch: Add Post-Migration Tasks feature to Move Groups
- DB table for task history
- API endpoints: list AAP templates, execute task, get status/history
- Supports: AAP playbooks + custom scripts
"""
import re

MAIN_PATH = r"C:\caas-dashboard\backend\main.py"

with open(MAIN_PATH, "r", encoding="utf-8") as f:
    content = f.read()

#  1. Add DB table for post-migration tasks 
db_table = '''
    c.execute("""CREATE TABLE IF NOT EXISTS post_migration_tasks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id    INTEGER NOT NULL,
        task_type   TEXT NOT NULL DEFAULT 'playbook',
        task_name   TEXT NOT NULL,
        template_id INTEGER,
        aap_inst_id INTEGER,
        custom_script TEXT DEFAULT '',
        extra_vars  TEXT DEFAULT '{}',
        status      TEXT DEFAULT 'pending',
        started_at  TEXT,
        finished_at TEXT,
        results     TEXT DEFAULT '{}',
        triggered_by TEXT DEFAULT '',
        created_at  TEXT DEFAULT (datetime('now'))
    )""")
'''

# Insert after move_group_vms table creation
marker = 'c.execute("""CREATE TABLE IF NOT EXISTS move_group_vms ('
if "post_migration_tasks" not in content:
    idx = content.index(marker)
    # Find the end of the CREATE TABLE block
    end_idx = content.index('""")', idx) + 4
    content = content[:end_idx] + "\n" + db_table + content[end_idx:]
    print("Added post_migration_tasks DB table")
else:
    print("post_migration_tasks table already exists")

#  2. Add API endpoints for post-migration tasks 
api_code = '''

#  Post-Migration Tasks for Move Groups 
@app.get("/api/migration/move-groups/{group_id}/post-tasks")
def list_post_tasks(group_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    c = get_conn()
    tasks = [dict(t) for t in c.execute(
        "SELECT * FROM post_migration_tasks WHERE group_id=? ORDER BY created_at DESC", (group_id,)
    ).fetchall()]
    return {"tasks": tasks}

@app.get("/api/migration/move-groups/{group_id}/post-tasks/playbooks")
def list_available_playbooks(group_id: int, u=Depends(require_role("admin","operator"))):
    """List all job templates from all connected AAP instances for post-migration use."""
    from ansible_client import list_aap_instances, get_aap_job_templates
    playbooks = []
    for inst in list_aap_instances():
        try:
            templates = get_aap_job_templates(inst)
            for t in templates:
                t["aap_instance_id"] = inst["id"]
                t["aap_instance_name"] = inst.get("name", "")
                playbooks.append(t)
        except Exception:
            pass
    return {"playbooks": playbooks}

@app.post("/api/migration/move-groups/{group_id}/post-tasks/run")
def run_post_task(group_id: int, req: dict, u=Depends(require_role("admin","operator"))):
    """
    Run a post-migration task on all VMs in the group.
    Body: { task_type: "playbook"|"custom", template_id, aap_inst_id, task_name, custom_script, extra_vars }
    """
    import threading
    from db import get_conn
    from ansible_client import (
        get_aap_instance, launch_job_template, get_job_output,
        create_inventory as aap_create_inv, get_aap_job_templates
    )
    c = get_conn()

    # Get group VMs
    vms = [dict(v) for v in c.execute(
        "SELECT * FROM move_group_vms WHERE group_id=?", (group_id,)
    ).fetchall()]
    if not vms:
        raise HTTPException(400, "No VMs in this group")

    task_type = req.get("task_type", "playbook")
    task_name = req.get("task_name", "Unnamed Task")
    template_id = req.get("template_id")
    aap_inst_id = req.get("aap_inst_id")
    custom_script = req.get("custom_script", "")
    extra_vars = req.get("extra_vars", "{}")

    # Create task record
    c.execute(
        """INSERT INTO post_migration_tasks
           (group_id, task_type, task_name, template_id, aap_inst_id, custom_script, extra_vars, status, started_at, triggered_by)
           VALUES (?,?,?,?,?,?,?,?,datetime('now'),?)""",
        (group_id, task_type, task_name, template_id, aap_inst_id, custom_script, extra_vars, "running", u.get("username",""))
    )
    task_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.connection.commit()

    def _execute_task():
        from db import get_conn as _gc
        cc = _gc()
        results = {"vms": [], "aap_job_id": None, "output": ""}
        try:
            if task_type == "playbook" and template_id and aap_inst_id:
                inst = get_aap_instance(aap_inst_id)
                if not inst:
                    raise Exception("AAP instance not found")

                # Build extra_vars with VM inventory info
                vm_list = [{"name": v["vm_name"], "ip": v.get("ip_address",""), "os": v.get("guest_os","")} for v in vms]
                ev = extra_vars if isinstance(extra_vars, str) else json.dumps(extra_vars)
                try:
                    ev_dict = json.loads(ev) if ev else {}
                except Exception:
                    ev_dict = {}
                ev_dict["target_vms"] = vm_list
                ev_dict["vm_ips"] = [v.get("ip_address","") for v in vms if v.get("ip_address")]
                ev_dict["vm_names"] = [v["vm_name"] for v in vms]
                ev_str = json.dumps(ev_dict)

                # Launch the job template
                launch_result = launch_job_template(inst, template_id, ev_str)
                job_id = launch_result.get("id") or launch_result.get("job")
                results["aap_job_id"] = job_id

                # Poll for completion (max 10 min)
                import time as _time
                for _ in range(120):
                    _time.sleep(5)
                    try:
                        from ansible_client import _get
                        job_data = _get(inst, f"/api/v2/jobs/{job_id}/")
                        status = job_data.get("status", "")
                        if status in ("successful", "failed", "error", "canceled"):
                            results["status"] = status
                            results["output"] = get_job_output(inst, job_id)
                            break
                    except Exception:
                        pass
                else:
                    results["status"] = "timeout"

                for v in vms:
                    results["vms"].append({"name": v["vm_name"], "status": results.get("status","unknown")})

            elif task_type == "custom" and custom_script:
                # Execute custom script via SSH/WinRM on each VM
                import subprocess, concurrent.futures
                def _run_on_vm(vm):
                    ip = vm.get("ip_address", "")
                    if not ip:
                        return {"name": vm["vm_name"], "status": "skipped", "output": "No IP address"}
                    os_type = (vm.get("guest_os","") or "").lower()
                    try:
                        if "windows" in os_type:
                            cmd = ["powershell", "-Command",
                                   f"Invoke-Command -ComputerName {ip} -ScriptBlock {{ {custom_script} }} -ErrorAction Stop"]
                        else:
                            cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
                                   f"root@{ip}", custom_script]
                        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                        return {"name": vm["vm_name"], "status": "success" if r.returncode == 0 else "failed",
                                "output": (r.stdout + r.stderr)[:2000]}
                    except Exception as e:
                        return {"name": vm["vm_name"], "status": "failed", "output": str(e)[:500]}

                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                    vm_results = list(ex.map(_run_on_vm, vms))
                results["vms"] = vm_results
                results["status"] = "successful" if all(r["status"]=="success" for r in vm_results) else "partial"

            # Update task record
            final_status = results.get("status", "failed")
            cc.execute(
                "UPDATE post_migration_tasks SET status=?, finished_at=datetime('now'), results=? WHERE id=?",
                (final_status, json.dumps(results), task_id)
            )
            cc.connection.commit()
        except Exception as e:
            cc.execute(
                "UPDATE post_migration_tasks SET status='failed', finished_at=datetime('now'), results=? WHERE id=?",
                (json.dumps({"error": str(e)}), task_id)
            )
            cc.connection.commit()

    threading.Thread(target=_execute_task, daemon=True).start()
    audit(u["username"], "POST_MIGRATION_TASK", target=f"group:{group_id}", detail=f"task={task_name} type={task_type}", role=u.get("role",""))
    return {"task_id": task_id, "status": "running", "message": f"Task '{task_name}' started on {len(vms)} VMs"}

@app.get("/api/migration/move-groups/post-tasks/{task_id}")
def get_post_task_status(task_id: int, u=Depends(require_role("admin","operator","viewer"))):
    from db import get_conn
    c = get_conn()
    task = c.execute("SELECT * FROM post_migration_tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        raise HTTPException(404, "Task not found")
    t = dict(task)
    try:
        t["results"] = json.loads(t.get("results","{}"))
    except Exception:
        pass
    return t

@app.delete("/api/migration/move-groups/post-tasks/{task_id}")
def delete_post_task(task_id: int, u=Depends(require_role("admin"))):
    from db import get_conn
    c = get_conn()
    c.execute("DELETE FROM post_migration_tasks WHERE id=?", (task_id,))
    c.connection.commit()
    return {"status": "ok"}
'''

# Insert after the migrate_move_group endpoint
if "/api/migration/move-groups/{group_id}/post-tasks" not in content:
    # Find the end of migrate_move_group function
    marker2 = "#  Post-Migration Tasks"
    if marker2 not in content:
        # Find the last move-group related endpoint
        last_mg = content.rfind("def migrate_move_group")
        # Find the next @app or def after it
        next_func = content.find("\n@app.", last_mg + 100)
        if next_func == -1:
            next_func = len(content)
        content = content[:next_func] + api_code + content[next_func:]
        print("Added post-migration task API endpoints")
else:
    print("Post-migration task endpoints already exist")

with open(MAIN_PATH, "w", encoding="utf-8") as f:
    f.write(content)
print("Backend updated!")