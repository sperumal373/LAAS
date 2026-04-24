path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()

# 1. Add IP ADDRESS and TAGS headers between Guest OS and ESXi Host
old1 = b'                        <th style={thStyle}>Guest OS</th>\r\n                        <th style={thStyle}>ESXi Host</th>'
new1 = b'                        <th style={thStyle}>Guest OS</th>\r\n                        <th style={thStyle}>IP Address</th>\r\n                        <th style={thStyle}>VM Tags</th>\r\n                        <th style={thStyle}>ESXi Host</th>'

# 2. Add IP and Tags cells between guest_os and host in table rows
old2 = b'                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.guest_os || "-"}</td>\r\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>'
new2 = b'                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.guest_os || "-"}</td>\r\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500, fontFamily: "monospace" }}>{vm.ip || "-"}</td>\r\n                            <td style={{ ...tdStyle, fontSize: 11, fontWeight: 500 }}>{Array.isArray(vm.tags) && vm.tags.length ? vm.tags.join(", ") : "-"}</td>\r\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>'

# 3. Update colspan for empty state (was 8, now 10)
old3 = b'<td colSpan={8} style={{ ...tdStyle, textAlign: "center", color: p.textMute, padding: 30 }}>No VMs found</td>'
new3 = b'<td colSpan={10} style={{ ...tdStyle, textAlign: "center", color: p.textMute, padding: 30 }}>No VMs found</td>'

# Also update search to include tags
old4 = b'v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()))'
new4 = b'v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()) || v.ip?.toLowerCase().includes(vmSearch.toLowerCase()) || (Array.isArray(v.tags) && v.tags.some(t => t.toLowerCase().includes(vmSearch.toLowerCase()))))'

replacements = [(old1, new1), (old2, new2), (old3, new3), (old4, new4)]
for i, (old, new) in enumerate(replacements, 1):
    c = raw.count(old)
    if c != 1:
        print(f'ERROR: replacement {i} found {c} matches')
        import sys; sys.exit(1)
    raw = raw.replace(old, new, 1)
    print(f'Replacement {i}: OK')

open(path, 'wb').write(raw)
print('All done!')
