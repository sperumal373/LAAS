import sys
sys.stdout.reconfigure(encoding='utf-8')
c = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8', errors='replace').read()

# Find the exact strings using repr to identify the corrupt chars
idx = c.find('function VolumeTopologyModal')
chunk = c[idx:idx+16000]
lines = chunk.splitlines()
line157 = lines[156]
line166 = lines[165]
print('L157:', repr(line157))
print('L166:', repr(line166))

# Replace by finding exact substrings in the full file
# Line 157 fix - replace 'Replicates to ??' and '?? Replicated from'
old1 = line157.strip()
new1 = old1
# replace all non-ascii chars on that line with proper arrows
import re
# find '?' or corrupted char patterns between quotes
new1 = re.sub(r"'Replicates to [^']*'", "'Replicates to >>'", new1)
new1 = re.sub(r"'[^']*Replicated from'", "'<< Replicated from'", new1)
print('L157 fixed:', repr(new1))

# Line 166 fix
old2 = line166.strip()
new2 = re.sub(r"isOut\?'[^']*':'[^']*'", "isOut?'>>':'<<'", old2)
print('L166 fixed:', repr(new2))

# Apply replacements - need to strip indentation for matching
indent157 = len(line157) - len(line157.lstrip())
indent166 = len(line166) - len(line166.lstrip())
indented_new1 = ' ' * indent157 + new1
indented_new2 = ' ' * indent166 + new2

c2 = c.replace(line157, indented_new1)
c2 = c2.replace(line166, indented_new2)

if c2 != c:
    with open(r'c:\caas-dashboard\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
        f.write(c2)
    print('OK: fixed')
else:
    print('WARN: no change')
