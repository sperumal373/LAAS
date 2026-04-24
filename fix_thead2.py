path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
data = open(path, 'rb').read()

vm_name_idx = data.find(b'VM Name</th>')
thead_end = data.find(b'</thead>', vm_name_idx) + len(b'</thead>')
old_block = data[vm_name_idx:thead_end]

ss = b'padding:"2px 4px",borderRadius:5,border:"1px solid "+p.border,background:p.bg,color:p.text,fontSize:10'

new_block = (
    b'VM Name</th>\r\n'
    b'                        <th style={thStyle}><div style={{display:"flex",alignItems:"center",gap:6}}>Power <select value={fPower} onChange={e=>setFPower(e.target.value)} style={{' + ss + b',width:60}}><option value="">All</option><option value="on">On</option><option value="off">Off</option></select></div></th>\r\n'
    b'                        <th style={thStyle}>CPU</th>\r\n'
    b'                        <th style={thStyle}>RAM (GB)</th>\r\n'
    b'                        <th style={thStyle}>Disk (GB)</th>\r\n'
    b'                        <th style={thStyle}><div style={{display:"flex",alignItems:"center",gap:6}}>Guest OS <select value={fOS} onChange={e=>setFOS(e.target.value)} style={{' + ss + b',maxWidth:120}}><option value="">All</option>{[...new Set(allVMs.map(v=>v.guest_os||"").filter(Boolean))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></div></th>\r\n'
    b'                        <th style={thStyle}>IP Address</th>\r\n'
    b'                        <th style={thStyle}><div style={{display:"flex",alignItems:"center",gap:6}}>VM Tags <select value={fTag} onChange={e=>setFTag(e.target.value)} style={{' + ss + b',maxWidth:100}}><option value="">All</option>{[...new Set(allVMs.flatMap(v=>Array.isArray(v.tags)?v.tags.map(t=>typeof t==="string"?t:t.tag||""):[]).filter(Boolean))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></div></th>\r\n'
    b'                        <th style={thStyle}><div style={{display:"flex",alignItems:"center",gap:6}}>Applications <select value={fApp} onChange={e=>setFApp(e.target.value)} style={{' + ss + b',maxWidth:100}}><option value="">All</option>{[...new Set(allVMs.flatMap(v=>Array.isArray(v.applications)?v.applications.map(a=>typeof a==="string"?a:a.app||""):[]).filter(Boolean))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></div></th>\r\n'
    b'                        <th style={thStyle}>ESXi Host</th>\r\n'
    b'                      </tr>\r\n'
    b'                    </thead>'
)

data = data.replace(old_block, new_block, 1)

# Also fix the power filter comparison - power_state could be "poweredOn"/"poweredOff"
old_pf = b'!fPower || (v.power_state || "").toLowerCase() === fPower.toLowerCase()'
new_pf = b'!fPower || (fPower === "on" ? (v.power_state || "").toLowerCase().includes("on") : (v.power_state || "").toLowerCase().includes("off"))'
data = data.replace(old_pf, new_pf, 1)

open(path, 'wb').write(data)
print("Done - inline filters + power on/off fixed")
