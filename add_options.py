"""Add migration options, schedule, visibility fixes, admin-only approve."""
M = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
d = open(M, "r", encoding="utf-8").read()

# ========== 1. Add new state variables after Step 5 state ==========
old_state = '''  // Step 5 state
  const [planName, setPlanName] = useState("");
  const [saving, setSaving] = useState(false);'''

new_state = '''  // Step 5 state
  const [planName, setPlanName] = useState("");
  const [saving, setSaving] = useState(false);

  // Migration Options state
  const [migWarm, setMigWarm] = useState(false);
  const [migPowerOn, setMigPowerOn] = useState(true);
  const [migKeepSource, setMigKeepSource] = useState(true);
  const [migDecomSource, setMigDecomSource] = useState(false);
  const [migSkipConvert, setMigSkipConvert] = useState(false);
  const [migPreserveIPs, setMigPreserveIPs] = useState(false);
  const [migPreflight, setMigPreflight] = useState(true);
  const [migTargetNS, setMigTargetNS] = useState("openshift-mtv");
  const [migNotes, setMigNotes] = useState("");
  const [migSchedule, setMigSchedule] = useState("");'''
d = d.replace(old_state, new_state)

# ========== 2. Add options to createMigrationPlan payload ==========
old_payload = '''        migration_tool: tool,
        status: "planned",
      });'''

new_payload = '''        migration_tool: tool,
        status: "planned",
        options: {
          warm: migWarm,
          power_on_target: migPowerOn,
          keep_source: migKeepSource,
          decommission_source: migDecomSource,
          skip_guest_conversion: migSkipConvert,
          preserve_static_ips: migPreserveIPs,
          run_preflight: migPreflight,
          target_namespace: migTargetNS,
          schedule: migSchedule || null,
        },
        notes: migNotes,
      });'''
d = d.replace(old_payload, new_payload)

# ========== 3. Reset options on wizard reset ==========
old_reset = '''      setPreflightResults(null); setNetworkMap([]); setStorageMap([]); setPlanName("");'''
new_reset = '''      setPreflightResults(null); setNetworkMap([]); setStorageMap([]); setPlanName("");
      setMigWarm(false); setMigPowerOn(true); setMigKeepSource(true); setMigDecomSource(false);
      setMigSkipConvert(false); setMigPreserveIPs(false); setMigPreflight(true);
      setMigTargetNS("openshift-mtv"); setMigNotes(""); setMigSchedule("");'''
d = d.replace(old_reset, new_reset)

# ========== 4. Fix Approve to be admin-only + add schedule modal ==========
old_approve = '''      acts.push({ label: "\\u{1F44D} Approve & Schedule", color: "#8b5cf6", fn: () => doUpdateStatus(plan.id, "approved") });'''
new_approve = '''      if (currentUser?.role === "admin") {
        acts.push({ label: "\\u{1F44D} Approve", color: "#8b5cf6", fn: () => {
          const sched = prompt("Schedule execution (leave blank for manual):\\nFormat: YYYY-MM-DD HH:MM", "");
          doUpdateStatus(plan.id, "approved", sched ? "Scheduled: " + sched : "");
        }});
      } else {
        acts.push({ label: "\\u{1F512} Awaiting Admin Approval", color: "#6b7280", fn: () => showToast("Only admins can approve migration plans", "error") });
      }'''
d = d.replace(old_approve, new_approve)

# ========== 5. Add Retry button for failed, Rollback for completed ==========
old_failed = '''    } else if (["failed","cancelled","rolled_back"].includes(s)) {
      acts.push({ label: "\\u21A9 Reset to Planned", color: "#5b8def", fn: () => doUpdateStatus(plan.id, "planned") });
    }'''
new_failed = '''    } else if (s === "failed") {
      acts.push({ label: "\\u{1F504} Retry Migration", color: "#f59e0b", fn: () => doUpdateStatus(plan.id, "approved").then(() => { setTimeout(() => startExecution(plan.id), 500); }) });
      acts.push({ label: "\\u21A9 Reset to Planned", color: "#5b8def", fn: () => doUpdateStatus(plan.id, "planned") });
    } else if (["cancelled","rolled_back"].includes(s)) {
      acts.push({ label: "\\u21A9 Reset to Planned", color: "#5b8def", fn: () => doUpdateStatus(plan.id, "planned") });
    }'''
d = d.replace(old_failed, new_failed)

# Fix completed actions - add Rollback
old_completed = '''    } else if (s === "completed") {
      acts.push({ label: "\\u{1F5D1}\\uFE0F Decommission Source", color: "#ef4444", confirm: true, fn: () => showToast("Source VMs flagged for decommission") });'''
new_completed = '''    } else if (s === "completed") {
      acts.push({ label: "\\u{1F5D1}\\uFE0F Decommission Source", color: "#ef4444", confirm: true, fn: () => doUpdateStatus(plan.id, "completed", "SOURCE_DECOM_REQUESTED").then(() => showToast("Source VMs flagged for decommission")) });
      acts.push({ label: "\\u21A9\\uFE0F Rollback", color: "#f97316", confirm: true, fn: () => doUpdateStatus(plan.id, "rolled_back", "Rollback requested") });'''
d = d.replace(old_completed, new_completed)

# ========== 6. Fix visibility - brighter text colors ==========
# thStyle - make brighter and bigger
old_th = '''  const thStyle = { padding: "10px 14px", textAlign: "left", fontSize: 11, fontWeight: 700, color: p.textMute, textTransform: "uppercase", letterSpaci'''
# Find full thStyle line
idx_th = d.find('const thStyle')
idx_th_end = d.find(';', idx_th)
old_th_full = d[idx_th:idx_th_end+1]
new_th = 'const thStyle = { padding: "12px 16px", textAlign: "left", fontSize: 12.5, fontWeight: 800, color: p.text, textTransform: "uppercase", letterSpacing: "1px", borderBottom: `2px solid ${p.border}` };'
d = d.replace(old_th_full, new_th)

# tdStyle - bigger font
idx_td = d.find('const tdStyle')
idx_td_end = d.find(';', idx_td)
old_td_full = d[idx_td:idx_td_end+1]
new_td = 'const tdStyle = { padding: "12px 16px", fontSize: 13.5, fontWeight: 500, color: p.text, borderBottom: `1px solid ${p.border}15` };'
d = d.replace(old_td_full, new_td)

# badge - bigger, more visible
idx_badge = d.find('const badge')
idx_badge_end = d.find(';', idx_badge)
old_badge_full = d[idx_badge:idx_badge_end+1]
new_badge = 'const badge = (bg, fg) => ({ display: "inline-flex", alignItems: "center", gap: 4, padding: "5px 12px", borderRadius: 99, fontSize: 12, fontWeight: 700, background: `${bg}22`, color: bg, border: `1.5px solid ${bg}40`, letterSpacing: ".3px" });'
d = d.replace(old_badge_full, new_badge)

# btnOutline - brighter
old_btn_outline = '  const btnOutline = { ...btn(p.grey), background: "transparent", color: p.textSub, border: `1px solid ${p.border}`, boxShadow: "none" };'
new_btn_outline = '  const btnOutline = { ...btn(p.grey), background: "transparent", color: p.text, border: `1.5px solid ${p.border}`, boxShadow: "none", fontWeight: 700 };'
d = d.replace(old_btn_outline, new_btn_outline)

# Fix subtitle text - "Cross-Hypervisor" line
old_sub = '''fontSize: 12, color: p.textMute, fontWeight: 500'''
new_sub = '''fontSize: 13, color: p.textSub || p.textMute, fontWeight: 600'''
d = d.replace(old_sub, new_sub, 1)

# ========== 7. Add Migration Options panel in Review step ==========
old_review_effort = '''            {/* Effort estimate */}'''
options_panel = '''            {/* Migration Options */}
            <div style={{ ...card, background: p.panelAlt, marginBottom: 20, border: `1.5px solid ${p.border}` }}>
              <div style={{ fontSize: 14, fontWeight: 800, color: p.accent, marginBottom: 16 }}>\\u2699\\uFE0F Migration Options</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>

                {/* Cold / Warm toggle */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }} onClick={() => setMigWarm(!migWarm)}>
                  <div style={{ width: 40, height: 22, borderRadius: 11, background: migWarm ? "#f59e0b" : "#5b8def", transition: "background .2s", position: "relative" }}>
                    <div style={{ width: 18, height: 18, borderRadius: "50%", background: "#fff", position: "absolute", top: 2, left: migWarm ? 20 : 2, transition: "left .2s", boxShadow: "0 1px 3px #0003" }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>{migWarm ? "\\u2600\\uFE0F Warm Migration" : "\\u2744\\uFE0F Cold Migration"}</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>{migWarm ? "Live precopy, minimal downtime (requires CBT)" : "Power off source VM first, then transfer disks"}</div>
                  </div>
                </div>

                {/* Power on target */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migPowerOn} onChange={e => setMigPowerOn(e.target.checked)} style={{ width: 18, height: 18, accentColor: p.green }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>\\u26A1 Power On After Migration</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Automatically start the VM on the target platform</div>
                  </div>
                </label>

                {/* Keep source */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migKeepSource} onChange={e => { setMigKeepSource(e.target.checked); if (e.target.checked) setMigDecomSource(false); }} style={{ width: 18, height: 18, accentColor: "#5b8def" }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>\\u{1F4BE} Keep Source VM</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Retain source VM after migration (powered off)</div>
                  </div>
                </label>

                {/* Decommission source */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: migDecomSource ? `${p.red}10` : p.surface, border: `1px solid ${migDecomSource ? p.red + "40" : p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migDecomSource} onChange={e => { setMigDecomSource(e.target.checked); if (e.target.checked) setMigKeepSource(false); }} style={{ width: 18, height: 18, accentColor: p.red }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: migDecomSource ? p.red : p.text }}>\\u{1F5D1}\\uFE0F Decommission Source</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Remove source VM from vCenter after successful migration</div>
                  </div>
                </label>

                {/* Skip guest conversion */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migSkipConvert} onChange={e => setMigSkipConvert(e.target.checked)} style={{ width: 18, height: 18, accentColor: "#f59e0b" }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>\\u23E9 Skip Guest Conversion</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Skip virt-v2v (faster, but may need manual virtio drivers)</div>
                  </div>
                </label>

                {/* Preserve IPs */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migPreserveIPs} onChange={e => setMigPreserveIPs(e.target.checked)} style={{ width: 18, height: 18, accentColor: "#06b6d4" }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>\\u{1F310} Preserve Static IPs</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Keep VM IP addresses (requires bridge/Multus networking)</div>
                  </div>
                </label>

                {/* Pre-flight inspection */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migPreflight} onChange={e => setMigPreflight(e.target.checked)} style={{ width: 18, height: 18, accentColor: p.green }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>\\u{1F50D} Run Pre-flight Inspection</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>MTV inspects VM compatibility before migration</div>
                  </div>
                </label>

                {/* Target Namespace (OpenShift only) */}
                {targetPlatform === "openshift" && (
                  <div style={{ padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}` }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text, marginBottom: 6 }}>\\u{1F3AF} Target Namespace</div>
                    <input value={migTargetNS} onChange={e => setMigTargetNS(e.target.value)} placeholder="openshift-mtv" style={{ ...inputStyle, width: "100%" }} />
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 4 }}>OCP namespace where migrated VMs will be created</div>
                  </div>
                )}
              </div>
            </div>

            {/* Schedule & Notes */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: p.text, marginBottom: 6, display: "block" }}>\\u{1F4C5} Schedule Migration (optional)</label>
                <input type="datetime-local" value={migSchedule} onChange={e => setMigSchedule(e.target.value)} style={{ ...inputStyle, width: "100%" }} />
                <div style={{ fontSize: 11, color: p.textSub, marginTop: 4 }}>Leave empty for manual execution after approval</div>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: p.text, marginBottom: 6, display: "block" }}>\\u{1F4DD} Notes / Change Ticket</label>
                <input value={migNotes} onChange={e => setMigNotes(e.target.value)} placeholder="e.g. CHG-12345 or JIRA-678" style={{ ...inputStyle, width: "100%" }} />
                <div style={{ fontSize: 11, color: p.textSub, marginTop: 4 }}>Reference ticket or migration notes</div>
              </div>
            </div>

            {/* Effort estimate */}'''
d = d.replace(old_review_effort, options_panel)

# ========== 8. Fix Plans tab text visibility ==========
# Activity log text bigger
d = d.replace('fontSize: 10.5, color: p.textSub', 'fontSize: 12, color: p.text')
# Timestamp brighter
d = d.replace('color: p.textMute, fontFamily: "monospace", whiteSpace: "nowrap", minWidth: 130', 'color: p.textSub || p.textMute, fontFamily: "monospace", whiteSpace: "nowrap", minWidth: 145, fontWeight: 500')
# Pipeline step labels bigger
d = d.replace('fontSize: 8, marginTop: 3', 'fontSize: 9.5, marginTop: 4')
# Plan name column brighter
d = d.replace('...tdStyle, fontWeight: 700', '...tdStyle, fontWeight: 800, fontSize: 14')
# Progress bar height in table
d = d.replace('flex: 1, height: 6, borderRadius: 3', 'flex: 1, height: 8, borderRadius: 4')
# Progress % text bigger
d = d.replace('fontSize: 10, color: p.textMute, fontWeight: 700, minWidth: 28', 'fontSize: 12, color: p.text, fontWeight: 800, minWidth: 32')
# Detail panel progress bar bigger
d = d.replace('height: 10, borderRadius: 5, background: `${p.textMute}15`', 'height: 14, borderRadius: 7, background: `${p.textMute}20`')
d = d.replace('height: "100%", borderRadius: 5, background: `linear-gradient', 'height: "100%", borderRadius: 7, background: `linear-gradient')
# Info grid text bigger
d = d.replace("display: \"grid\", gridTemplateColumns: \"1fr 1fr 1fr\", gap: 10, fontSize: 12", "display: \"grid\", gridTemplateColumns: \"1fr 1fr 1fr\", gap: 12, fontSize: 13")
# VMs in plan label bigger
d = d.replace('fontSize: 11, fontWeight: 700, color: p.textMute, marginBottom: 6, textTransform: "uppercase"', 'fontSize: 12, fontWeight: 800, color: p.text, marginBottom: 8, textTransform: "uppercase"')
# VM chips bigger
d = d.replace('padding: "4px 10px", borderRadius: 6, background: `${p.border}22`, fontSize: 11, fontWeight: 600', 'padding: "6px 12px", borderRadius: 8, background: `${p.border}30`, fontSize: 12, fontWeight: 700, color: p.text')
# Action buttons bigger
d = d.replace('padding: "7px 16px", borderRadius: 7', 'padding: "9px 18px", borderRadius: 8')
d = d.replace('fontSize: 11.5, cursor', 'fontSize: 12.5, cursor')
# Empty state text bigger
d = d.replace('fontSize: 16, fontWeight: 700, marginBottom: 6', 'fontSize: 18, fontWeight: 800, marginBottom: 8, color: p.text')
# Activity log header bigger
d = d.replace('padding: "8px 12px", background: `${p.border}33`, fontSize: 11, fontWeight: 700', 'padding: "10px 14px", background: `${p.border}33`, fontSize: 13, fontWeight: 800')
# Header "Migration Plans" bigger
d = d.replace('fontSize: 16, fontWeight: 800, color: p.text', 'fontSize: 20, fontWeight: 900, color: p.text', 1)
# Pipeline dots bigger
d = d.replace('width: 30, height: 30, borderRadius: "50%"', 'width: 34, height: 34, borderRadius: "50%"')
# Created column brighter
d = d.replace('...tdStyle, fontSize: 11', '...tdStyle, fontSize: 12, fontWeight: 500')
# "No migration plans" subtext
d = d.replace('fontSize: 12 }}>Create your first plan', 'fontSize: 13, color: p.textSub }}>Create your first plan')
# Show notes/schedule in plan expanded detail
old_created_info = '''              {plan.approved_by && <div><b>Approved By:</b> {plan.approved_by} @ {plan.approved_at}</div>}'''
new_created_info = '''              {plan.approved_by && <div><b>Approved By:</b> {plan.approved_by} @ {plan.approved_at}</div>}
              {plan.notes && <div><b>Notes:</b> {plan.notes}</div>}'''
d = d.replace(old_created_info, new_created_info)

open(M, "w", encoding="utf-8").write(d)
print(f"Done. File size: {len(d)} bytes, {len(d.splitlines())} lines")