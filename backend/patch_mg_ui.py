"""Add Move Groups UI to MigrationPage.jsx"""
f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()
q = b'\x22'

if b'Move Groups' in raw and b'tab === ' + q + b'groups' + q in raw:
    print('Move Groups UI already exists')
    exit()

# 1. Add imports
old_imp = b'fetchMigrationPlans, createMigrationPlan, deleteMigrationPlan, updatePlanStatus, executeMigrationPlan, fetchPlanEvents, runPreflightCheck,\r\n} from ' + q + b'./api' + q + b';'
new_imp = b'fetchMigrationPlans, createMigrationPlan, deleteMigrationPlan, updatePlanStatus, executeMigrationPlan, fetchPlanEvents, runPreflightCheck,\r\n  fetchMoveGroups, createMoveGroup, deleteMoveGroup, addVMsToGroup, removeVMFromGroup, migrateGroup,\r\n} from ' + q + b'./api' + q + b';'
assert old_imp in raw, 'Import marker not found'
raw = raw.replace(old_imp, new_imp, 1)
print('1. Imports added')

# 2. Add state variables after existing state
old_state = b'const [saving, setSaving] = useState(false);'
new_state = old_state + b'\r\n\r\n  // Move Groups state\r\n  const [moveGroups, setMoveGroups] = useState([]);\r\n  const [mgLoading, setMgLoading] = useState(false);\r\n  const [mgName, setMgName] = useState("");\r\n  const [mgExpanded, setMgExpanded] = useState(null);\r\n  const [mgAddVC, setMgAddVC] = useState("");\r\n  const [mgAddVMs, setMgAddVMs] = useState([]);\r\n  const [mgAddSel, setMgAddSel] = useState({});\r\n  const [mgAddLoading, setMgAddLoading] = useState(false);\r\n  const [mgMigrateId, setMgMigrateId] = useState(null);\r\n  const [mgTargetPlatform, setMgTargetPlatform] = useState("");'
assert old_state in raw, 'State marker not found'
raw = raw.replace(old_state, new_state, 1)
print('2. State added')

# 3. Add loadGroups function - find "useEffect(() => { if (tab" 
old_tab_effect = b'useEffect(() => { if (tab === ' + q + b'plans' + q + b') loadPlans(); }, [tab]);'
new_tab_effect = old_tab_effect + b'\r\n  useEffect(() => { if (tab === ' + q + b'groups' + q + b') loadGroups(); }, [tab]);\r\n\r\n  async function loadGroups() {\r\n    setMgLoading(true);\r\n    try { const g = await fetchMoveGroups(); setMoveGroups(g || []); } catch {}\r\n    setMgLoading(false);\r\n  }\r\n\r\n  async function handleCreateGroup() {\r\n    if (!mgName.trim()) return;\r\n    try {\r\n      await createMoveGroup(mgName.trim());\r\n      setMgName("");\r\n      loadGroups();\r\n      showToast("Move group created!", "success");\r\n    } catch (e) { showToast(e.message, "error"); }\r\n  }\r\n\r\n  async function handleDeleteGroup(gid) {\r\n    if (!confirm("Delete this move group and all its VMs?")) return;\r\n    try { await deleteMoveGroup(gid); loadGroups(); showToast("Group deleted", "success"); } catch (e) { showToast(e.message, "error"); }\r\n  }\r\n\r\n  async function handleAddVMsToGroup(gid) {\r\n    const selected = Object.entries(mgAddSel).filter(([,v]) => v).map(([k]) => mgAddVMs.find(v => v.name === k)).filter(Boolean);\r\n    if (!selected.length) return showToast("Select at least one VM", "error");\r\n    const vc = vcenters.find(v => String(v.id) === String(mgAddVC));\r\n    try {\r\n      const r = await addVMsToGroup(gid, selected, mgAddVC, vc?.name || mgAddVC);\r\n      showToast(`Added ${r.added} VM(s)`, "success");\r\n      setMgAddSel({}); loadGroups();\r\n    } catch (e) { showToast(e.message, "error"); }\r\n  }\r\n\r\n  async function handleRemoveVM(gid, vmId) {\r\n    try { await removeVMFromGroup(gid, vmId); loadGroups(); } catch (e) { showToast(e.message, "error"); }\r\n  }\r\n\r\n  async function handleMigrateGroup(gid) {\r\n    if (!mgTargetPlatform) return showToast("Select a target platform", "error");\r\n    try {\r\n      const r = await migrateGroup(gid, mgTargetPlatform, {});\r\n      showToast(`Created ${r.plans_created} migration plan(s)! Go to Plans tab.`, "success");\r\n      setMgMigrateId(null); setMgTargetPlatform("");\r\n      loadGroups();\r\n    } catch (e) { showToast(e.message, "error"); }\r\n  }\r\n\r\n  async function loadVMsForGroup(vcId) {\r\n    setMgAddLoading(true); setMgAddVMs([]); setMgAddSel({});\r\n    try {\r\n      const vc = vcenters.find(v => String(v.id) === String(vcId));\r\n      if (vc) {\r\n        const data = await fetchVMs(vc.id);\r\n        setMgAddVMs(data || []);\r\n      }\r\n    } catch {}\r\n    setMgAddLoading(false);\r\n  }'
assert old_tab_effect in raw, 'Tab effect marker not found'
raw = raw.replace(old_tab_effect, new_tab_effect, 1)
print('3. Functions added')

# 4. Add "Groups" tab button
old_tabs = b'[["new", ' + q + b'\xe2\x9c\xa8 New Migration' + q + b'], ["plans", ' + q + b'\xf0\x9f\x93\x8b Plans' + q + b']]'
new_tabs = b'[["new", ' + q + b'\xe2\x9c\xa8 New Migration' + q + b'], ["groups", ' + q + b'\xf0\x9f\x93\xa6 Move Groups' + q + b'], ["plans", ' + q + b'\xf0\x9f\x93\x8b Plans' + q + b']]'
assert old_tabs in raw, 'Tabs marker not found'
raw = raw.replace(old_tabs, new_tabs, 1)
print('4. Tab button added')

# 5. Insert groups tab content before plans tab
plans_marker = b'      {/* ======================== PLANS TAB ======================== */}'
assert plans_marker in raw, 'Plans tab marker not found'

groups_jsx = b'''      {/* ======================== MOVE GROUPS TAB ======================== */}
      {tab === "groups" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {/* Create new group */}
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <input value={mgName} onChange={e => setMgName(e.target.value)} placeholder="New group name..."
              style={{ flex: 1, padding: "10px 14px", borderRadius: 8, border: `1px solid ${p.border}`, background: p.surface, color: p.text, fontSize: 13 }}
              onKeyDown={e => e.key === "Enter" && handleCreateGroup()} />
            <button onClick={handleCreateGroup} disabled={!mgName.trim()}
              style={{ padding: "10px 22px", borderRadius: 8, border: "none", background: p.accent, color: "#fff", fontWeight: 700, fontSize: 13, cursor: "pointer", opacity: mgName.trim() ? 1 : 0.5 }}>
              + Create Group
            </button>
          </div>

          {mgLoading ? <LoadDots p={p} /> : moveGroups.length === 0 ? (
            <div style={{ textAlign: "center", padding: 60, color: p.textMute, fontSize: 14 }}>
              No move groups yet. Create one above to batch VMs for migration.
            </div>
          ) : moveGroups.map(g => {
            const isExp = mgExpanded === g.id;
            const isMigrating = mgMigrateId === g.id;
            return (
              <div key={g.id} style={{ background: p.surface, borderRadius: 12, border: `1px solid ${isExp ? p.accent : p.border}`, overflow: "hidden", transition: "all .2s" }}>
                {/* Group header */}
                <div onClick={() => setMgExpanded(isExp ? null : g.id)} style={{ display: "flex", alignItems: "center", padding: "14px 18px", cursor: "pointer", gap: 12 }}>
                  <span style={{ fontSize: 20 }}>{isExp ? "\\u25BC" : "\\u25B6"}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 15, color: p.text }}>{g.name}</div>
                    <div style={{ fontSize: 11.5, color: p.textMute, marginTop: 2 }}>
                      {g.vm_count} VM(s) \\u00B7 {(g.vcenters || []).join(", ") || "No vCenters"} \\u00B7 Created {g.created_at?.slice(0,16)}
                    </div>
                  </div>
                  <button onClick={e => { e.stopPropagation(); setMgMigrateId(isMigrating ? null : g.id); }} disabled={!g.vm_count}
                    style={{ padding: "7px 16px", borderRadius: 7, border: "none", background: g.vm_count ? "#10b981" : p.border, color: "#fff", fontWeight: 700, fontSize: 12, cursor: g.vm_count ? "pointer" : "default", opacity: g.vm_count ? 1 : 0.5 }}>
                    \\u{1F680} Migrate
                  </button>
                  <button onClick={e => { e.stopPropagation(); handleDeleteGroup(g.id); }}
                    style={{ padding: "7px 12px", borderRadius: 7, border: "none", background: "#ef4444", color: "#fff", fontWeight: 700, fontSize: 12, cursor: "pointer" }}>
                    \\u{1F5D1}
                  </button>
                </div>

                {/* Migrate panel */}
                {isMigrating && (
                  <div style={{ padding: "12px 18px", background: `${p.accent}08`, borderTop: `1px solid ${p.border}`, display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: p.text }}>Target:</span>
                    {TARGETS.map(t => (
                      <button key={t.id} onClick={() => setMgTargetPlatform(t.id)}
                        style={{ padding: "6px 14px", borderRadius: 7, border: mgTargetPlatform === t.id ? `2px solid ${t.color}` : `1px solid ${p.border}`,
                          background: mgTargetPlatform === t.id ? `${t.color}15` : p.surface, color: mgTargetPlatform === t.id ? t.color : p.textMute,
                          fontWeight: 700, fontSize: 12, cursor: "pointer" }}>
                        {t.icon} {t.label}
                      </button>
                    ))}
                    <button onClick={() => handleMigrateGroup(g.id)} disabled={!mgTargetPlatform}
                      style={{ marginLeft: "auto", padding: "7px 20px", borderRadius: 7, border: "none", background: mgTargetPlatform ? "#10b981" : p.border, color: "#fff", fontWeight: 700, fontSize: 12, cursor: mgTargetPlatform ? "pointer" : "default" }}>
                      Create Plan(s) \\u2192
                    </button>
                  </div>
                )}

                {/* Expanded: VM list + Add VMs */}
                {isExp && (
                  <div style={{ padding: "0 18px 16px", borderTop: `1px solid ${p.border}` }}>
                    {/* Existing VMs in group */}
                    {(g.vms || []).length > 0 && (
                      <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 12, fontSize: 12.5 }}>
                        <thead><tr style={{ color: p.textMute, textAlign: "left", borderBottom: `1px solid ${p.border}` }}>
                          <th style={{ padding: "6px 8px" }}>VM</th>
                          <th>vCenter</th><th>OS</th><th>CPU</th><th>Mem</th><th>Disk</th><th>Power</th><th></th>
                        </tr></thead>
                        <tbody>
                          {g.vms.map(vm => (
                            <tr key={vm.id} style={{ borderBottom: `1px solid ${p.border}22` }}>
                              <td style={{ padding: "6px 8px", fontWeight: 600, color: p.text }}>{vm.vm_name}</td>
                              <td style={{ color: p.textMute }}>{vm.vcenter_name || vm.vcenter_id}</td>
                              <td style={{ color: p.textMute }}>{vm.guest_os || "\\u2014"}</td>
                              <td>{vm.cpu || "\\u2014"}</td>
                              <td>{vm.memory_mb ? `${(vm.memory_mb/1024).toFixed(1)} GB` : "\\u2014"}</td>
                              <td>{vm.disk_gb ? `${vm.disk_gb.toFixed(1)} GB` : "\\u2014"}</td>
                              <td><span style={{ color: vm.power_state === "poweredOn" ? "#10b981" : "#f59e0b", fontWeight: 600 }}>{vm.power_state === "poweredOn" ? "\\u{1F7E2}" : "\\u{1F7E1}"}</span></td>
                              <td><button onClick={() => handleRemoveVM(g.id, vm.id)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontWeight: 700, fontSize: 14 }}>\\u00D7</button></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}

                    {/* Add VMs from vCenter */}
                    <div style={{ marginTop: 14, padding: 14, borderRadius: 8, background: `${p.bg}`, border: `1px dashed ${p.border}` }}>
                      <div style={{ fontSize: 12.5, fontWeight: 700, color: p.text, marginBottom: 8 }}>Add VMs from vCenter</div>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
                        <select value={mgAddVC} onChange={e => { setMgAddVC(e.target.value); if (e.target.value) loadVMsForGroup(e.target.value); else { setMgAddVMs([]); setMgAddSel({}); } }}
                          style={{ padding: "8px 12px", borderRadius: 7, border: `1px solid ${p.border}`, background: p.surface, color: p.text, fontSize: 12.5, minWidth: 200 }}>
                          <option value="">Select vCenter...</option>
                          {vcenters.map(vc => <option key={vc.id} value={vc.id}>{vc.name || vc.host}</option>)}
                        </select>
                        {mgAddVC && (
                          <button onClick={() => handleAddVMsToGroup(g.id)} disabled={!Object.values(mgAddSel).some(Boolean)}
                            style={{ padding: "7px 16px", borderRadius: 7, border: "none", background: Object.values(mgAddSel).some(Boolean) ? p.accent : p.border, color: "#fff", fontWeight: 700, fontSize: 12, cursor: "pointer" }}>
                            + Add Selected
                          </button>
                        )}
                      </div>
                      {mgAddLoading ? <LoadDots p={p} /> : mgAddVMs.length > 0 && (
                        <div style={{ maxHeight: 250, overflow: "auto", borderRadius: 6, border: `1px solid ${p.border}` }}>
                          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                            <thead><tr style={{ color: p.textMute, background: p.surface, position: "sticky", top: 0, textAlign: "left" }}>
                              <th style={{ padding: "6px 8px", width: 30 }}><input type="checkbox" onChange={e => { const o = {}; mgAddVMs.forEach(v => o[v.name] = e.target.checked); setMgAddSel(o); }} /></th>
                              <th>VM Name</th><th>OS</th><th>CPU</th><th>Mem</th><th>Power</th>
                            </tr></thead>
                            <tbody>
                              {mgAddVMs.map(vm => (
                                <tr key={vm.name} style={{ borderBottom: `1px solid ${p.border}22`, background: mgAddSel[vm.name] ? `${p.accent}10` : "transparent" }}>
                                  <td style={{ padding: "5px 8px" }}><input type="checkbox" checked={!!mgAddSel[vm.name]} onChange={e => setMgAddSel(s => ({...s, [vm.name]: e.target.checked}))} /></td>
                                  <td style={{ fontWeight: 600, color: p.text }}>{vm.name}</td>
                                  <td style={{ color: p.textMute }}>{vm.guest_os || "\\u2014"}</td>
                                  <td>{vm.cpu || "\\u2014"}</td>
                                  <td>{vm.memory_mb ? `${(vm.memory_mb/1024).toFixed(1)} GB` : "\\u2014"}</td>
                                  <td><span style={{ color: vm.power_state === "poweredOn" ? "#10b981" : "#f59e0b" }}>{vm.power_state === "poweredOn" ? "\\u{1F7E2}" : "\\u{1F7E1}"}</span></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

'''

# Normalize CRLF
groups_jsx = groups_jsx.replace(b'\n', b'\r\n')
raw = raw.replace(plans_marker, groups_jsx.rstrip() + b'\r\n\r\n' + plans_marker, 1)
print('5. Move Groups tab UI added')

open(f, 'wb').write(raw)
print('Done! Size:', len(raw))