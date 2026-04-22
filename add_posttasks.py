import json, sys

PATH = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"

with open(PATH, "rb") as f:
    text = f.read().decode("utf-8")

orig_count = text.count("\n")
print(f"Original: {orig_count} lines")

# ============================================================
# PART 1: Self-contained components BEFORE export default
# ============================================================
COMP_CODE = '''
function AapDropdown({ value, onSelect, p }) {
  const [list, setList] = useState([]);
  const [ld, setLd] = useState(true);
  useEffect(() => {
    fetch("/api/ansible/instances", { headers: { Authorization: "Bearer " + localStorage.getItem("token") } })
      .then(r => r.json())
      .then(d => { setList((d.instances || []).filter(i => i.status === "ok")); setLd(false); })
      .catch(() => setLd(false));
  }, []);
  return (
    <div>
      <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: "block" }}>AAP Instance</label>
      {ld ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>Loading instances...</div> :
       list.length === 0 ? <div style={{ color: "#f59e0b", fontSize: 12, padding: 8 }}>No AAP instances configured.</div> :
       <select value={value || ""} onChange={e => onSelect(e.target.value)}
         style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 13 }}>
         <option value="">-- Select AAP Instance ({list.length} available) --</option>
         {list.map(i => <option key={i.id} value={String(i.id)}>{i.name} ({i.url}) - {i.env}</option>)}
       </select>}
    </div>
  );
}

function PlaybookDropdown({ aapId, groupId, value, onSelect, p }) {
  const [list, setList] = useState([]);
  const [ld, setLd] = useState(false);
  const [q, setQ] = useState("");
  const [debounceTimer, setDebounceTimer] = useState(null);
  const doSearch = (searchTerm) => {
    if (!aapId) return;
    setLd(true);
    const url = "/api/migration/move-groups/" + groupId + "/post-tasks/playbooks?aap_id=" + aapId + (searchTerm ? "&search=" + encodeURIComponent(searchTerm) : "");
    fetch(url, { headers: { Authorization: "Bearer " + getToken() } })
      .then(r => r.json())
      .then(d => { setList(d.playbooks || []); setLd(false); })
      .catch(() => { setList([]); setLd(false); });
  };
  useEffect(() => {
    if (!aapId) { setList([]); setQ(""); return; }
    setQ(""); setList([]);
  }, [aapId, groupId]);
  const handleSearch = (val) => {
    setQ(val);
    if (debounceTimer) clearTimeout(debounceTimer);
    if (val.length >= 2) {
      setDebounceTimer(setTimeout(() => doSearch(val), 400));
    } else {
      setList([]);
    }
  };
  if (!aapId) return null;
  return (
    <div>
      <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: "block" }}>
        Playbook / Job Template {ld && "(searching...)"}
      </label>
      <input placeholder="Type 2+ chars to search playbooks..." value={q} onChange={e => handleSearch(e.target.value)}
        style={{ width: "100%", padding: "8px 12px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 12, marginBottom: 6, boxSizing: "border-box" }} />
      {ld ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>Searching...</div> :
       list.length > 0 ? (
         <select value={value || ""} onChange={e => onSelect(e.target.value)}
           style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 13 }}
           size={Math.min(list.length + 1, 12)}>
           <option value="">-- {list.length} playbooks found --</option>
           {list.map(pb => <option key={pb.aap_instance_id + ":" + pb.id} value={pb.aap_instance_id + ":" + pb.id}>{pb.name}{pb.playbook ? " (" + pb.playbook + ")" : ""}</option>)}
         </select>
       ) : q.length >= 2 ? <div style={{ color: p.textMute, fontSize: 12, padding: 8 }}>No playbooks found</div> : null}
    </div>
  );
}

'''

m = "export default function MigrationPage"
assert m in text, "FAIL: no MigrationPage export"
text = text.replace(m, COMP_CODE + m, 1)
print("1/5 Components added")

# ============================================================
# PART 2: State variables after mgLoading
# ============================================================
anchor = "const [mgLoading, setMgLoading] = useState(false);"
assert anchor in text
STATE = '''
  // Post-Migration Tasks
  const [ptGroupId, setPtGroupId] = useState(null);
  const [ptTaskType, setPtTaskType] = useState("playbook");
  const [ptSelAapInst, setPtSelAapInst] = useState("");
  const [ptSelTemplate, setPtSelTemplate] = useState("");
  const [ptTaskName, setPtTaskName] = useState("");
  const [ptCustomScript, setPtCustomScript] = useState("");
  const [ptExtraVars, setPtExtraVars] = useState("");
  const [ptRunning, setPtRunning] = useState(false);
  const [ptTasks, setPtTasks] = useState([]);
  const [ptExpandedTask, setPtExpandedTask] = useState(null);
'''
text = text.replace(anchor, anchor + STATE, 1)
print("2/5 State vars added")

# ============================================================
# PART 3: Functions after loadGroups
# ============================================================
# Find "setMgLoading(false);\n  }\n" which ends loadGroups
for end_pat in ["setMgLoading(false);\n  }\n", "setMgLoading(false);\r\n  }\r\n"]:
    idx = text.find(end_pat)
    if idx >= 0:
        insert_at = idx + len(end_pat)
        break
assert idx >= 0, "FAIL: no loadGroups end"

FUNCS = '''
  async function openPostTasks(gid) {
    setPtGroupId(gid); setPtTasks([]);
    setPtTaskType("playbook"); setPtSelAapInst(""); setPtSelTemplate("");
    setPtTaskName(""); setPtCustomScript(""); setPtExtraVars("");
    try {
      const r = await fetch("/api/migration/move-groups/" + gid + "/post-tasks",
        { headers: { Authorization: "Bearer " + localStorage.getItem("token") } });
      const d = await r.json();
      setPtTasks(d.tasks || []);
    } catch (e) { console.error("post-tasks load err", e); }
  }

  async function runPostTask() {
    if (!ptTaskName.trim()) return showToast("Enter a task name", "error");
    if (ptTaskType === "playbook" && !ptSelTemplate) return showToast("Select a playbook", "error");
    setPtRunning(true);
    try {
      const body = { task_name: ptTaskName, task_type: ptTaskType };
      if (ptTaskType === "playbook") {
        const [aapId, tplId] = ptSelTemplate.split(":");
        body.aap_instance_id = parseInt(aapId);
        body.template_id = parseInt(tplId);
        if (ptExtraVars.trim()) body.extra_vars = JSON.parse(ptExtraVars);
      } else { body.script = ptCustomScript; }
      const r = await fetch("/api/migration/move-groups/" + ptGroupId + "/post-tasks/run",
        { method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + localStorage.getItem("token") }, body: JSON.stringify(body) });
      const d = await r.json();
      if (d.error) showToast(d.error, "error");
      else { showToast("Task started!", "success"); openPostTasks(ptGroupId); }
    } catch (e) { showToast("Failed: " + e.message, "error"); }
    setPtRunning(false);
  }

  async function refreshPostTaskStatus(tid) {
    try {
      const r = await fetch("/api/migration/move-groups/post-tasks/" + tid,
        { headers: { Authorization: "Bearer " + localStorage.getItem("token") } });
      const d = await r.json();
      setPtTasks(prev => prev.map(t => t.id === tid ? { ...t, ...d } : t));
    } catch (e) {}
  }

'''
text = text[:insert_at] + FUNCS + text[insert_at:]
print("3/5 Functions added")

# ============================================================
# PART 4: Post-Tasks button next to Migrate button
# ============================================================
mig_text = "\U0001f680 Migrate\n                  </button>"
mig_idx = text.find(mig_text)
if mig_idx < 0:
    mig_text = "\U0001f680 Migrate\r\n                  </button>"
    mig_idx = text.find(mig_text)
assert mig_idx >= 0, "FAIL: no Migrate button"
insert_at2 = mig_idx + len(mig_text)

BTN = '''
                  <button onClick={e => { e.stopPropagation(); openPostTasks(g.id); }} disabled={!g.vm_count}
                    style={{ padding: "7px 14px", borderRadius: 7, border: "none", background: g.vm_count ? "#8b5cf6" : p.border, color: "#fff", fontWeight: 700, fontSize: 12, cursor: g.vm_count ? "pointer" : "default", opacity: g.vm_count ? 1 : 0.5 }}>
                    \u2699\ufe0f Post-Tasks
                  </button>'''
text = text[:insert_at2] + BTN + text[insert_at2:]
print("4/5 Post-Tasks button added")

# ============================================================
# PART 5: Slide-out panel - inject before the final );} of the component
# ============================================================
# Find the return ( and its matching ); at the end
# The component ends with:\n  );\n}\n
# Find the LAST occurrence of "  );" followed by "}" 
lines = text.split("\n")
insert_line = -1
for i in range(len(lines)-1, -1, -1):
    if lines[i].strip() == "</div>":
        insert_line = i
        break

assert insert_line > 0, "FAIL: no closing div"
print(f"Inserting panel before line {insert_line+1}")

PANEL = '''      {/* POST-MIGRATION TASKS SLIDE-OUT PANEL */}
      {ptGroupId && (
        <div style={{ position: "fixed", top: 0, right: 0, width: 520, height: "100vh", background: p.surface, boxShadow: "-4px 0 30px rgba(0,0,0,.25)", zIndex: 1000, display: "flex", flexDirection: "column", borderLeft: "3px solid " + p.accent }}>
          <div style={{ padding: "18px 22px", borderBottom: "1px solid " + p.border, display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 22 }}>\u2699\ufe0f</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 800, fontSize: 16, color: p.text }}>Post-Migration Tasks</div>
              <div style={{ fontSize: 11.5, color: p.textMute }}>Group #{ptGroupId}</div>
            </div>
            <button onClick={() => setPtGroupId(null)} style={{ background: "none", border: "none", color: p.textMute, fontSize: 22, cursor: "pointer", fontWeight: 700 }}>&times;</button>
          </div>
          <div style={{ flex: 1, overflow: "auto", padding: "18px 22px", display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", gap: 8 }}>
              {[["playbook", "Ansible Playbook"], ["custom", "Custom Script"]].map(([val, label]) => (
                <button key={val} onClick={() => setPtTaskType(val)}
                  style={{ flex: 1, padding: "10px 14px", borderRadius: 8, border: "1px solid " + (ptTaskType === val ? p.accent : p.border), background: ptTaskType === val ? p.accent + "18" : "transparent", color: ptTaskType === val ? p.accent : p.textMute, fontWeight: 700, fontSize: 12.5, cursor: "pointer" }}>
                  {label}
                </button>
              ))}
            </div>
            <input value={ptTaskName} onChange={e => setPtTaskName(e.target.value)} placeholder="Task name (e.g. Install Monitoring Agent)"
              style={{ padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 13, width: "100%", boxSizing: "border-box" }} />
            {ptTaskType === "playbook" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <AapDropdown value={ptSelAapInst} onSelect={v => { setPtSelAapInst(v); setPtSelTemplate(""); }} p={p} />
                <PlaybookDropdown aapId={ptSelAapInst} groupId={ptGroupId} value={ptSelTemplate} onSelect={v => setPtSelTemplate(v)} p={p} />
              </div>
            )}
            {ptTaskType === "custom" && (
              <div>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: "block" }}>Script (runs on each VM via SSH/WinRM)</label>
                <textarea value={ptCustomScript} onChange={e => setPtCustomScript(e.target.value)} rows={6}
                  placeholder="# Example: install agent"
                  style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 12, fontFamily: "monospace", resize: "vertical", boxSizing: "border-box" }} />
              </div>
            )}
            {ptTaskType === "playbook" && (
              <div>
                <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: "block" }}>Extra Variables (JSON, optional)</label>
                <textarea value={ptExtraVars} onChange={e => setPtExtraVars(e.target.value)} rows={3}
                  placeholder='{"env": "production"}'
                  style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: "1px solid " + p.border, background: p.bg, color: p.text, fontSize: 12, fontFamily: "monospace", resize: "vertical", boxSizing: "border-box" }} />
              </div>
            )}
            <button onClick={runPostTask} disabled={ptRunning}
              style={{ padding: "12px 20px", borderRadius: 8, border: "none", background: ptRunning ? p.border : "#10b981", color: "#fff", fontWeight: 800, fontSize: 14, cursor: ptRunning ? "default" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              {ptRunning ? "Running..." : "\u25b6 Execute on All VMs"}
            </button>
            {ptTasks.length > 0 && (
              <div>
                <div style={{ fontSize: 13, fontWeight: 800, color: p.text, marginBottom: 10, borderTop: "1px solid " + p.border, paddingTop: 14 }}>Task History</div>
                {ptTasks.map(t => {
                  const sc = { running: "#3b82f6", successful: "#10b981", failed: "#ef4444", partial: "#f59e0b", pending: "#6b7280" };
                  return (
                    <div key={t.id} style={{ background: p.bg, borderRadius: 8, border: "1px solid " + p.border, marginBottom: 8, padding: "10px 14px", display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: sc[t.status] || "#6b7280", display: "inline-block" }}></span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: 12.5, color: p.text }}>{t.task_name}</div>
                        <div style={{ fontSize: 10.5, color: p.textMute }}>{t.task_type} | {t.triggered_by} | {(t.started_at || "").slice(0,16)}</div>
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 700, color: sc[t.status] || "#6b7280", textTransform: "uppercase" }}>{t.status}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}'''

panel_lines = PANEL.split("\n")
for pl in reversed(panel_lines):
    lines.insert(insert_line, pl)

text = "\n".join(lines)
print("5/5 Panel added")

final_count = text.count("\n")
print(f"Final: {final_count} lines (added {final_count - orig_count})")

with open(PATH, "wb") as f:
    f.write(text.encode("utf-8"))
print("SAVED")