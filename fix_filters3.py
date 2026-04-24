path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()
lines = raw.split(b'\r\n')

# Replace lines 248-259 (indices 247-259) with correct code
old_lines = b'\r\n'.join(lines[247:260])
new_block = b'\r\n'.join([
    b'  const filteredVMs = allVMs',
    b'    .filter(v => !selHost || v.host === selHost)',
    b'    .filter(v => !vmSearch || v.name?.toLowerCase().includes(vmSearch.toLowerCase()) || v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()) || v.ip?.toLowerCase().includes(vmSearch.toLowerCase()) || (Array.isArray(v.tags) && v.tags.some(t => t.toLowerCase().includes(vmSearch.toLowerCase()))))',
    b'    .filter(v => !filterPower || (filterPower === "on" ? v.status === "poweredOn" : v.status !== "poweredOn"))',
    b'    .filter(v => !filterOS || (v.guest_os || "").toLowerCase().includes(filterOS.toLowerCase()))',
    b'    .filter(v => !filterTag || (Array.isArray(v.tags) && v.tags.some(t => t.toLowerCase().includes(filterTag.toLowerCase()))))',
    b'    .filter(v => !filterApp || (Array.isArray(v.applications) && v.applications.some(a => a.app.toLowerCase().includes(filterApp.toLowerCase()))));',
    b'  const _uniqueOS = [...new Set(allVMs.map(v => v.guest_os).filter(Boolean))];',
    b'  const _uniqueTags = [...new Set(allVMs.flatMap(v => v.tags || []))];',
    b'  const _uniqueApps = [...new Set(allVMs.flatMap(v => (v.applications || []).map(a => a.app)))];',
    b'  const selectedVMList = allVMs.filter(v => selVMs[v.moid || v.name]);',
])

c = raw.count(old_lines)
print(f'Found {c} match(es)')
if c == 1:
    raw = raw.replace(old_lines, new_block, 1)
    open(path, 'wb').write(raw)
    print('Fixed filteredVMs + unique lists + selectedVMList')
else:
    print('ERROR')
