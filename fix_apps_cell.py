path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
data = open(path, 'rb').read()

# Find the tags cell: vm.tags.join(", ") : "-"}</td>
marker = b'vm.tags.join(", ") : "-"}</td>'
idx = data.find(marker)
if idx < 0:
    print("Marker not found")
    exit()

insert_pos = idx + len(marker)
print("Found tags cell end at byte", insert_pos)
print("Next chars:", data[insert_pos:insert_pos+50])

apps_cell = (
    b'\r\n                            <td style={{ ...tdStyle, fontSize: 12 }}>'
    b'{Array.isArray(vm.applications) && vm.applications.length ? vm.applications.map((a,i) => '
    b'<span key={i} style={{display:"inline-block",padding:"2px 8px",borderRadius:12,'
    b'fontSize:11,fontWeight:600,marginRight:4,marginBottom:2,'
    b'background:"rgba(99,102,241,0.13)",color:"#818cf8"}}>{a}</span>'
    b') : "-"}</td>'
)

if b'vm.applications' not in data:
    data = data[:insert_pos] + apps_cell + data[insert_pos:]
    open(path, 'wb').write(data)
    print("Added Applications cell. Done.")
else:
    print("Already exists")
