path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()

# 1. Add Applications header after VM Tags header
old1 = b'                        <th style={thStyle}>VM Tags</th>\r\n                        <th style={thStyle}>ESXi Host</th>'
new1 = b'                        <th style={thStyle}>VM Tags</th>\r\n                        <th style={thStyle}>Applications</th>\r\n                        <th style={thStyle}>ESXi Host</th>'

# 2. Add Applications data cell after VM Tags cell  
old2 = b'                            <td style={{ ...tdStyle, fontSize: 11, fontWeight: 500 }}>{Array.isArray(vm.tags) && vm.tags.length ? vm.tags.join(", ") : "-"}</td>\r\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>'
new2 = b'                            <td style={{ ...tdStyle, fontSize: 11, fontWeight: 500 }}>{Array.isArray(vm.tags) && vm.tags.length ? vm.tags.join(", ") : "-"}</td>\r\n                            <td style={{ ...tdStyle, fontSize: 11, fontWeight: 600 }}>{Array.isArray(vm.applications) && vm.applications.length ? vm.applications.map(a => a.app).join(", ") : "-"}</td>\r\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>'

# 3. Update colspan for empty state (was 10, now 11)
old3 = b'<td colSpan={10} style={{ ...tdStyle, textAlign: "center", color: p.textMute, padding: 30 }}>No VMs found</td>'
new3 = b'<td colSpan={11} style={{ ...tdStyle, textAlign: "center", color: p.textMute, padding: 30 }}>No VMs found</td>'

for i, (old, new) in enumerate([(old1,new1),(old2,new2),(old3,new3)], 1):
    c = raw.count(old)
    if c != 1:
        print(f'ERROR: replacement {i} found {c} matches')
        import sys; sys.exit(1)
    raw = raw.replace(old, new, 1)
    print(f'Replacement {i}: OK')

open(path, 'wb').write(raw)
print('All done!')
