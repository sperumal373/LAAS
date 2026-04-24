f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()

# 1. Add liveMtvStatus state
old1 = b'const [liveStatus, setLiveStatus] = useState("");'
new1 = b'const [liveStatus, setLiveStatus] = useState("");\r\n  const [liveMtvStatus, setLiveMtvStatus] = useState(null);'
assert old1 in raw, "C1 not found"
raw = raw.replace(old1, new1, 1)
print("1 OK")

# 2. In polling interval: add setLiveMtvStatus after setLiveStatus
old2 = b'setLiveStatus(r.status || "");\r\n        if (["completed", "failed"'
new2 = b'setLiveStatus(r.status || "");\r\n        if (r.mtv_status) setLiveMtvStatus(r.mtv_status);\r\n        if (["completed", "failed"'
assert old2 in raw, "C2 not found"
raw = raw.replace(old2, new2, 1)
print("2 OK")

# 3. In initial fetch: add setLiveMtvStatus after setLiveStatus
old3 = b'setLiveStatus(r.status || "");\r\n    }).catch(() => {});'
new3 = b'setLiveStatus(r.status || "");\r\n      if (r.mtv_status) setLiveMtvStatus(r.mtv_status);\r\n    }).catch(() => {});'
assert old3 in raw, "C3 not found"
raw = raw.replace(old3, new3, 1)
print("3 OK")

# 4. Insert MTV pipeline stages UI
marker = b'</div>\r\n                            )}\r\n                            {actions.length > 0 && ('
assert marker in raw, "C4 marker not found"
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
print("4 OK")

open(f, 'wb').write(raw)
print("Done! File size:", len(raw))