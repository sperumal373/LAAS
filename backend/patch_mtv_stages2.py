f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()

# CHANGE 1 already applied (liveMtvStatus state exists)
if b'liveMtvStatus' not in raw:
    old1 = b'const [liveStatus, setLiveStatus] = useState("");'
    new1 = b'const [liveStatus, setLiveStatus] = useState("");\r\n  const [liveMtvStatus, setLiveMtvStatus] = useState(null);'
    raw = raw.replace(old1, new1)
    print("1. Added liveMtvStatus state")
else:
    print("1. liveMtvStatus already exists")

# CHANGE 2: Store mtv_status during polling - find the exact pattern
if b'setLiveMtvStatus' not in raw or raw.count(b'setLiveMtvStatus') < 2:
    # In the interval callback
    old2a = b'setLiveStatus(r.status || "");\r\n        if (r.mtv_status) setLiveMtvStatus(r.mtv_status);\r\n        if (["completed"'
    old2b = b'setLiveStatus(r.status || "");\r\n        if (["completed"'
    if old2a in raw:
        print("2. Already has setLiveMtvStatus in interval")
    elif old2b in raw:
        raw = raw.replace(old2b, b'setLiveStatus(r.status || "");\r\n        if (r.mtv_status) setLiveMtvStatus(r.mtv_status);\r\n        if (["completed"', 1)
        print("2. Added setLiveMtvStatus in interval")
    else:
        print("2. WARNING: Could not find interval pattern")
    
    # In the initial fetch
    old3a = b'setLiveStatus(r.status || "");\r\n      if (r.mtv_status) setLiveMtvStatus(r.mtv_status);\r\n    }).catch'
    old3b = b'setLiveStatus(r.status || "");\r\n    }).catch'
    if old3a in raw:
        print("3. Already has setLiveMtvStatus in initial fetch")
    elif old3b in raw:
        raw = raw.replace(old3b, b'setLiveStatus(r.status || "");\r\n      if (r.mtv_status) setLiveMtvStatus(r.mtv_status);\r\n    }).catch', 1)
        print("3. Added setLiveMtvStatus in initial fetch")
    else:
        print("3. WARNING: Could not find initial fetch pattern")
else:
    print("2-3. setLiveMtvStatus already wired up")

# CHANGE 4: MTV pipeline - check if already added
if b'MTV Migration Stages' in raw:
    print("4. MTV pipeline already exists")
else:
    # Insert after progress bar, before actions
    marker = b'</div>\r\n                            )}\r\n                            {actions.length > 0 && ('
    if marker not in raw:
        print("4. ERROR: Could not find insertion marker")
    else:
        # Build the component as a separate file for clarity
        comp = (
            b'</div>\r\n                            )}\r\n'
            b'                            {/* MTV Pipeline Stages */}\r\n'
            b'                            {plan.target_platform === "openshift" && isLive && liveMtvStatus && liveMtvStatus.vms && liveMtvStatus.vms.length > 0 && (\r\n'
            b'                              <div style={{ marginBottom: 14, padding: 14, borderRadius: 8, background: `${p.surface}`, border: `1px solid ${p.border}` }}>\r\n'
            b'                                <div style={{ fontSize: 13, fontWeight: 800, color: p.text, marginBottom: 10, textTransform: "uppercase", letterSpacing: ".5px" }}>{"\xf0\x9f\x94\x84"} MTV Migration Stages</div>\r\n'
            b'                                {liveMtvStatus.vms.map((vm, vi) => {\r\n'
            b'                                  const MTV_STAGES = ["Initialize","PreflightInspection","DiskTransfer","Cutover","ImageConversion","VirtualMachineCreation"];\r\n'
            b'                                  const stageMap = {};\r\n'
            b'                                  (vm.pipeline || []).forEach(s => { stageMap[s.name] = s; });\r\n'
            b'                                  return (\r\n'
            b'                                    <div key={vi} style={{ marginBottom: vi < liveMtvStatus.vms.length - 1 ? 12 : 0 }}>\r\n'
            b'                                      <div style={{ fontSize: 12.5, fontWeight: 700, color: p.text, marginBottom: 8 }}>{"\xf0\x9f\x96\xa5\xef\xb8\x8f"} {vm.name || "VM"} <span style={{ fontSize: 11, fontWeight: 500, color: p.textMute, marginLeft: 6 }}>Phase: {vm.phase || "Pending"}</span></div>\r\n'
            b'                                      <div style={{ display: "flex", alignItems: "center", gap: 0 }}>\r\n'
            b'                                        {MTV_STAGES.map((stg, si) => {\r\n'
            b'                                          const info = stageMap[stg] || (stg === "DiskTransfer" ? stageMap["DiskTransferV2v"] || stageMap["DiskAllocation"] : null) || {};\r\n'
            b'                                          const ph = info.phase || "Pending";\r\n'
            b'                                          const done = ph === "Completed";\r\n'
            b'                                          const run = ph === "Running" || ph === "InProgress";\r\n'
            b'                                          const fail = ph === "Failed" || ph === "Error";\r\n'
            b'                                          const clr = done ? "#22c55e" : run ? "#3b82f6" : fail ? "#ef4444" : `${p.textMute}55`;\r\n'
            b'                                          const ico = done ? "\\u2714" : run ? "\\u23F3" : fail ? "\\u2718" : "\\u25CB";\r\n'
            b'                                          const pct = info.total > 0 ? Math.round(info.completed / info.total * 100) : null;\r\n'
            b'                                          const lbl = stg.replace(/([A-Z])/g, " $1").trim();\r\n'
            b'                                          return <Fragment key={stg}>\r\n'
            b'                                            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, minWidth: 0 }}>\r\n'
            b'                                              <div style={{ width: 30, height: 30, borderRadius: "50%", background: !done && !run && !fail ? `${p.textMute}15` : `${clr}18`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, border: `2px solid ${clr}`, boxShadow: run ? `0 0 10px ${clr}44` : "none", transition: "all .3s", animation: run ? "pulse 2s infinite" : "none" }}>\r\n'
            b'                                                <span style={{ color: clr, fontWeight: 700 }}>{ico}</span>\r\n'
            b'                                              </div>\r\n'
            b'                                              <div style={{ fontSize: 10, marginTop: 3, color: !done && !run && !fail ? p.textMute : clr, fontWeight: run ? 800 : 600, textAlign: "center", lineHeight: 1.2, maxWidth: 80 }}>{lbl}</div>\r\n'
            b'                                              {pct !== null && <div style={{ fontSize: 9, color: clr, fontWeight: 700, marginTop: 1 }}>{pct}%</div>}\r\n'
            b'                                            </div>\r\n'
            b'                                            {si < MTV_STAGES.length - 1 && <div style={{ flex: 0.6, height: 2, borderRadius: 1, background: done ? "#22c55e" : `${p.textMute}22`, transition: "background .5s", marginBottom: 20 }} />}\r\n'
            b'                                          </Fragment>;\r\n'
            b'                                        })}\r\n'
            b'                                      </div>\r\n'
            b'                                    </div>\r\n'
            b'                                  );\r\n'
            b'                                })}\r\n'
            b'                              </div>\r\n'
            b'                            )}\r\n'
            b'                            {actions.length > 0 && ('
        )
        raw = raw.replace(marker, comp, 1)
        print("4. MTV pipeline stages component added")

open(f, 'wb').write(raw)
print("All done!")