p = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
t = open(p, "r", encoding="utf-8").read()
t = t.replace("await fetchHVHosts();", "await fetchHVStatus();", 1)
old_filter = '.filter(h => h.status === "connected" || h.status === "ok")'
new_filter = '.filter(h => h.success === true)'
t = t.replace(old_filter, new_filter, 1)
open(p, "w", encoding="utf-8").write(t)
print("PATCHED")
for i, line in enumerate(open(p, encoding="utf-8"), 1):
    if "fetchHVStatus" in line or "h.success" in line:
        print(f"  L{i}: {line.rstrip()}")
