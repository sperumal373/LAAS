lines = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8', errors='replace').readlines()
start = -1
for i,l in enumerate(lines):
    if 'function VolumeTopologyModal' in l:
        start = i
        break

end = -1
for i in range(start+50, start+400):
    if lines[i].rstrip() == '}':
        end = i
        break

print(f'Modal: lines {start+1} to {end+1} ({end-start} lines)')
modal_text = ''.join(lines[start:end+1])
opens  = modal_text.count('<div')
closes = modal_text.count('</div>')
print(f'div opens={opens}, div closes={closes}')
print('Last 5 lines of modal:')
for l in lines[end-4:end+2]:
    print(repr(l[:80]))
