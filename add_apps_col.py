path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
data = open(path, "rb").read()
NL = b"\r\n"

changes = 0

# 1. Add APPLICATIONS header between VM Tags and ESXi Host
old1 = b'                        <th style={thStyle}>VM Tags</th>' + NL + b'                        <th style={thStyle}>ESXi Host</th>'
new1 = b'                        <th style={thStyle}>VM Tags</th>' + NL + b'                        <th style={thStyle}>Applications</th>' + NL + b'                        <th style={thStyle}>ESXi Host</th>'
if old1 in data:
    data = data.replace(old1, new1)
    changes += 1
    print("1. Added Applications header")

# 2. Add applications data cell between vm.tags and vm.host
old2 = (
    b"""{Array.isArray(vm.tags) && vm.tags.length ? vm.tags.join(", ") : "-"}</td>""" + NL +
    b"""                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>"""
)
app_cell = (
    b"""{Array.isArray(vm.tags) && vm.tags.length ? vm.tags.join(", ") : "-"}</td>""" + NL +
    b"""                            <td style={{ ...tdStyle, fontSize: 11 }}>""" + NL +
    b"""                              {Array.isArray(vm.applications) && vm.applications.length ? (""" + NL +
    b"""                                <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>""" + NL +
    b"""                                  {vm.applications.map((a, ai) => (""" + NL +
    b"""                                    <span key={ai} style={{""" + NL +
    b"""                                      display: "inline-block", padding: "2px 7px", borderRadius: 6, fontSize: 10, fontWeight: 600,""" + NL +
    b"""                                      background: a.category === "database" ? "#f59e0b22" : a.category === "web" ? "#3b82f622" : a.category === "container" ? "#8b5cf622" : a.category === "devops" ? "#10b98122" : a.category === "infra" ? "#6366f122" : a.category === "monitoring" ? "#ec489922" : "#64748b22",""" + NL +
    b"""                                      color: a.category === "database" ? "#f59e0b" : a.category === "web" ? "#3b82f6" : a.category === "container" ? "#8b5cf6" : a.category === "devops" ? "#10b981" : a.category === "infra" ? "#6366f1" : a.category === "monitoring" ? "#ec4899" : "#94a3b8",""" + NL +
    b"""                                      border: "1px solid " + (a.category === "database" ? "#f59e0b33" : a.category === "web" ? "#3b82f633" : a.category === "container" ? "#8b5cf633" : a.category === "devops" ? "#10b98133" : a.category === "infra" ? "#6366f133" : a.category === "monitoring" ? "#ec489933" : "#64748b33"),""" + NL +
    b"""                                    }}>{a.app}</span>""" + NL +
    b"""                                  ))}""" + NL +
    b"""                                </div>""" + NL +
    b"""                              ) : <span style={{ color: p.textMute }}>-</span>}""" + NL +
    b"""                            </td>""" + NL +
    b"""                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>"""
)
if old2 in data:
    data = data.replace(old2, app_cell)
    changes += 1
    print("2. Added Applications data cell")

# 3. Update colSpan from 10 to 11 for "No VMs found"
old3 = b'colSpan={10}'
new3 = b'colSpan={11}'
if old3 in data:
    data = data.replace(old3, new3, 1)
    changes += 1
    print("3. Updated colSpan to 11")

# 4. Add applications to search filter
old4 = b"""(Array.isArray(v.tags) && v.tags.some(t => t.toLowerCase().includes(vmSearch.toLowerCase()))))"""
new4 = b"""(Array.isArray(v.tags) && v.tags.some(t => t.toLowerCase().includes(vmSearch.toLowerCase()))) || (Array.isArray(v.applications) && v.applications.some(a => a.app.toLowerCase().includes(vmSearch.toLowerCase()))))"""
if old4 in data:
    data = data.replace(old4, new4)
    changes += 1
    print("4. Added applications to search filter")

open(path, "wb").write(data)
print(f"\nDone - {changes} changes applied")
