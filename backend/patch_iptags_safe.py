f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'

# Read as raw bytes, modify as bytes, write as bytes - no encoding conversion
raw = open(f, 'rb').read()

# 1 - Add column headers: between "Guest OS</th>" and "ESXi Host</th>"
old_h = b'<th style={thStyle}>Guest OS</th>\n                        <th style={thStyle}>ESXi Host</th>'
new_h = b'<th style={thStyle}>Guest OS</th>\n                        <th style={thStyle}>IP Address</th>\n                        <th style={thStyle}>Tags</th>\n                        <th style={thStyle}>ESXi Host</th>'
if old_h in raw:
    raw = raw.replace(old_h, new_h)
    print('1. Headers added')
else:
    # try with \r\n
    old_h2 = old_h.replace(b'\n', b'\r\n')
    new_h2 = new_h.replace(b'\n', b'\r\n')
    if old_h2 in raw:
        raw = raw.replace(old_h2, new_h2)
        print('1. Headers added (CRLF)')
    else:
        print('1. HEADER NOT FOUND')

# 2 - Add cells
old_c = b'{vm.guest_os || "-"}</td>\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>'
new_c = b'{vm.guest_os || "-"}</td>\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.ip || "-"}</td>\n                            <td style={{ ...tdStyle, fontSize: 11, fontWeight: 500, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={Array.isArray(vm.tags) && vm.tags.length > 0 ? vm.tags.map(t => typeof t === "string" ? t : (t.tag || t.name || "")).join(", ") : ""}>{Array.isArray(vm.tags) && vm.tags.length > 0 ? vm.tags.map(t => typeof t === "string" ? t : (t.tag || t.name || "")).join(", ") : "-"}</td>\n                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>'
if old_c in raw:
    raw = raw.replace(old_c, new_c)
    print('2. Cells added')
else:
    old_c2 = old_c.replace(b'\n', b'\r\n')
    new_c2 = new_c.replace(b'\n', b'\r\n')
    if old_c2 in raw:
        raw = raw.replace(old_c2, new_c2)
        print('2. Cells added (CRLF)')
    else:
        print('2. CELLS NOT FOUND')

# 3 - colSpan
if b'colSpan={8}' in raw:
    raw = raw.replace(b'colSpan={8}', b'colSpan={10}')
    print('3. colSpan fixed')

# 4 - search filter
old_f = b'v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()));'
new_f = b'v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()) || v.ip?.toLowerCase().includes(vmSearch.toLowerCase()) || (Array.isArray(v.tags) && v.tags.some(t => (typeof t === "string" ? t : (t.tag || t.name || "")).toLowerCase().includes(vmSearch.toLowerCase()))));'
if old_f in raw:
    raw = raw.replace(old_f, new_f)
    print('4. Search filter updated')
else:
    print('4. FILTER NOT FOUND')

open(f, 'wb').write(raw)
print('Saved - emojis preserved!')