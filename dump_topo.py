import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'

c = open(r'c:\caas-dashboard\backend\storage_client.py', encoding='utf-8', errors='replace').read()
idx = c.find('def get_volume_topology')
chunk = c[idx:idx+4000]
# Write to a temp file to avoid encoding issues
open(r'c:\caas-dashboard\topo_func_dump.txt', 'w', encoding='utf-8').write(chunk)
print("Written to topo_func_dump.txt")
print("First 200 chars:", chunk[:200])
