f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

# Fix: replace template literal with string concat in the filter IIFE
old = '{dnsQ?`No records match "${dnsQ}"`:"No records"}'
new = '{dnsQ?("No records match \u201c"+dnsQ+"\u201d"):"No records"}'

if old in content:
    content = content.replace(old, new, 1)
    print('Fix applied!')
else:
    print('String not found, checking...')
    idx = content.find('No records match')
    print(repr(content[max(0,idx-20):idx+80]))

with open(f, 'w', encoding='utf-8') as fh:
    fh.write(content)
print('Saved.')
