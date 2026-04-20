f = open(r'C:\caas-dashboard\frontend\src\MigrationPage.jsx', 'r', encoding='utf-8')
c = f.read()
f.close()

if 'Cutover Mode' in c:
    print("Already has Cutover Mode UI")
else:
    marker = """                )}
              </div>
            </div>

            {/* Schedule"""

    cutover_block = '''                )}

                {/* Cutover Mode (Nutanix only) */}
                {targetPlatform === "nutanix" && (
                  <div style={{ padding: "12px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, gridColumn: "1 / -1" }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text, marginBottom: 10 }}>{String.fromCodePoint(0x2702, 0xFE0F)} Cutover Mode <span style={{fontSize:11,fontWeight:400,color:p.textSub}}>(when to switch over to target VM)</span></div>
                    <div style={{ display: "flex", gap: 10, marginBottom: 6 }}>
                      {[{val:"auto",icon:String.fromCodePoint(0x26A1),label:"Auto Cutover",desc:"Immediately after seeding completes (recommended)",color:"#22c55e"},
                        {val:"scheduled",icon:String.fromCodePoint(0x1F4C5),label:"Scheduled Cutover",desc:"Pick a date/time for cutover",color:"#f59e0b"},
                        {val:"manual",icon:String.fromCodePoint(0x1F5B1, 0xFE0F),label:"Manual Cutover",desc:"You trigger cutover from Move UI",color:"#8b5cf6"}
                      ].map(opt => (
                        <div key={opt.val} onClick={() => setMigCutoverMode(opt.val)}
                          style={{ flex: 1, padding: "10px 12px", borderRadius: 10, cursor: "pointer",
                            background: migCutoverMode === opt.val ? opt.color + "18" : p.panelAlt,
                            border: `2px solid ${migCutoverMode === opt.val ? opt.color : "transparent"}`,
                            transition: "all .2s" }}>
                          <div style={{ fontSize: 13, fontWeight: 700, color: migCutoverMode === opt.val ? opt.color : p.text }}>{opt.icon} {opt.label}</div>
                          <div style={{ fontSize: 11, color: p.textSub, marginTop: 3 }}>{opt.desc}</div>
                        </div>
                      ))}
                    </div>
                    {migCutoverMode === "scheduled" && (
                      <div style={{ marginTop: 8, padding: "8px 12px", borderRadius: 8, background: p.panelAlt }}>
                        <label style={{ fontSize: 12, fontWeight: 700, color: p.text, marginBottom: 4, display: "block" }}>Cutover Date/Time</label>
                        <input type="datetime-local" value={migCutoverDatetime} onChange={e => setMigCutoverDatetime(e.target.value)}
                          style={{ ...inputStyle, width: "100%", maxWidth: 280 }} />
                        <div style={{ fontSize: 11, color: "#f59e0b", marginTop: 4 }}>Seeding starts now. Cutover triggers at the scheduled time.</div>
                      </div>
                    )}
                    {migCutoverMode === "manual" && (
                      <div style={{ fontSize: 11, color: "#8b5cf6", marginTop: 4, padding: "6px 10px", borderRadius: 6, background: "#8b5cf610" }}>After seeding, open Move UI at https://172.16.146.117 to click Cutover.</div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Schedule'''

    if marker in c:
        c = c.replace(marker, cutover_block, 1)
        f = open(r'C:\caas-dashboard\frontend\src\MigrationPage.jsx', 'w', encoding='utf-8')
        f.write(c)
        f.close()
        print("Added Cutover Mode UI. Count:", c.count('Cutover Mode'))
    else:
        print("ERROR: marker not found in file")
        # Debug
        idx = c.find(')}')
        lines = c.split('\n')
        for i, line in enumerate(lines):
            if '{/* Schedule' in line:
                print(f"  Schedule comment at line {i+1}: {line.strip()[:80]}")
            if 'Target Namespace' in line:
                print(f"  Target Namespace at line {i+1}: {line.strip()[:80]}")
