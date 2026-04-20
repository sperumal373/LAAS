import sys
be = open(r'C:\caas-dashboard\backend\main.py', 'r', encoding='utf-8').read()
marker = '#  Magic Migrate'
idx = be.find(marker)
if idx == -1:
    print('ERROR: marker not found'); sys.exit(1)
nl = be.rfind('\n', 0, idx)
nl2 = be.rfind('\n', 0, nl)
cut = nl2 + 1
before = be[:cut]
new_section = open(r'C:\caas-dashboard\migration_backend_new.py', 'r', encoding='utf-8').read()
with open(r'C:\caas-dashboard\backend\main.py', 'w', encoding='utf-8') as f:
    f.write(before + new_section + '\n')
print(f'Backend: kept {cut} bytes + new section {len(new_section)} bytes')
