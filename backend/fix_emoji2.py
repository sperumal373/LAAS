f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
c = open(f, 'rb').read()
# Find the "Magic Migrate" area
idx = c.find(b'Magic Migrate')
chunk = c[idx-20:idx+20]
print('Bytes around Magic Migrate:', chunk)
print('Hex:', chunk.hex())
# Find all non-ASCII sequences 
text = c.decode('utf-8')
import re
nonascii = re.findall(r'[^\x00-\x7f]{2,}', text)
unique = set(nonascii)
for u in sorted(unique)[:20]:
    print(repr(u), '->', u)