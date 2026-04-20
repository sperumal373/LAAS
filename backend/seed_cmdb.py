import sys, os
sys.path.insert(0, r'C:\caas-dashboard\backend')
os.chdir(r'C:\caas-dashboard\backend')
from dotenv import load_dotenv
load_dotenv(r'C:\caas-dashboard\backend\.env')

import cmdb_client

print('Starting CMDB collection...')
result = cmdb_client.collect_all_cis()

print()
print('=== CMDB Collection Results ===')
total = result.get("total", 0)
inserted = result.get("inserted", 0)
updated = result.get("updated", 0)
print(f'Total CIs: {total} ({inserted} new, {updated} updated)')
print()
print('By platform:')
for plat, cnt in result.get("by_platform", {}).items():
    print(f'  {plat:22s}: {cnt} CIs')

print()
s = cmdb_client.get_ci_summary()
print('=== Summary in DB ===')
for k, v in s.items():
    if v not in (None, '') and v != 0:
        print(f'  {k:25s}: {v}')
