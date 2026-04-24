path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
data = open(path, "rb").read()
NL = b"\r\n"
lines = data.split(NL)
changes = 0

# Find Applications header line and add Topology after it
for i, line in enumerate(lines):
    if b"<th style={thStyle}>Applications</th>" in line:
        # Insert Topology header after Applications
        new_line = b'                        <th style={thStyle}>Topology</th>'
        lines.insert(i + 1, new_line)
        changes += 1
        print(f"1. Added Topology header at line {i+2}")
        break

# Find the closing </td> of applications cell and add topology cell after it
# Look for the vm.host td and insert before it
for i, line in enumerate(lines):
    if b"vm.host" in line and b"<td" in line and i > 700:
        # Insert topology cell before host cell
        topo_cell = [
            b'                            <td style={{ ...tdStyle, fontSize: 11, textAlign: "center" }}>',
            b'                              {vm.topology === "Cluster" ? (',
            b'                                <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 700,',
            b'                                  background: "#8b5cf622", color: "#a78bfa", border: "1px solid #8b5cf633" }}>',
            b'                                  <span style={{ fontSize: 12 }}>{"\u{1F517}"}</span> Cluster',
            b'                                  {vm.cluster_type ? <span style={{ fontSize: 9, opacity: 0.8, marginLeft: 2 }}>({vm.cluster_type})</span> : null}',
            b'                                </span>',
            b'                              ) : (',
            b'                                <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 700,',
            b'                                  background: "#64748b22", color: "#94a3b8", border: "1px solid #64748b33" }}>',
            b'                                  <span style={{ fontSize: 12 }}>{"\u{1F4E6}"}</span> Standalone',
            b'                                </span>',
            b'                              )}',
            b'                            </td>',
        ]
        for j, tc in enumerate(topo_cell):
            lines.insert(i + j, tc)
        changes += 1
        print(f"2. Added Topology data cell at line {i+1}")
        break

# Update colSpan for "No VMs found"
for i, line in enumerate(lines):
    if b'colSpan={11}' in line:
        lines[i] = line.replace(b'colSpan={11}', b'colSpan={12}')
        changes += 1
        print(f"3. Updated colSpan to 12")
        break

# Add topology to search filter
for i, line in enumerate(lines):
    if b'v.applications) && v.applications.some' in line:
        # Add topology search
        old_end = b'))))'
        new_end = b'))) || (v.topology && v.topology.toLowerCase().includes(vmSearch.toLowerCase())) || (v.cluster_type && v.cluster_type.toLowerCase().includes(vmSearch.toLowerCase())))'
        if old_end in line:
            lines[i] = line.replace(old_end, new_end, 1)
            changes += 1
            print(f"4. Added topology to search filter")
        break

data = NL.join(lines)
open(path, "wb").write(data)
print(f"\nDone - {changes} changes applied")
