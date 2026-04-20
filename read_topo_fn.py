import sys
sys.stdout.reconfigure(encoding='utf-8')
c = open(r'c:\caas-dashboard\backend\storage_client.py', encoding='utf-8', errors='replace').read()
idx = c.find('def get_volume_topology')
chunk = c[idx:idx+1500]
lines = chunk.splitlines()
for i, l in enumerate(lines):
    print(i+1, repr(l[:100]))
    if i > 80: break
