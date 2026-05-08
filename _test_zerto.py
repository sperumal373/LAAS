import sys
sys.path.insert(0, r"C:\caas-dashboard\backend")
from zerto_client import init_zerto_db, list_sites, test_site_connection, get_dashboard

init_zerto_db()
sites = list_sites()
print("=== Sites in DB ===")
for s in sites:
    print("  [%d] %s  host=%s  type=%s  status=%s" % (s["id"], s["name"], s["host"], s["site_type"], s["status"]))

print()
print("=== Connection Tests ===")
for s in sites:
    r = test_site_connection(s["id"])
    if r.get("ok"):
        print("  OK  %s (%s) => site_name=%s  version=%s  base=%s" % (s["name"], s["host"], r.get("site_name",""), r.get("version",""), r.get("base","")))
    else:
        print("  FAIL %s (%s) => %s" % (s["name"], s["host"], r.get("error","")))
