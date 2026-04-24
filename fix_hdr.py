path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
raw = open(path, "rb").read()

# Replace the 4 plain th headers with select-in-header versions
old = b'''                        <th style={thStyle}>Power</th>
                        <th style={thStyle}>CPU</th>
                        <th style={thStyle}>RAM (GB)</th>
                        <th style={thStyle}>Disk (GB)</th>
                        <th style={thStyle}>Guest OS</th>
                        <th style={thStyle}>IP Address</th>
                        <th style={thStyle}>VM Tags</th>
                        <th style={thStyle}>Applications</th>
                        <th style={thStyle}>ESXi Host</th>'''

fSel = 'background:"transparent",color:p.textSub,border:"none",fontSize:10,fontWeight:700,cursor:"pointer",padding:0,textTransform:"uppercase",letterSpacing:".5px"'

new = (
    '                        <th style={thStyle}><select value={filterPower} onChange={e => setFilterPower(e.target.value)} style={{' + fSel + '}}><option value="">Power \u25BE</option><option value="on">ON</option><option value="off">OFF</option></select></th>\n'
    '                        <th style={thStyle}>CPU</th>\n'
    '                        <th style={thStyle}>RAM (GB)</th>\n'
    '                        <th style={thStyle}>Disk (GB)</th>\n'
    '                        <th style={thStyle}><select value={filterOS} onChange={e => setFilterOS(e.target.value)} style={{' + fSel + ',maxWidth:140}}><option value="">Guest OS \u25BE</option>{_uniqueOS.map(os => <option key={os} value={os}>{os.length>35?os.slice(0,32)+"...":os}</option>)}</select></th>\n'
    '                        <th style={thStyle}>IP Address</th>\n'
    '                        <th style={thStyle}><select value={filterTag} onChange={e => setFilterTag(e.target.value)} style={{' + fSel + ',maxWidth:120}}><option value="">VM Tags \u25BE</option>{_uniqueTags.map(t => <option key={t} value={t}>{t}</option>)}</select></th>\n'
    '                        <th style={thStyle}><select value={filterApp} onChange={e => setFilterApp(e.target.value)} style={{' + fSel + ',maxWidth:130}}><option value="">Applications \u25BE</option>{_uniqueApps.map(a => <option key={a} value={a}>{a}</option>)}</select></th>\n'
    '                        <th style={thStyle}>ESXi Host</th>'
).encode("utf-8")

old = old.replace(b"\n", b"\r\n")
new = new.replace(b"\n", b"\r\n")

c = raw.count(old)
print(f"Found {c}")
if c == 1:
    raw = raw.replace(old, new, 1)
    open(path, "wb").write(raw)
    print("Done - inline filters in headers")
else:
    print("ERROR - no match")