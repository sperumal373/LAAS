import re

data = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8').read()

# Find page IDs from page==="xxx" && patterns
page_ids = list(re.finditer(r'page==="(\w+)"&&', data))
seen = set()
print('=== All page IDs (navigation) ===')
for m in page_ids:
    pid = m.group(1)
    if pid not in seen:
        seen.add(pid)
        print(f'  {pid}')

# Find nav items array
nav_block = re.search(r'navItems\s*=\s*\[(.{500,3000}?)\]', data, re.S)
if nav_block:
    print('\n=== navItems block ===')
    print(nav_block.group(0)[:2000])

# Find sidebar/nav labels
labels = re.findall(r'label\s*:\s*"([^"]+)"', data[:200000])
seen2 = set()
print('\n=== Navigation labels (first 200k chars) ===')
for l in labels:
    if l not in seen2 and len(l) < 30:
        seen2.add(l)
        print(f'  {l}')
