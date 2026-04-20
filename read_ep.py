import sys
sys.stdout.reconfigure(encoding='utf-8')
c = open(r'c:\caas-dashboard\backend\main.py', encoding='utf-8', errors='replace').read()
idx = c.find('/api/storage/arrays/{arr_id}/topology')
print(c[idx:idx+700])
