import re

data = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8').read()

# Find the IPAM nav entry
for pattern in ['id:"ipam"', "id:'ipam'", 'id: "ipam"', "id: 'ipam'"]:
    idx = data.find(pattern)
    if idx >= 0:
        print(f'Found {pattern!r} at pos {idx}')
        print('Context:')
        print(data[max(0, idx-300):idx+400])
        break

# Find assets nav entry (to see if it exists)
print('\n\n=== ASSETS page nav entry ===')
for pattern in ['id:"assets"', "id:'assets'", 'id: "assets"', "id: 'assets'"]:
    idx2 = data.find(pattern)
    if idx2 >= 0:
        print(f'Found {pattern!r} at pos {idx2}')
        print(data[max(0, idx2-200):idx2+300])
        break

# Find page routing for assets and ipam
print('\n\n=== page routing for ipam/assets ===')
for pg in ['ipam', 'assets']:
    m = re.search(rf'page==="{pg}"[^{{}}]{{0,200}}', data)
    if m:
        print(f'{pg}: {data[m.start():m.start()+200]}')
        print()
