import sys, re
sys.stdout.reconfigure(encoding='utf-8')
c = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8', errors='replace').read()

# Search globally for vendor strings used in StorageArrayCard
# Look for vendor comparisons like arr.vendor==="..."
vendors_cmp = re.findall(r'arr\.vendor===["\']([\w\s\-]+)["\']', c)
vendors_cmp += re.findall(r'vendor===["\']([\w\s\-]+)["\']', c)
vendors_cmp += re.findall(r'"vendor":"([\w\s\-]+)"', c)
print("Vendor comparisons:", sorted(set(vendors_cmp)))

# Find the sidebar vendor list in StoragePage (the pill/filter buttons)
idx = c.find('function StoragePage')
chunk = c[idx:idx+30000]
# find where arrays are listed with vendor filter pills
pill_idx = chunk.find('NetApp')
if pill_idx != -1:
    print("\nNetApp context:")
    print(repr(chunk[max(0,pill_idx-200):pill_idx+400]))
