f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()
text = raw.decode('utf-8')

# The problem: emojis were UTF-8 bytes, then interpreted as CP1252, then re-encoded as UTF-8
# So we need: decode UTF-8 -> encode CP1252 -> decode UTF-8
import re

def fix_chunk(m):
    s = m.group(0)
    try:
        fixed = s.encode('cp1252').decode('utf-8')
        return fixed
    except:
        return s

# Match runs of non-ASCII chars (the mojibake)
pattern = re.compile(r'[\x80-\xff][\x80-\xff]+')
fixed = pattern.sub(fix_chunk, text)

diffs = [(i, a, b) for i, (a, b) in enumerate(zip(text, fixed)) if a != b]
print(f'Fixed {len(diffs)} character positions')
if diffs:
    for pos, old, new in diffs[:5]:
        print(f'  pos {pos}: {repr(old)} -> {repr(new)}')

open(f, 'w', encoding='utf-8').write(fixed)
print('Saved!')