s = open('C:/caas-dashboard/frontend/src/App.jsx', encoding='utf-8').read()
lines = s.split('\n')

# Show rvtools tab entry
idx = next((i for i,l in enumerate(lines) if 'id:"rvtools"' in l), -1)
print("=== rvtools tab entry (line", idx+1, ") ===")
for i in range(idx-2, idx+6):
    print(i+1, '|', repr(lines[i]))

# Show useEffect
idx2 = next((i for i,l in enumerate(lines) if 'vmTab==="rvtools"&&rvtReports' in l), -1)
print("\n=== useEffect (line", idx2+1, ") ===")
for i in range(idx2-2, idx2+4):
    print(i+1, '|', repr(lines[i]))

# Show loadRVToolsReports function
idx3 = next((i for i,l in enumerate(lines) if 'async function loadRVToolsReports' in l), -1)
print("\n=== loadRVToolsReports (line", idx3+1, ") ===")
for i in range(idx3-1, idx3+6):
    print(i+1, '|', repr(lines[i]))

# Show the rvtReports state line
idx4 = next((i for i,l in enumerate(lines) if 'rvtReports, setRvtReports' in l), -1)
print("\n=== rvtReports state (line", idx4+1, ") ===")
for i in range(idx4-1, idx4+3):
    print(i+1, '|', repr(lines[i]))
