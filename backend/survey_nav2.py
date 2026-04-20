import re

data = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8').read()

# Find nav items with id and label
nav_pattern = re.findall(r'\{[^{}]*?id\s*:\s*["\'](\w[\w-]*)["\'][^{}]*?label\s*:\s*["\']([^"\']+)["\']', data[:300000])
print('=== Nav items (id, label) found in first 300k ===')
seen = set()
for item in nav_pattern:
    key = item[0]
    if key not in seen and len(item[0]) < 20:
        seen.add(key)
        print(f'  id={item[0]:20s} label={item[1]}')

# Also find all page==="xxx" patterns
print('\n=== All page IDs in rendering ===')
pages = re.findall(r'page==="(\w+)"', data)
seen2 = set()
for p in pages:
    if p not in seen2:
        seen2.add(p)
        print(f'  {p}')

# Find the nav list structure
print('\n=== Looking for sidebar/nav definition ===')
# Common pattern: const NAV = [...] or const navItems = [...]
nav_defs = re.findall(r'(?:NAV|navItems|NAVS|sideNav|menuItems|pages)\s*=\s*\[', data)
for nd in nav_defs:
    idx = data.find(nd)
    print(f'  Found: {nd!r} at pos {idx}')
    print(f'  Context: {data[idx:idx+300]}')
    print()
