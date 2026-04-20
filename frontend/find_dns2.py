f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

# Find the DNS tab render block - look for the tab render return/JSX
dns_section = 'tab==="dns"'
dns_jsx_marker = '{tab==="dns"'  # how it appears in JSX

positions = []
start = 0
while True:
    idx = content.find(dns_section, start)
    if idx < 0:
        break
    positions.append(idx)
    start = idx + 1

print(f'Found {len(positions)} occurrences of tab===dns')
for pos in positions:
    print(f'  pos {pos}: {repr(content[pos:pos+80])}')
