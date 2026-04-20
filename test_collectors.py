import sys, os
sys.path.insert(0, r'C:\caas-dashboard\backend')
os.chdir(r'C:\caas-dashboard\backend')

from cmdb_client import _collect_storage, _collect_physical
from collections import Counter

# Test storage
storage_cis = _collect_storage()
print(f"Storage CIs: {len(storage_cis)}")
for ci in storage_cis:
    print(f"  {ci['name']} | {ci['correlation_id']} | {ci['ip_address']}")

# Test physical
phys_cis = _collect_physical()
print(f"\nPhysical CIs: {len(phys_cis)}")
corr_counts = Counter(c['correlation_id'] for c in phys_cis)
dupes = {k: v for k, v in corr_counts.items() if v > 1}
print(f"Duplicate correlation_ids: {len(dupes)}")
print(f"Unique correlation_ids: {len(corr_counts)}")
if dupes:
    print("Remaining dupes:")
    for k, v in list(dupes.items())[:10]:
        print(f"  {k} x{v}")
