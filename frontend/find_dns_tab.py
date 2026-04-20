f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

tab_dns = 'tab==="dns"'
idx = content.find(tab_dns)
print('tab===dns found at:', idx)
print(repr(content[idx:idx+200]))
