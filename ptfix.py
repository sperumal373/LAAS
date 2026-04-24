PATH = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
with open(PATH, "rb") as f:
    text = f.read().decode("utf-8")
changes = 0

# 1. Add ptAapInstances state
old1 = 'const [ptExpandedTask, setPtExpandedTask] = useState(null);'
new1 = old1 + '\n  const [ptAapInstances, setPtAapInstances] = useState([]);\n  const [ptLoadingPB, setPtLoadingPB] = useState(false);'
if 'ptAapInstances' not in text:
    text = text.replace(old1, new1)
    changes += 1
    print("1. Added ptAapInstances state")

# 2. Fix openPostTasks - fetch /api/ansible/instances instead of playbooks
old2 = 'fetch("/api/migration/move-groups/" + gid + "/post-tasks/playbooks"'
new2 = 'fetch("/api/ansible/instances"'
if '/post-tasks/playbooks",' in text and 'setPtPlaybooks(pbRes' in text:
    text = text.replace(old2, new2)
    text = text.replace('const [pbRes, histRes]', 'const [aapRes, histRes]')
    text = text.replace('setPtPlaybooks(pbRes.playbooks || []);', 'setPtAapInstances((aapRes.instances || []).filter(i => i.status === "ok"));')
    changes += 1
    print("2. Fixed openPostTasks to fetch AAP instances")

# 3. Add loadPlaybooksForInstance function
old3 = '  async function runPostTask() {'
new3 = '''  async function loadPlaybooksForInstance(instId) {
    setPtSelAapInst(instId); setPtPlaybooks([]); setPtSelTemplate("");
    if (!instId) return;
    setPtLoadingPB(true);
    try {
      const r = await fetch("/api/migration/move-groups/" + ptGroupId + "/post-tasks/playbooks?aap_id=" + instId, {
        headers: { Authorization: "Bearer " + localStorage.getItem("token") }
      }).then(r => r.json());
      setPtPlaybooks(r.playbooks || []);
    } catch (e) { showToast("Failed to load playbooks: " + e.message, "error"); }
    setPtLoadingPB(false);
  }
  async function runPostTask() {'''
if 'loadPlaybooksForInstance' not in text:
    text = text.replace(old3, new3)
    changes += 1
    print("3. Added loadPlaybooksForInstance function")

# 4. Replace playbook selector - add AAP instance dropdown
old_label = "Select Playbook / Job Template</label>"
new_label = "AAP Instance</label>"
old_select_val = "value={ptSelTemplate} onChange={e => setPtSelTemplate(e.target.value)}"
# Instead of complex multi-line replace, do surgical replacements
# Replace the label
if old_label in text and 'AAP Instance</label>' not in text:
    # Find the playbook section and replace it
    idx = text.find("Select Playbook / Job Template</label>")
    if idx > 0:
        # Find the enclosing div start
        sec_start = text.rfind("{ptTaskType === 'playbook' && (", idx - 500, idx)
        sec_end = text.find("{ptTaskType === 'custom' && (", idx)
        if sec_start > 0 and sec_end > 0:
            old_section = text[sec_start:sec_end]
            new_section = """{ptTaskType === 'playbook' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: 'block' }}>AAP Instance</label>
                    <select value={ptSelAapInst} onChange={e => loadPlaybooksForInstance(e.target.value)}
                      style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid ' + p.border, background: p.bg, color: p.text, fontSize: 13 }}>
                      <option value="">-- Select AAP Instance --</option>
                      {ptAapInstances.map(inst => (
                        <option key={inst.id} value={inst.id}>{inst.name} ({inst.url}) - {inst.env}</option>
                      ))}
                    </select>
                    {ptAapInstances.length === 0 && <div style={{ fontSize: 11.5, color: '#f59e0b', marginTop: 6 }}>No AAP instances configured.</div>}
                  </div>
                  {ptSelAapInst && (
                    <div>
                      <label style={{ fontSize: 11.5, fontWeight: 700, color: p.textMute, marginBottom: 6, display: 'block' }}>Playbook / Job Template {ptLoadingPB && '(loading...)'}</label>
                      <select value={ptSelTemplate} onChange={e => setPtSelTemplate(e.target.value)}
                        style={{ width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid ' + p.border, background: p.bg, color: p.text, fontSize: 13 }}>
                        <option value="">{ptLoadingPB ? 'Loading...' : '-- ' + ptPlaybooks.length + ' playbooks available --'}</option>
                        {ptPlaybooks.map(pb => (
                          <option key={pb.aap_instance_id + ':' + pb.id} value={pb.aap_instance_id + ':' + pb.id}>
                            {pb.name} {pb.playbook ? '(' + pb.playbook + ')' : ''}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              )}
              """
            text = text[:sec_start] + new_section + text[sec_end:]
            changes += 1
            print("4. Replaced playbook selector with AAP instance picker")

print(f"\nTotal changes: {changes}")
with open(PATH, "wb") as f:
    f.write(text.encode("utf-8"))
print("Saved!")