s = open('C:/caas-dashboard/frontend/src/App.jsx', encoding='utf-8').read()
lines = s.split('\n')

# Find render block start
idx = next((i for i,l in enumerate(lines) if 'RVTools Reports tab' in l), -1)
print("=== RVTools render block area (lines", idx+1, "to", idx+30, ") ===")
for i in range(idx-3, idx+30):
    print(i+1, '|', repr(lines[i]))
