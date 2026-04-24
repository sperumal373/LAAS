path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
data = open(path, 'rb').read()

# 1. Add filter state vars after vmSearch state
marker1 = b'const [vmSearch, setVmSearch] = useState("");'
filter_states = (
    b'const [vmSearch, setVmSearch] = useState("");\r\n'
    b'  const [fPower, setFPower] = useState("");\r\n'
    b'  const [fOS, setFOS] = useState("");\r\n'
    b'  const [fTag, setFTag] = useState("");\r\n'
    b'  const [fApp, setFApp] = useState("");\r\n'
    b'  const hasFilters = fPower || fOS || fTag || fApp;'
)
data = data.replace(marker1, filter_states, 1)
print("1. Added filter state vars")

# 2. Update filteredVMs to include new filters
old_filter = (
    b'filteredVMs = allVMs\r\n'
    b'    .filter(v => !selHost || v.host === selHost)\r\n'
    b'    .filter(v => !vmSearch || v.name?.toLowerCase().includes(vmSearch.toLowerCase()) || v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()) || v.ip?.toLowerCase().includes(vmSearch.toLowerCase()) || (Array.isArray(v.tags) && v.tags.some(t => t.toLowerCase().includes(vmSearch.toLowerCase()))));'
)
new_filter = (
    b'filteredVMs = allVMs\r\n'
    b'    .filter(v => !selHost || v.host === selHost)\r\n'
    b'    .filter(v => !vmSearch || v.name?.toLowerCase().includes(vmSearch.toLowerCase()) || v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()) || v.ip?.toLowerCase().includes(vmSearch.toLowerCase()) || (Array.isArray(v.tags) && v.tags.some(t => t.toLowerCase().includes(vmSearch.toLowerCase()))))\r\n'
    b'    .filter(v => !fPower || (v.power_state || "").toLowerCase() === fPower.toLowerCase())\r\n'
    b'    .filter(v => !fOS || (v.guest_os || "") === fOS)\r\n'
    b'    .filter(v => !fTag || (Array.isArray(v.tags) && v.tags.some(t => (typeof t === "string" ? t : t.tag || "").includes(fTag))))\r\n'
    b'    .filter(v => !fApp || (Array.isArray(v.applications) && v.applications.some(a => (typeof a === "string" ? a : a.app || "") === fApp)));'
)
data = data.replace(old_filter, new_filter, 1)
print("2. Updated filteredVMs logic")

# 3. Add filter dropdowns under column headers - replace the </thead> area
# We add a second <tr> row with filter selects
old_thead_end = b'</tr>\r\n                    </thead>'
# Build unique value extractors + select elements for filters
filter_row = (
    b'</tr>\r\n'
    b'                      <tr style={{background:p.panelAlt}}>\r\n'
    b'                        <th></th><th></th>\r\n'
    b'                        <th style={{padding:"4px 6px"}}><select value={fPower} onChange={e=>setFPower(e.target.value)} style={{width:"100%",padding:"3px 4px",borderRadius:6,border:"1px solid "+p.border,background:p.bg,color:p.text,fontSize:11}}><option value="">All</option>{[...new Set(allVMs.map(v=>(v.power_state||"").toLowerCase()))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></th>\r\n'
    b'                        <th></th><th></th>\r\n'
    b'                        <th style={{padding:"4px 6px"}}><select value={fOS} onChange={e=>setFOS(e.target.value)} style={{width:"100%",padding:"3px 4px",borderRadius:6,border:"1px solid "+p.border,background:p.bg,color:p.text,fontSize:11}}><option value="">All</option>{[...new Set(allVMs.map(v=>v.guest_os||"").filter(Boolean))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></th>\r\n'
    b'                        <th></th>\r\n'
    b'                        <th style={{padding:"4px 6px"}}><select value={fTag} onChange={e=>setFTag(e.target.value)} style={{width:"100%",padding:"3px 4px",borderRadius:6,border:"1px solid "+p.border,background:p.bg,color:p.text,fontSize:11}}><option value="">All</option>{[...new Set(allVMs.flatMap(v=>Array.isArray(v.tags)?v.tags.map(t=>typeof t==="string"?t:t.tag||""):[]).filter(Boolean))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></th>\r\n'
    b'                        <th style={{padding:"4px 6px"}}><select value={fApp} onChange={e=>setFApp(e.target.value)} style={{width:"100%",padding:"3px 4px",borderRadius:6,border:"1px solid "+p.border,background:p.bg,color:p.text,fontSize:11}}><option value="">All</option>{[...new Set(allVMs.flatMap(v=>Array.isArray(v.applications)?v.applications.map(a=>typeof a==="string"?a:a.app||""):[]).filter(Boolean))].sort().map(v=><option key={v} value={v}>{v}</option>)}</select></th>\r\n'
    b'                        <th></th>\r\n'
    b'                      </tr>\r\n'
    b'                    </thead>'
)
data = data.replace(old_thead_end, filter_row, 1)
print("3. Added filter row in thead")

# 4. Add clear filters button near the search box
# Find the vmSearch input and add a clear button after the search area
search_input_marker = b'placeholder="Search VMs'
idx = data.find(search_input_marker)
if idx > 0:
    # Find the closing /> of this input
    close = data.find(b'/>', idx)
    insert_pos = close + 2
    clear_btn = (
        b'\r\n                    {hasFilters && <button onClick={() => {setFPower("");setFOS("");setFTag("");setFApp("");}} '
        b'style={{marginLeft:8,padding:"6px 14px",borderRadius:8,border:"1px solid "+p.accent,background:"transparent",color:p.accent,fontSize:11.5,fontWeight:700,cursor:"pointer",letterSpacing:".5px"}}'
        b'>\u2715 Clear Filters</button>}'
    )
    data = data[:insert_pos] + clear_btn + data[insert_pos:]
    print("4. Added clear filters button")
else:
    print("4. Search input not found, skipping clear button")

open(path, 'wb').write(data)
print("Done!")
