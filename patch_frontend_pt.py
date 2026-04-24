import re
PATH = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
with open(PATH, "rb") as f:
    text = f.read().decode("utf-8")

changes = 0

# 1. State vars
target = 'const [mgTargetPlatform, setMgTargetPlatform] = useState("");'
pt_state = '''
  // Post-Migration Tasks state
  const [ptGroupId, setPtGroupId] = useState(null);
  const [ptPlaybooks, setPtPlaybooks] = useState([]);
  const [ptTasks, setPtTasks] = useState([]);
  const [ptLoading, setPtLoading] = useState(false);
  const [ptTaskType, setPtTaskType] = useState("playbook");
  const [ptSelTemplate, setPtSelTemplate] = useState("");
  const [ptTaskName, setPtTaskName] = useState("");
  const [ptCustomScript, setPtCustomScript] = useState("");
  const [ptExtraVars, setPtExtraVars] = useState("");
  const [ptRunning, setPtRunning] = useState(false);
  const [ptExpandedTask, setPtExpandedTask] = useState(null);'''
if "ptGroupId" not in text:
    text = text.replace(target, target + "\n" + pt_state)
    changes += 1
    print("1. Added state vars")

# 2. Functions
marker2 = "  async function loadVMsForGroup"
pt_funcs = '''
  async function openPostTasks(gid) {
    setPtGroupId(gid); setPtLoading(true); setPtPlaybooks([]); setPtTasks([]);
    setPtTaskType("playbook"); setPtSelTemplate(""); setPtTaskName(""); setPtCustomScript(""); setPtExtraVars("");
    try {
      const [pbRes, histRes] = await Promise.all([
        fetch("/api/migration/move-groups/" + gid + "/post-tasks/playbooks", { headers: { Authorization: "Bearer " + localStorage.getItem("token") } }).then(r => r.json()),
        fetch("/api/migration/move-groups/" + gid + "/post-tasks", { headers: { Authorization: "Bearer " + localStorage.getItem("token") } }).then(r => r.json())
      ]);
      setPtPlaybooks(pbRes.playbooks || []);
      setPtTasks(histRes.tasks || []);
    } catch (e) { showToast("Failed to load: " + e.message, "error"); }
    setPtLoading(false);
  }
  async function runPostTask() {
    if (!ptTaskName.trim()) return showToast("Enter a task name", "error");
    if (ptTaskType === "playbook" && !ptSelTemplate) return showToast("Select a playbook", "error");
    if (ptTaskType === "custom" && !ptCustomScript.trim()) return showToast("Enter a script", "error");
    setPtRunning(true);
    try {
      const body = { task_type: ptTaskType, task_name: ptTaskName,
        template_id: ptSelTemplate ? parseInt(ptSelTemplate.split(":")[1]) : null,
        aap_inst_id: ptSelTemplate ? parseInt(ptSelTemplate.split(":")[0]) : null,
        custom_script: ptCustomScript, extra_vars: ptExtraVars || "{}" };
      const r = await fetch("/api/migration/move-groups/" + ptGroupId + "/post-tasks/run", {
        method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + localStorage.getItem("token") },
        body: JSON.stringify(body) }).then(r => r.json());
      showToast(r.message || "Task started!", "success");
      setPtTaskName(""); setPtCustomScript(""); setPtExtraVars("");
      setTimeout(() => openPostTasks(ptGroupId), 3000);
    } catch (e) { showToast("Failed: " + e.message, "error"); }
    setPtRunning(false);
  }
  async function refreshPostTaskStatus(taskId) {
    try {
      const r = await fetch("/api/migration/move-groups/post-tasks/" + taskId, {
        headers: { Authorization: "Bearer " + localStorage.getItem("token") } }).then(r => r.json());
      setPtTasks(prev => prev.map(t => t.id === taskId ? { ...t, ...r } : t));
    } catch {}
  }

'''
if "openPostTasks" not in text:
    text = text.replace(marker2, pt_funcs + marker2)
    changes += 1
    print("2. Added functions")

# 3. Post-Tasks button
old_del = 'e.stopPropagation(); handleDeleteGroup(g.id);'
if "openPostTasks(g.id)" not in text and old_del in text:
    pt_btn = '''<button onClick={e => { e.stopPropagation(); openPostTasks(g.id); }} disabled={!g.vm_count}
                    style={{ padding: "7px 16px", borderRadius: 7, border: "none", background: g.vm_count ? "#8b5cf6" : p.border, color: "#fff", fontWeight: 700, fontSize: 12, cursor: g.vm_count ? "pointer" : "default", opacity: g.vm_count ? 1 : 0.5 }}>
                    Post-Tasks
                  </button>
                  <button onClick={e => { '''
    text = text.replace('<button onClick={e => { ' + old_del, pt_btn + old_del)
    changes += 1
    print("3. Added button")

print(f"Total changes: {changes}")
with open(PATH, "wb") as f:
    f.write(text.encode("utf-8"))
print("Frontend saved!")