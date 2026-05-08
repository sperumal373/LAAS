with open("C:/caas-dashboard/backend/cis_scanner.py","rb") as f: t=f.read().decode("utf-8")

# Patch scan_assets_cis signature
old_sig = 'def scan_assets_cis(asset_ids: list | None = None, triggered_by: str = "manual") -> dict:'
new_sig = 'def scan_assets_cis(asset_ids: list | None = None, triggered_by: str = "manual", os_filter: str | None = None) -> dict:'

# Also patch the job insert to include os_filter
old_insert = 'INSERT INTO cis_scan_jobs (triggered_by, status, target_vms)\n                VALUES (%s, \'queued\', %s) RETURNING id\n            """, (triggered_by, len(assets)))'
new_insert = 'INSERT INTO cis_scan_jobs (triggered_by, status, target_vms, os_filter)\n                VALUES (%s, \'queued\', %s, %s) RETURNING id\n            """, (triggered_by, len(assets), os_filter))'

if old_sig in t:
    t = t.replace(old_sig, new_sig, 1)
    print("Patched signature")
else:
    print("WARNING: signature not found, looking for it...")
    idx = t.find("def scan_assets_cis")
    print(repr(t[idx:idx+150]))

if old_insert in t:
    t = t.replace(old_insert, new_insert, 1)
    print("Patched job insert")
else:
    print("WARNING: job insert not found")

with open("C:/caas-dashboard/backend/cis_scanner.py","wb") as f: f.write(t.encode("utf-8"))
print("Done")
