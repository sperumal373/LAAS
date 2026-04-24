f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
c = open(f, 'rb').read()

# The file was double-encoded: UTF-8 emojis were interpreted as latin1 then saved as UTF-8
# Try to fix by finding mojibake patterns
# Approach: decode as utf-8, then try to fix mojibake by encoding as latin1 and decoding as utf-8
text = c.decode('utf-8')

# Find all mojibake sequences (characters in range 0x80-0xFF followed by similar)
import re

def fix_mojibake(m):
    s = m.group(0)
    try:
        return s.encode('latin-1').decode('utf-8')
    except:
        return s

# Match sequences of chars in 0xC0-0xFF range followed by 0x80-0xBF
pattern = re.compile(r'[\xc0-\xf4][\x80-\xbf]{1,3}')
fixed = pattern.sub(fix_mojibake, text)

changes = sum(1 for a, b in zip(text, fixed) if a != b)
print(f'Fixed {changes} characters')
open(f, 'w', encoding='utf-8').write(fixed)
print('Saved!')