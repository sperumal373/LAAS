data = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8').read()

# Find IPAM nav entry in the VMware page nav (the first nav array)
idx = data.find('id:"ipam"')
print(f'ipam nav entry at char {idx}')
print('--- context ---')
print(repr(data[idx-100:idx+300]))

# Find IPAM in the sidebar nav (the second occurrence with roles)
idx2 = data.find('id:"ipam"', idx+1)
print(f'\nsecond ipam entry at char {idx2}')
print('--- context ---')
print(repr(data[idx2-100:idx2+300]))

# Find where page routing for ipam is
import re
m = re.search(r'page==="ipam"[^}]{0,300}', data)
if m:
    print(f'\nipam page routing at {m.start()}:')
    print(repr(data[m.start()-20:m.start()+300]))
