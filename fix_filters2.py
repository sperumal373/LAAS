path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()
lines = raw.split(b'\r\n')

# Replacement 2: Add filter chains to filteredVMs (line 250 ends with ;)
old2 = lines[250]  # the last .filter line ending with ));
# Remove trailing ); and add new filters
new2 = old2.rstrip(b';').rstrip(b')') + b')\r\n    .filter(v => !filterPower || (filterPower === "on" ? v.status === "poweredOn" : v.status !== "poweredOn"))\r\n    .filter(v => !filterOS || (v.guest_os || "").toLowerCase().includes(filterOS.toLowerCase()))\r\n    .filter(v => !filterTag || (Array.isArray(v.tags) && v.tags.some(t => t.toLowerCase().includes(filterTag.toLowerCase()))))\r\n    .filter(v => !filterApp || (Array.isArray(v.applications) && v.applications.some(a => a.app.toLowerCase().includes(filterApp.toLowerCase()))));'

c = raw.count(old2)
print(f'Found {c} match(es) for old2')
if c == 1:
    raw = raw.replace(old2, new2, 1)
    print('Replacement 2: OK')
else:
    import sys; sys.exit(1)

# Replacement 3: Add unique value computations
old3 = b'  const selectedVMList = allVMs.filter(v => selVMs[v.moid || v.name]);'
new3 = b'  const _uniqueOS = [...new Set(allVMs.map(v => v.guest_os).filter(Boolean))];\r\n  const _uniqueTags = [...new Set(allVMs.flatMap(v => v.tags || []))];\r\n  const _uniqueApps = [...new Set(allVMs.flatMap(v => (v.applications || []).map(a => a.app)))];\r\n  const selectedVMList = allVMs.filter(v => selVMs[v.moid || v.name]);'
c = raw.count(old3)
print(f'Found {c} match(es) for old3')
if c == 1:
    raw = raw.replace(old3, new3, 1)
    print('Replacement 3: OK')

# Replacement 4: Add filter bar UI
old4 = b'            </div>\r\n\r\n            {loadingVMs ? <LoadDots p={p} /> : selVC && ('
new4 = b'            </div>\r\n            {allVMs.length > 0 && <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>\r\n              <select value={filterPower} onChange={e => setFilterPower(e.target.value)} style={{ ...selectStyle, flex: "0 0 auto", minWidth: 120, fontSize: 12 }}>\r\n                <option value="">All Power</option><option value="on">Powered ON</option><option value="off">Powered OFF</option>\r\n              </select>\r\n              <select value={filterOS} onChange={e => setFilterOS(e.target.value)} style={{ ...selectStyle, flex: "0 0 auto", minWidth: 180, fontSize: 12 }}>\r\n                <option value="">All Guest OS</option>\r\n                {_uniqueOS.map(os => <option key={os} value={os}>{os.length > 40 ? os.slice(0,37) + "..." : os}</option>)}\r\n              </select>\r\n              <select value={filterTag} onChange={e => setFilterTag(e.target.value)} style={{ ...selectStyle, flex: "0 0 auto", minWidth: 150, fontSize: 12 }}>\r\n                <option value="">All Tags</option>\r\n                {_uniqueTags.map(t => <option key={t} value={t}>{t}</option>)}\r\n              </select>\r\n              <select value={filterApp} onChange={e => setFilterApp(e.target.value)} style={{ ...selectStyle, flex: "0 0 auto", minWidth: 160, fontSize: 12 }}>\r\n                <option value="">All Applications</option>\r\n                {_uniqueApps.map(a => <option key={a} value={a}>{a}</option>)}\r\n              </select>\r\n              {(filterPower || filterOS || filterTag || filterApp) && <button onClick={() => { setFilterPower(""); setFilterOS(""); setFilterTag(""); setFilterApp(""); }} style={{ background: "transparent", border: "1px solid " + p.border, borderRadius: 6, color: p.textMute, fontSize: 11, padding: "4px 12px", cursor: "pointer" }}>Clear Filters</button>}\r\n            </div>}\r\n\r\n            {loadingVMs ? <LoadDots p={p} /> : selVC && ('
c = raw.count(old4)
print(f'Found {c} match(es) for old4')
if c == 1:
    raw = raw.replace(old4, new4, 1)
    print('Replacement 4: OK')

open(path, 'wb').write(raw)
print('All done!')
