"""Find section markers in the architecture doc."""
import re
with open(r'C:\caas-dashboard\architecture-doc.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find section IDs
for m in re.finditer(r'id="(sec\d+)"', content):
    # Get nearby text
    start = m.start()
    snippet = content[start:start+200]
    clean = re.sub(r'<[^>]+>', '', snippet).strip()[:80]
    print(f"  {m.group(1)}: {clean}")

# Find version references
for m in re.finditer(r'v\d\.\d', content):
    ctx = content[max(0,m.start()-20):m.end()+20]
    ctx = re.sub(r'<[^>]+>', '', ctx).strip()
    print(f"  Version ref: {ctx[:60]}")
