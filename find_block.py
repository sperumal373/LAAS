s = open('C:/caas-dashboard/frontend/src/App.jsx', encoding='utf-8').read()
lines = s.split('\n')

# Find the RVTools block start and end
rvt_start = next((i for i,l in enumerate(lines) if '{/* RVTools Reports tab */' in l), -1)
print(f"RVTools block starts at line {rvt_start+1}")

# Find the RVTools block end (the )}\n after the big closing div)
# Look for the closing '      )}' that ends the vmTab==="rvtools"&&( block
rvt_end = -1
depth = 0
for i in range(rvt_start, min(rvt_start + 600, len(lines))):
    l = lines[i].strip()
    if l == '{vmTab==="rvtools"&&(':
        depth = 1
    elif depth > 0:
        depth += l.count('(') - l.count(')')
        if depth <= 0:
            rvt_end = i
            break

print(f"RVTools block ends at line {rvt_end+1}")
print()

# Show 10 lines BEFORE the block start
print("=== 10 lines before rvtools block ===")
for i in range(max(0, rvt_start-10), rvt_start):
    print(i+1, '|', repr(lines[i]))

print()
print("=== 10 lines after rvtools block ===")
for i in range(rvt_end+1, min(rvt_end+11, len(lines))):
    print(i+1, '|', repr(lines[i]))
