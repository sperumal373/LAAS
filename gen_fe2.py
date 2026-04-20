M = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
lines = open(M, 'r', encoding='utf-8').readlines()
print(f"Total lines: {len(lines)}")

# Find PLANS TAB start (line index 807)
plans_start = None
plans_end = None
for i, l in enumerate(lines):
    if "PLANS TAB" in l:
        plans_start = i
    if plans_start and i > plans_start and l.strip().startswith(');') and 'return' not in l:
        # This is the closing ");  }" of the component
        pass

# Safer: find from PLANS TAB to end of file before ");\n}"
for i in range(len(lines)-1, plans_start or 0, -1):
    if lines[i].strip() == '};' or lines[i].strip() == '}':
        plans_end = i + 1
        break

# Actually let me just find the exact range
# Plans tab starts at line 807 (index 807)
# Component ends at line 866 (index 866) with "}"
# I want to replace from line 807 to line 866 (inclusive)
plans_start = 807
comp_end = None
for i in range(len(lines)-1, -1, -1):
    if lines[i].strip() == '}':
        comp_end = i
        break

print(f"Plans tab starts at line {plans_start}, component ends at line {comp_end}")
print(f"Will replace lines {plans_start} to {comp_end}")

before = lines[:plans_start]

NEW_PLANS = """      {/* ======================== PLANS TAB ======================== */}
      {tab === "plans" && (
        <div style={card}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: p.text }}>\u{1F4CB} Migration Plans</div>
            <button onClick={loadPlans} style={btnOutline}>\u{1F504} Refresh</button>
          </div>

          {loadingPlans ? <LoadDots p={p} /> : plans.length === 0 ? (
            <div style={{ textAlign: "center", padding: 60, color: p.textMute }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>\u{1F4E6}</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>No migration plans yet</div>
              <div style={{ fontSize: 12 }}>Create your first plan using the "New Migration" tab.</div>
            </div>
          ) : (
            <div style={{ borderRadius: 10, border: `1px solid ${p.border}`, overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead><tr>
                  <th style={thStyle}>Plan Name</th>
                  <th style={thStyle}>Source</th>
                  <th style={thStyle}>Target</th>
                  <th style={thStyle}>VMs</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Progress</th>
                  <th style={thStyle}>Created</th>
                  <th style={thStyle}>Actions</th>
                </tr></thead>
                <tbody>
                  {plans.map(plan => {
                    const sCfg = STATUS_CFG[plan.status] || STATUS_CFG.planned;
                    const isLive = pollingPlan === plan.id;
                    const pProgress = isLive ? liveProgress : (plan.progress || 0);
                    const actions = getActions(plan);
                    return (
                    <Fragment key={plan.id}>
                      <tr style={{ background: expandedPlan === plan.id ? `${p.accent}08` : "transparent", cursor: "pointer", transition: "background .2s" }}
                          onClick={() => { setExpandedPlan(expandedPlan === plan.id ? null : plan.id); if (["executing","migrating","validating"].includes(plan.status)) setPollingPlan(plan.id); }}>
                        <td style={{ ...tdStyle, fontWeight: 700 }}>{plan.plan_name}</td>
                        <td style={tdStyle}>VMware</td>
                        <td style={tdStyle}><span style={badge(TARGETS.find(t => t.id === plan.target_platform)?.color || p.grey)}>{TARGETS.find(t => t.id === plan.target_platform)?.label || plan.target_platform}</span></td>
                        <td style={tdStyle}>{Array.isArray(plan.vm_list) ? plan.vm_list.length : "-"}</td>
                        <td style={tdStyle}><span style={badge(sCfg.color)}>{sCfg.icon} {sCfg.label}</span></td>
                        <td style={tdStyle}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 80 }}>
                            <div style={{ flex: 1, height: 6, borderRadius: 3, background: `${p.textMute}22` }}>
                              <div style={{ height: "100%", borderRadius: 3, background: sCfg.color, width: `${pProgress}%`, transition: "width .5s ease" }} />
                            </div>
                            <span style={{ fontSize: 10, color: p.textMute, fontWeight: 700, minWidth: 28 }}>{pProgress}%</span>
                          </div>
                        </td>
                        <td style={{ ...tdStyle, fontSize: 11 }}>{plan.created_at || "-"}</td>
                        <td style={tdStyle} onClick={e => e.stopPropagation()}>
                          <button onClick={() => delPlan(plan.id)} style={{ background: "transparent", border: "none", cursor: "pointer", color: p.red, fontWeight: 700, fontSize: 11 }}>\u{1F5D1}\uFE0F</button>
                        </td>
                      </tr>

                      {expandedPlan === plan.id && (
                        <tr><td colSpan={8} style={{ padding: 0, background: p.panelAlt, borderBottom: `1px solid ${p.border}` }}>
                          <div style={{ padding: "16px 20px" }}>

                            {/* Status Pipeline */}
                            <div style={{ display: "flex", alignItems: "center", margin: "0 0 16px", padding: "12px 16px", background: p.surface, borderRadius: 10, border: `1px solid ${p.border}` }}>
                              {PIPELINE.map((stg, i) => {
                                const sc = STATUS_CFG[stg];
                                const currentOrd = STATUS_CFG[plan.status]?.ord ?? -1;
                                const isReached = currentOrd >= sc.ord && currentOrd >= 0;
                                const isCurrent = plan.status === stg || (stg === "preflight_passed" && plan.status === "preflight_running");
                                return <Fragment key={stg}>
                                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
                                    <div style={{
                                      width: 30, height: 30, borderRadius: "50%",
                                      background: isReached ? sc.color : `${p.textMute}22`,
                                      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13,
                                      border: isCurrent ? `2.5px solid ${sc.color}` : "2.5px solid transparent",
                                      boxShadow: isCurrent ? `0 0 12px ${sc.color}44` : "none",
                                      transition: "all .3s",
                                      animation: isCurrent && ["executing","migrating","validating","preflight_running"].includes(plan.status) ? "pulse 2s infinite" : "none",
                                    }}>{sc.icon}</div>
                                    <div style={{ fontSize: 8, marginTop: 3, color: isReached ? sc.color : p.textMute, fontWeight: isCurrent ? 800 : 400, textAlign: "center" }}>{sc.label}</div>
                                  </div>
                                  {i < PIPELINE.length - 1 && (
                                    <div style={{ flex: 1.5, height: 3, borderRadius: 2, background: currentOrd > sc.ord && currentOrd >= 0 ? STATUS_CFG[PIPELINE[i+1]]?.color || p.textMute : `${p.textMute}22`, transition: "background .5s", marginBottom: 16 }} />
                                  )}
                                </Fragment>;
                              })}
                              {["failed","cancelled","rolled_back","preflight_failed"].includes(plan.status) && (
                                <div style={{ marginLeft: 8, display: "flex", flexDirection: "column", alignItems: "center" }}>
                                  <div style={{ width: 30, height: 30, borderRadius: "50%", background: sCfg.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, border: `2.5px solid ${sCfg.color}`, boxShadow: `0 0 12px ${sCfg.color}44` }}>{sCfg.icon}</div>
                                  <div style={{ fontSize: 8, marginTop: 3, color: sCfg.color, fontWeight: 800 }}>{sCfg.label}</div>
                                </div>
                              )}
                            </div>

                            {/* Info */}
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, fontSize: 12, color: p.text, marginBottom: 14 }}>
                              <div><b>Migration Tool:</b> {plan.migration_tool || "-"}</div>
                              <div><b>Created By:</b> {plan.created_by || "-"}</div>
                              <div><b>Created:</b> {plan.created_at || "-"}</div>
                              {plan.approved_by && <div><b>Approved By:</b> {plan.approved_by} @ {plan.approved_at}</div>}
                              {plan.started_at && <div><b>Started:</b> {plan.started_at}</div>}
                              {plan.completed_at && <div><b>Completed:</b> {plan.completed_at}</div>}
                            </div>

                            {/* VMs */}
                            {Array.isArray(plan.vm_list) && plan.vm_list.length > 0 && (
                              <div style={{ marginBottom: 14 }}>
                                <div style={{ fontSize: 11, fontWeight: 700, color: p.textMute, marginBottom: 6, textTransform: "uppercase", letterSpacing: ".5px" }}>VMs in this plan</div>
                                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                                  {plan.vm_list.map((vm, vi) => (
                                    <div key={vi} style={{ padding: "4px 10px", borderRadius: 6, background: `${p.border}22`, fontSize: 11, fontWeight: 600 }}>{vm.name || vm}</div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Live Progress */}
                            {["executing","migrating","validating"].includes(plan.status) && (
                              <div style={{ marginBottom: 14, padding: 12, borderRadius: 8, background: `${sCfg.color}08`, border: `1px solid ${sCfg.color}25` }}>
                                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontWeight: 700, marginBottom: 6 }}>
                                  <span style={{ color: sCfg.color }}>{sCfg.icon} {sCfg.label}</span>
                                  <span style={{ color: p.textMute }}>{pProgress}% complete</span>
                                </div>
                                <div style={{ height: 10, borderRadius: 5, background: `${p.textMute}15` }}>
                                  <div style={{ height: "100%", borderRadius: 5, background: `linear-gradient(90deg, ${sCfg.color}, ${sCfg.color}cc)`, width: `${pProgress}%`, transition: "width 1s ease", boxShadow: `0 0 8px ${sCfg.color}40` }} />
                                </div>
                              </div>
                            )}

                            {/* Actions */}
                            {actions.length > 0 && (
                              <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
                                {actions.map((act, ai) => (
                                  <button key={ai}
                                    onClick={() => act.confirm ? (confirm("Are you sure?") && act.fn()) : act.fn()}
                                    style={{ padding: "7px 16px", borderRadius: 7, border: `1px solid ${act.color}`, background: `${act.color}12`, color: act.color, fontWeight: 700, fontSize: 11.5, cursor: "pointer", transition: "all .15s" }}
                                    onMouseEnter={e => { e.target.style.background = act.color; e.target.style.color = "#fff"; }}
                                    onMouseLeave={e => { e.target.style.background = `${act.color}12`; e.target.style.color = act.color; }}
                                  >{act.label}</button>
                                ))}
                              </div>
                            )}

                            {/* Event Log */}
                            {(() => {
                              const events = (pollingPlan === plan.id && liveEvents.length > 0) ? liveEvents : (plan.event_log || []);
                              if (!events.length) return null;
                              return (
                                <div style={{ borderRadius: 8, border: `1px solid ${p.border}`, overflow: "hidden" }}>
                                  <div style={{ padding: "8px 12px", background: `${p.border}33`, fontSize: 11, fontWeight: 700, color: p.text }}>\u{1F4DC} Activity Log ({events.length})</div>
                                  <div style={{ maxHeight: 200, overflowY: "auto", padding: "6px 0" }} ref={el => { if (el) el.scrollTop = el.scrollHeight; }}>
                                    {events.map((ev, ei) => (
                                      <div key={ei} style={{ padding: "3px 12px", fontSize: 10.5, color: p.textSub, display: "flex", gap: 8, borderBottom: `1px solid ${p.border}08` }}>
                                        <span style={{ color: p.textMute, fontFamily: "monospace", whiteSpace: "nowrap", minWidth: 130 }}>{ev.ts}</span>
                                        <span style={{ color: ev.msg?.includes("OK") || ev.msg?.includes("complete") || ev.msg?.includes("100%") ? "#22c55e" : ev.msg?.includes("fail") ? "#ef4444" : p.text }}>{ev.msg}</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              );
                            })()}

                          </div>
                        </td></tr>
                      )}
                    </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <style>{`
        @keyframes pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.15); opacity: 0.85; } }
        @keyframes ldDot { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}
"""

result = "".join(before) + NEW_PLANS
open(M, 'w', encoding='utf-8').write(result)
print(f"Plans tab replaced. New file: {len(result)} chars, {result.count(chr(10))} lines")