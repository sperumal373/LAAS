f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()
Q = b'\x22'

if b'fetchMoveGroups' in raw:
    print('Already patched')
    exit()

# 1. Add imports
old_import = b'} from ' + Q + b'./api' + Q + b';'
new_import = (
    b'  fetchMoveGroups, createMoveGroup, deleteMoveGroup, addVMsToGroup, removeVMFromGroup, migrateGroup,\r\n'
    b'} from ' + Q + b'./api' + Q + b';'
)
raw = raw.replace(old_import, new_import, 1)
print('1. Imports added')

# 2. Add state for move groups after existing state declarations
# Find "const [tab, setTab]" and add states after plans state section
state_marker = b'const [saving, setSaving] = useState(false);'
mg_state = (
    b'const [saving, setSaving] = useState(false);\r\n'
    b'\r\n'
    b'  // Move Groups state\r\n'
    b'  const [moveGroups, setMoveGroups] = useState([]);\r\n'
    b'  const [mgLoading, setMgLoading] = useState(false);\r\n'
    b'  const [mgNewName, setMgNewName] = useState(' + Q + Q + b');\r\n'
    b'  const [mgSelGroup, setMgSelGroup] = useState(null);\r\n'
    b'  const [mgAddVC, setMgAddVC] = useState(' + Q + Q + b');\r\n'
    b'  const [mgVMs, setMgVMs] = useState([]);\r\n'
    b'  const [mgVMSearch, setMgVMSearch] = useState(' + Q + Q + b');\r\n'
    b'  const [mgSelVMs, setMgSelVMs] = useState({});\r\n'
    b'  const [mgLoadingVMs, setMgLoadingVMs] = useState(false);\r\n'
    b'  const [mgMigrateTarget, setMgMigrateTarget] = useState(' + Q + Q + b');\r\n'
    b'  const [mgTargetDetail, setMgTargetDetail] = useState({});\r\n'
    b'  const [mgMigrating, setMgMigrating] = useState(false);'
)
raw = raw.replace(state_marker, mg_state, 1)
print('2. State added')

# 3. Add loadMoveGroups function - find "useEffect(() => { if (tab === plans)" and add before it
load_marker = b'useEffect(() => { if (tab === ' + Q + b'plans' + Q + b') loadPlans(); }, [tab]);'
mg_load = (
    b'const loadMoveGroups = async () => { setMgLoading(true); try { const g = await fetchMoveGroups(); setMoveGroups(g); } catch {} setMgLoading(false); };\r\n'
    b'  const mgLoadVMs = async (vcId) => { if (!vcId) return; setMgLoadingVMs(true); try { const v = await fetchVMs(vcId); setMgVMs(v); } catch {} setMgLoadingVMs(false); };\r\n'
    b'  const mgCreateGroup = async () => { if (!mgNewName.trim()) return; try { await createMoveGroup({ name: mgNewName.trim() }); setMgNewName(' + Q + Q + b'); loadMoveGroups(); showToast(' + Q + b'Move group created!' + Q + b', ' + Q + b'ok' + Q + b'); } catch(e) { showToast(e.message, ' + Q + b'error' + Q + b'); } };\r\n'
    b'  const mgDeleteGroup = async (id) => { if (!confirm(' + Q + b'Delete this move group?' + Q + b')) return; try { await deleteMoveGroup(id); if (mgSelGroup?.id === id) setMgSelGroup(null); loadMoveGroups(); } catch {} };\r\n'
    b'  const mgAddVMs = async () => { if (!mgSelGroup) return; const vms = mgVMs.filter(v => mgSelVMs[v.name]); if (!vms.length) return; const vc = vcenters.find(v => String(v.id) === String(mgAddVC)); try { await addVMsToGroup(mgSelGroup.id, { vms: vms.map(v => ({ name: v.name, moref: v.moref || ' + Q + Q + b', guest_os: v.guest_os || ' + Q + Q + b', cpu: v.cpu || 0, memory_mb: v.memory_mb || 0, disk_gb: v.disk_gb || 0, power_state: v.power_state || ' + Q + Q + b', ip_address: v.ip_address || ' + Q + Q + b', esxi_host: v.esxi_host || ' + Q + Q + b' })), vcenter_id: String(mgAddVC), vcenter_name: vc?.name || vc?.host || ' + Q + Q + b' }); setMgSelVMs({}); loadMoveGroups(); showToast(vms.length + ' + Q + b' VM(s) added!' + Q + b', ' + Q + b'ok' + Q + b'); } catch(e) { showToast(e.message, ' + Q + b'error' + Q + b'); } };\r\n'
    b'  const mgRemoveVM = async (gid, vid) => { try { await removeVMFromGroup(gid, vid); loadMoveGroups(); } catch {} };\r\n'
    b'  const mgDoMigrate = async () => { if (!mgSelGroup || !mgMigrateTarget) return; setMgMigrating(true); try { const r = await migrateGroup(mgSelGroup.id, { target_platform: mgMigrateTarget, target_detail: mgTargetDetail }); showToast(r.plans_created + ' + Q + b' plan(s) created! Check Plans tab.' + Q + b', ' + Q + b'ok' + Q + b'); setTab(' + Q + b'plans' + Q + b'); loadPlans(); } catch(e) { showToast(e.message, ' + Q + b'error' + Q + b'); } setMgMigrating(false); };\r\n'
    b'  useEffect(() => { if (tab === ' + Q + b'groups' + Q + b') { loadMoveGroups(); if (!vcenters.length) fetchVCenters().then(v => setVcenters(v)).catch(() => {}); } }, [tab]);\r\n'
    b'  useEffect(() => { if (mgAddVC) mgLoadVMs(mgAddVC); }, [mgAddVC]);\r\n'
    b'  useEffect(() => { if (mgSelGroup && moveGroups.length) { const g = moveGroups.find(x => x.id === mgSelGroup.id); if (g) setMgSelGroup(g); } }, [moveGroups]);\r\n'
    b'  ' + load_marker
)
raw = raw.replace(load_marker, mg_load, 1)
print('3. Functions added')

# 4. Add "groups" tab button
old_tabs = b'[["new", ' + Q + b'\xe2\x9c\xa8 New Migration' + Q + b'], ["plans", ' + Q + b'\xf0\x9f\x93\x8b Plans' + Q + b']]'
new_tabs = b'[["new", ' + Q + b'\xe2\x9c\xa8 New Migration' + Q + b'], ["groups", ' + Q + b'\xf0\x9f\x93\xa6 Move Groups' + Q + b'], ["plans", ' + Q + b'\xf0\x9f\x93\x8b Plans' + Q + b']]'
raw = raw.replace(old_tabs, new_tabs, 1)
print('4. Tab button added')

# 5. Insert Move Groups tab content - before the plans tab
plans_tab_marker = b'      {/* ======================== PLANS TAB ======================== */}'
mg_tab_jsx = b'''      {/* ======================== MOVE GROUPS TAB ======================== */}
      {tab === "groups" && (
        <div style={{ display: "flex", gap: 18, minHeight: 500 }}>
          {/* Left: Groups list */}
          <div style={{ width: 300, flexShrink: 0 }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
              <input value={mgNewName} onChange={e => setMgNewName(e.target.value)} placeholder="Group name..."
                style={{ flex: 1, padding: "8px 12px", borderRadius: 8, border: `1px solid ${p.border}`, background: p.surface, color: p.text, fontSize: 13 }}
                onKeyDown={e => e.key === "Enter" && mgCreateGroup()} />
              <button onClick={mgCreateGroup} disabled={!mgNewName.trim()}
                style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: p.accent, color: "#fff", fontWeight: 700, fontSize: 12, cursor: "pointer", opacity: mgNewName.trim() ? 1 : 0.5 }}>+ Create</button>
            </div>
            {mgLoading ? <LoadDots p={p} /> : moveGroups.length === 0 ? (
              <div style={{ textAlign: "center", padding: 40, color: p.textMute, fontSize: 13 }}>No move groups yet. Create one above.</div>
            ) : moveGroups.map(g => (
              <div key={g.id} onClick={() => setMgSelGroup(g)}
                style={{ padding: "12px 14px", marginBottom: 8, borderRadius: 10, cursor: "pointer",
                  background: mgSelGroup?.id === g.id ? `${p.accent}18` : p.surface,
                  border: `1.5px solid ${mgSelGroup?.id === g.id ? p.accent : p.border}`,
                  transition: "all .2s" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontWeight: 700, fontSize: 13.5, color: p.text }}>{g.name}</div>
                  <button onClick={e => { e.stopPropagation(); mgDeleteGroup(g.id); }}
                    style={{ background: "none", border: "none", color: p.red || "#ef4444", cursor: "pointer", fontSize: 15, padding: 2 }}>\\u2716</button>
                </div>
                <div style={{ fontSize: 11.5, color: p.textMute, marginTop: 4 }}>
                  {g.vm_count} VM{g.vm_count !== 1 ? "s" : ""} {g.vcenters?.length ? "\\u00B7 " + g.vcenters.join(", ") : ""}
                </div>
              </div>
            ))}
          </div>

          {/* Right: Group detail */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {!mgSelGroup ? (
              <div style={{ textAlign: "center", padding: 80, color: p.textMute, fontSize: 14 }}>
                \\u2190 Select or create a move group
              </div>
            ) : (<>
              <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 14 }}>
                <div style={{ fontWeight: 800, fontSize: 18, color: p.text }}>{mgSelGroup.name}</div>
                <span style={{ fontSize: 12, color: p.textMute, background: p.surface, padding: "3px 10px", borderRadius: 6, fontWeight: 600 }}>
                  {mgSelGroup.vm_count || 0} VMs
                </span>
              </div>

              {/* Add VMs section */}
              <div style={{ padding: 14, borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, marginBottom: 16 }}>
                <div style={{ fontWeight: 700, fontSize: 13, color: p.text, marginBottom: 10 }}>Add VMs from vCenter</div>
                <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
                  <select value={mgAddVC} onChange={e => { setMgAddVC(e.target.value); setMgSelVMs({}); }}
                    style={{ padding: "7px 10px", borderRadius: 8, border: `1px solid ${p.border}`, background: p.bg, color: p.text, fontSize: 12.5, minWidth: 200 }}>
                    <option value="">Select vCenter...</option>
                    {vcenters.map(v => <option key={v.id} value={v.id}>{v.name || v.host}</option>)}
                  </select>
                  <input value={mgVMSearch} onChange={e => setMgVMSearch(e.target.value)} placeholder="Search VMs..."
                    style={{ padding: "7px 10px", borderRadius: 8, border: `1px solid ${p.border}`, background: p.bg, color: p.text, fontSize: 12.5, flex: 1, minWidth: 150 }} />
                  <button onClick={mgAddVMs} disabled={!Object.values(mgSelVMs).some(Boolean)}
                    style={{ padding: "7px 16px", borderRadius: 8, border: "none", background: "#10b981", color: "#fff", fontWeight: 700, fontSize: 12, cursor: "pointer",
                      opacity: Object.values(mgSelVMs).some(Boolean) ? 1 : 0.5 }}>
                    + Add Selected
                  </button>
                </div>
                {mgAddVC && (mgLoadingVMs ? <LoadDots p={p} /> : (
                  <div style={{ maxHeight: 220, overflowY: "auto", borderRadius: 8, border: `1px solid ${p.border}` }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                      <thead><tr style={{ background: `${p.accent}10` }}>
                        <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 700, color: p.textMute }}></th>
                        <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 700, color: p.textMute }}>VM Name</th>
                        <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 700, color: p.textMute }}>Guest OS</th>
                        <th style={{ padding: "6px 8px", textAlign: "right", fontWeight: 700, color: p.textMute }}>CPU</th>
                        <th style={{ padding: "6px 8px", textAlign: "right", fontWeight: 700, color: p.textMute }}>RAM</th>
                        <th style={{ padding: "6px 8px", textAlign: "right", fontWeight: 700, color: p.textMute }}>Disk</th>
                      </tr></thead>
                      <tbody>
                        {mgVMs.filter(v => !mgVMSearch || v.name?.toLowerCase().includes(mgVMSearch.toLowerCase())).map(v => {
                          const already = (mgSelGroup.vms || []).some(gv => gv.vm_name === v.name && String(gv.vcenter_id) === String(mgAddVC));
                          return (
                            <tr key={v.name} style={{ borderBottom: `1px solid ${p.border}22`, opacity: already ? 0.4 : 1 }}>
                              <td style={{ padding: "5px 8px" }}>
                                {already ? <span title="Already in group" style={{ fontSize: 11, color: p.textMute }}>\\u2714</span> :
                                  <input type="checkbox" checked={!!mgSelVMs[v.name]} onChange={e => setMgSelVMs(prev => ({...prev, [v.name]: e.target.checked}))} />}
                              </td>
                              <td style={{ padding: "5px 8px", fontWeight: 600, color: p.text }}>{v.name}</td>
                              <td style={{ padding: "5px 8px", color: p.textMute }}>{v.guest_os || "\\u2014"}</td>
                              <td style={{ padding: "5px 8px", textAlign: "right", color: p.textMute }}>{v.cpu || "\\u2014"}</td>
                              <td style={{ padding: "5px 8px", textAlign: "right", color: p.textMute }}>{v.memory_mb ? (v.memory_mb/1024).toFixed(1) + " GB" : "\\u2014"}</td>
                              <td style={{ padding: "5px 8px", textAlign: "right", color: p.textMute }}>{v.disk_gb ? v.disk_gb.toFixed(1) + " GB" : "\\u2014"}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ))}
              </div>

              {/* VMs in group */}
              {mgSelGroup.vms?.length > 0 && (
                <div style={{ padding: 14, borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, marginBottom: 16 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: p.text, marginBottom: 10 }}>VMs in Group ({mgSelGroup.vms.length})</div>
                  <div style={{ maxHeight: 250, overflowY: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                      <thead><tr style={{ background: `${p.accent}10` }}>
                        <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 700, color: p.textMute }}>VM Name</th>
                        <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 700, color: p.textMute }}>vCenter</th>
                        <th style={{ padding: "6px 8px", textAlign: "left", fontWeight: 700, color: p.textMute }}>Guest OS</th>
                        <th style={{ padding: "6px 8px", textAlign: "right", fontWeight: 700, color: p.textMute }}>CPU</th>
                        <th style={{ padding: "6px 8px", textAlign: "right", fontWeight: 700, color: p.textMute }}>RAM</th>
                        <th style={{ padding: "6px 8px", textAlign: "center", fontWeight: 700, color: p.textMute }}></th>
                      </tr></thead>
                      <tbody>
                        {mgSelGroup.vms.map(v => (
                          <tr key={v.id} style={{ borderBottom: `1px solid ${p.border}22` }}>
                            <td style={{ padding: "5px 8px", fontWeight: 600, color: p.text }}>{v.vm_name}</td>
                            <td style={{ padding: "5px 8px", color: p.textMute, fontSize: 11 }}>{v.vcenter_name || v.vcenter_id}</td>
                            <td style={{ padding: "5px 8px", color: p.textMute }}>{v.guest_os || "\\u2014"}</td>
                            <td style={{ padding: "5px 8px", textAlign: "right", color: p.textMute }}>{v.cpu || "\\u2014"}</td>
                            <td style={{ padding: "5px 8px", textAlign: "right", color: p.textMute }}>{v.memory_mb ? (v.memory_mb/1024).toFixed(1) + " GB" : "\\u2014"}</td>
                            <td style={{ padding: "5px 8px", textAlign: "center" }}>
                              <button onClick={() => mgRemoveVM(mgSelGroup.id, v.id)}
                                style={{ background: "none", border: "none", color: p.red || "#ef4444", cursor: "pointer", fontSize: 13 }}>\\u2716</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Migrate section */}
              {mgSelGroup.vms?.length > 0 && (
                <div style={{ padding: 14, borderRadius: 10, background: `${p.accent}08`, border: `1.5px solid ${p.accent}30`, marginBottom: 16 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: p.text, marginBottom: 10 }}>Migrate This Group</div>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                    <select value={mgMigrateTarget} onChange={e => setMgMigrateTarget(e.target.value)}
                      style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${p.border}`, background: p.bg, color: p.text, fontSize: 12.5, minWidth: 200 }}>
                      <option value="">Select target platform...</option>
                      <option value="openshift">Red Hat OpenShift</option>
                      <option value="nutanix">Nutanix AHV</option>
                      <option value="hyperv">Microsoft Hyper-V</option>
                    </select>
                    <button onClick={mgDoMigrate} disabled={!mgMigrateTarget || mgMigrating}
                      style={{ padding: "8px 24px", borderRadius: 8, border: "none", fontWeight: 700, fontSize: 13, cursor: "pointer",
                        background: mgMigrateTarget ? "linear-gradient(135deg, #f59e0b, #f97316)" : p.border,
                        color: mgMigrateTarget ? "#fff" : p.textMute, transition: "all .2s",
                        opacity: mgMigrateTarget && !mgMigrating ? 1 : 0.6 }}>
                      {mgMigrating ? "Creating plans..." : "\\u{1F680} Create Migration Plans"}
                    </button>
                  </div>
                  {mgMigrateTarget && mgSelGroup.vcenters?.length > 1 && (
                    <div style={{ marginTop: 8, fontSize: 11.5, color: p.textMute, fontStyle: "italic" }}>
                      This group spans {mgSelGroup.vcenters.length} vCenters. One plan per vCenter will be auto-created.
                    </div>
                  )}
                </div>
              )}
            </>)}
          </div>
        </div>
      )}

'''
raw = raw.replace(plans_tab_marker, mg_tab_jsx.encode('utf-8').replace(b'\n', b'\r\n') + b'      ' + plans_tab_marker, 1)
print('5. Move Groups tab UI added')

open(f, 'wb').write(raw)
print('Frontend done! Size:', len(raw))