import sys
p = r"C:\caas-dashboard\backend\main.py"
data = open(p,"rb").read()
if b"ZERTO DISASTER RECOVERY" in data:
    print("main.py already patched")
    sys.exit(0)

routes = """

# === ZERTO DISASTER RECOVERY ROUTES ===
from zerto_client import (
    init_zerto_db, list_sites as z_list_sites, get_site as z_get_site,
    create_site as z_create_site, delete_site as z_delete_site,
    test_site_connection, get_dashboard as z_get_dashboard,
    list_vpgs as z_list_vpgs, get_vpg_detail as z_get_vpg_detail,
    list_vms as z_list_vms, list_alerts as z_list_alerts,
    dismiss_alert as z_dismiss_alert, list_tasks as z_list_tasks,
    list_events as z_list_events, get_reports as z_get_reports,
    failover_test, failover_test_stop, live_failover,
    commit_failover, rollback_failover, move_vpg, failback_vpg,
    get_audit_log as z_get_audit_log, list_checkpoints as z_list_checkpoints,
)
init_zerto_db()

@app.get("/api/zerto/sites")
def api_zerto_list_sites(token: str = Depends(verify_token)):
    return z_list_sites()

@app.get("/api/zerto/sites/{site_id}")
def api_zerto_get_site(site_id: int, token: str = Depends(verify_token)):
    return z_get_site(site_id)

@app.post("/api/zerto/sites")
def api_zerto_create_site(body: dict, token: str = Depends(verify_token)):
    return z_create_site(body)

@app.delete("/api/zerto/sites/{site_id}")
def api_zerto_delete_site(site_id: int, token: str = Depends(verify_token)):
    return z_delete_site(site_id)

@app.post("/api/zerto/sites/{site_id}/test")
def api_zerto_test_site(site_id: int, token: str = Depends(verify_token)):
    return test_site_connection(site_id)

@app.get("/api/zerto/sites/{site_id}/dashboard")
def api_zerto_dashboard(site_id: int, token: str = Depends(verify_token)):
    return z_get_dashboard(site_id)

@app.get("/api/zerto/sites/{site_id}/vpgs")
def api_zerto_vpgs(site_id: int, token: str = Depends(verify_token)):
    return z_list_vpgs(site_id)

@app.get("/api/zerto/sites/{site_id}/vms")
def api_zerto_vms(site_id: int, token: str = Depends(verify_token)):
    return z_list_vms(site_id)

@app.get("/api/zerto/sites/{site_id}/alerts")
def api_zerto_alerts(site_id: int, token: str = Depends(verify_token)):
    return z_list_alerts(site_id)

@app.post("/api/zerto/sites/{site_id}/alerts/{alert_id}/dismiss")
def api_zerto_dismiss(site_id: int, alert_id: str, token: str = Depends(verify_token)):
    return z_dismiss_alert(site_id, alert_id)

@app.get("/api/zerto/sites/{site_id}/tasks")
def api_zerto_tasks(site_id: int, token: str = Depends(verify_token)):
    return z_list_tasks(site_id)

@app.get("/api/zerto/sites/{site_id}/events")
def api_zerto_events(site_id: int, token: str = Depends(verify_token)):
    return z_list_events(site_id)

@app.get("/api/zerto/sites/{site_id}/reports")
def api_zerto_reports(site_id: int, token: str = Depends(verify_token)):
    return z_get_reports(site_id)

@app.get("/api/zerto/sites/{site_id}/audit")
def api_zerto_audit(site_id: int, token: str = Depends(verify_token)):
    return z_get_audit_log(site_id)

@app.get("/api/zerto/sites/{site_id}/vpgs/{vpg_id}/checkpoints")
def api_zerto_checkpoints(site_id: int, vpg_id: str, token: str = Depends(verify_token)):
    return z_list_checkpoints(site_id, vpg_id)

@app.post("/api/zerto/sites/{site_id}/vpgs/{vpg_id}/test-failover")
def api_zerto_tf(site_id: int, vpg_id: str, body: dict = {}, token: str = Depends(verify_token)):
    return failover_test(site_id, vpg_id, body.get("vpg_name",""), body.get("checkpoint_id"))

@app.post("/api/zerto/sites/{site_id}/vpgs/{vpg_id}/stop-test")
def api_zerto_st(site_id: int, vpg_id: str, body: dict = {}, token: str = Depends(verify_token)):
    return failover_test_stop(site_id, vpg_id, body.get("vpg_name",""), body.get("success",True), body.get("notes",""))

@app.post("/api/zerto/sites/{site_id}/vpgs/{vpg_id}/live-failover")
def api_zerto_lf(site_id: int, vpg_id: str, body: dict = {}, token: str = Depends(verify_token)):
    return live_failover(site_id, vpg_id, body.get("vpg_name",""), body)

@app.post("/api/zerto/sites/{site_id}/vpgs/{vpg_id}/commit-failover")
def api_zerto_cf(site_id: int, vpg_id: str, body: dict = {}, token: str = Depends(verify_token)):
    return commit_failover(site_id, vpg_id, body.get("vpg_name",""), body.get("reverse_protection",False))

@app.post("/api/zerto/sites/{site_id}/vpgs/{vpg_id}/rollback-failover")
def api_zerto_rf(site_id: int, vpg_id: str, body: dict = {}, token: str = Depends(verify_token)):
    return rollback_failover(site_id, vpg_id, body.get("vpg_name",""))

@app.post("/api/zerto/sites/{site_id}/vpgs/{vpg_id}/move")
def api_zerto_mv(site_id: int, vpg_id: str, body: dict = {}, token: str = Depends(verify_token)):
    return move_vpg(site_id, vpg_id, body.get("vpg_name",""), body)

@app.post("/api/zerto/sites/{site_id}/vpgs/{vpg_id}/failback")
def api_zerto_fb(site_id: int, vpg_id: str, body: dict = {}, token: str = Depends(verify_token)):
    return failback_vpg(site_id, vpg_id, body.get("vpg_name",""), body)
"""

routes_bytes = routes.encode("utf-8")
marker = b'if __name__ == "__main__"'
if marker in data:
    idx = data.rfind(marker)
    data = data[:idx] + routes_bytes + b"\n" + data[idx:]
else:
    data = data + routes_bytes

open(p,"wb").write(data)
print("main.py patched OK, size:", len(data))
