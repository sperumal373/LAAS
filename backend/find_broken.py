f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
text = open(f, encoding='utf-8').read()

import re
# Find all unique non-ASCII sequences
hits = re.findall(r'(?:[\x80-\xff][\x80-\xff\ufe0f]*)', text)
from collections import Counter
for seq, cnt in Counter(hits).most_common(30):
    print(f'  {cnt:3d}x  {repr(seq):30s}  displays as: {seq}')