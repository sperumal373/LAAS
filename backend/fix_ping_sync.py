"""Fix ping route to be synchronous and fix summary field names."""
import re

path = r"c:\caas-dashboard\backend\main.py"
content = open(path, "r", encoding="utf-8").read()

# Fix 1: ping route – make synchronous
# Find the ping route block
ping_start = content.find('@app.post("/api/ipam2/vlans/{vlan_db_id}/ping")')
if ping_start < 0:
    print("ERROR: ping route not found")
else:
    # Find end of the function (next @app. decorator)
    ping_end = content.find('\n@app.', ping_start + 10)
    old_ping = content[ping_start:ping_end]
    print("OLD PING ROUTE:")
    print(repr(old_ping[:300]))

    new_ping = '''@app.post("/api/ipam2/vlans/{vlan_db_id}/ping")
def ipam2_ping(vlan_db_id: int, u=Depends(require_role("admin", "operator"))):
    """Ping all IPs in a VLAN synchronously and return results."""
    try:
        results = _ipam_pg.ping_and_save(vlan_db_id)
        return {"status": "done", "vlan_db_id": vlan_db_id, "count": len(results)}
    except Exception as e:
        log.error(f"[ipam2] ping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))'''

    content = content[:ping_start] + new_ping + content[ping_end:]
    print("Ping route fixed")

# Fix 2: get_summary – add available_ips and offline_ips keys
old_summary_field = "SUM(CASE WHEN i.status='available' THEN 1 ELSE 0 END) AS free_ips,"
new_summary_field = "SUM(CASE WHEN i.status='available' THEN 1 ELSE 0 END) AS free_ips,\n            SUM(CASE WHEN i.status='available' THEN 1 ELSE 0 END) AS available_ips,"
if old_summary_field in content and "available_ips" not in content:
    content = content.replace(old_summary_field, new_summary_field)
    print("Summary available_ips added")

old_offline = "SUM(CASE WHEN i.ping_status='up'   THEN 1 ELSE 0 END) AS up_ips,"
new_offline = "SUM(CASE WHEN i.status='offline'   THEN 1 ELSE 0 END) AS offline_ips,\n            SUM(CASE WHEN i.ping_status='up'   THEN 1 ELSE 0 END) AS up_ips,"
# Only in get_summary function  
if old_offline in content and "offline_ips" not in content:
    content = content.replace(old_offline, new_offline, 1)
    print("Summary offline_ips added")

open(path, "w", encoding="utf-8").write(content)
print("Done – main.py saved")
