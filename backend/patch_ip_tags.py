f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
c = open(f, encoding='utf-8').read()
orig = c

# 1 - Add column headers
old_h = '<th style={thStyle}>Guest OS</th>\n                        <th style={thStyle}>ESXi Host</th>'
new_h = '<th style={thStyle}>Guest OS</th>\n                        <th style={thStyle}>IP Address</th>\n                        <th style={thStyle}>Tags</th>\n                        <th style={thStyle}>ESXi Host</th>'
c = c.replace(old_h, new_h)

# 2 - Add cells
old_c = '{vm.guest_os || "-"}</td>\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>'
new_c = '{vm.guest_os || "-"}</td>\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.ip || "-"}</td>\n                            <td style={{ ...tdStyle, fontSize: 11, fontWeight: 500, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={Array.isArray(vm.tags) && vm.tags.length > 0 ? vm.tags.map(t => typeof t === "string" ? t : (t.tag || t.name || "")).join(", ") : ""}>{Array.isArray(vm.tags) && vm.tags.length > 0 ? vm.tags.map(t => typeof t === "string" ? t : (t.tag || t.name || "")).join(", ") : "-"}</td>\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>'
c = c.replace(old_c, new_c)

# 3 - colSpan
c = c.replace('colSpan={8}', 'colSpan={10}')

# 4 - search filter
old_f = 'v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()));'
new_f = 'v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()) || v.ip?.toLowerCase().includes(vmSearch.toLowerCase()) || (Array.isArray(v.tags) && v.tags.some(t => (typeof t === "string" ? t : (t.tag || t.name || "")).toLowerCase().includes(vmSearch.toLowerCase()))));'
c = c.replace(old_f, new_f)

changes = 0
if 'IP Address' in c: changes += 1
if 'vm.ip' in c: changes += 1
if 'colSpan={10}' in c: changes += 1
if 'v.ip?' in c: changes += 1
print(f'Changes verified: {changes}/4')
open(f, 'w', encoding='utf-8').write(c)
print('Saved!')
