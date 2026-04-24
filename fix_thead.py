path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
data = open(path, 'rb').read()

# Find the header row start (VM Name) and thead end
vm_name_idx = data.find(b'VM Name</th>')
thead_end = data.find(b'</thead>', vm_name_idx)
thead_end_full = thead_end + len(b'</thead>')

# Get everything from VM Name</th> to </thead> and replace it
old_block = data[vm_name_idx:thead_end_full]

ss = b'style={{width:"100%",padding:"2px 4px",borderRadius:5,border:"1px solid "+p.border,background:p.bg,color:p.text,fontSize:10,marginTop:4}}'

new_block = (
    b'VM Name</th>\r\n'
    b'                        <th style={thStyle}><div>Power</div><select value={fPower} onChange={e=>setFPower(e.target.value)} ' + ss + b'><option value="">All</option>{[...new Set(allVMs.map(v=>(v.power_state||"").toLowerCase()))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></th>\r\n'
    b'                        <th style={thStyle}>CPU</th>\r\n'
    b'                        <th style={thStyle}>RAM (GB)</th>\r\n'
    b'                        <th style={thStyle}>Disk (GB)</th>\r\n'
    b'                        <th style={thStyle}><div>Guest OS</div><select value={fOS} onChange={e=>setFOS(e.target.value)} ' + ss + b'><option value="">All</option>{[...new Set(allVMs.map(v=>v.guest_os||"").filter(Boolean))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></th>\r\n'
    b'                        <th style={thStyle}>IP Address</th>\r\n'
    b'                        <th style={thStyle}><div>VM Tags</div><select value={fTag} onChange={e=>setFTag(e.target.value)} ' + ss + b'><option value="">All</option>{[...new Set(allVMs.flatMap(v=>Array.isArray(v.tags)?v.tags.map(t=>typeof t==="string"?t:t.tag||""):[]).filter(Boolean))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></th>\r\n'
    b'                        <th style={thStyle}><div>Applications</div><select value={fApp} onChange={e=>setFApp(e.target.value)} ' + ss + b'><option value="">All</option>{[...new Set(allVMs.flatMap(v=>Array.isArray(v.applications)?v.applications.map(a=>typeof a==="string"?a:a.app||""):[]).filter(Boolean))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></th>\r\n'
    b'                        <th style={thStyle}>ESXi Host</th>\r\n'
    b'                      </tr>\r\n'
    b'                    </thead>'
)

data = data.replace(old_block, new_block, 1)
open(path, 'wb').write(data)
print("Replaced thead - inline filters, no extra rows")
