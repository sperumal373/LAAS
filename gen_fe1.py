import re
M = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
mp = open(M, 'r', encoding='utf-8').read()

# 1. Update imports
mp = mp.replace(
    "fetchMigrationPlans, createMigrationPlan, deleteMigrationPlan, runPreflightCheck,",
    "fetchMigrationPlans, createMigrationPlan, deleteMigrationPlan, updatePlanStatus, executeMigrationPlan, fetchPlanEvents, runPreflightCheck,"
)
print("1. Imports updated")

# 2. Add polling state after expandedPlan
old_state = 'const [expandedPlan, setExpandedPlan] = useState(null);'
new_state = old_state + """
  const [pollingPlan, setPollingPlan] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);
  const [liveProgress, setLiveProgress] = useState(0);
  const [liveStatus, setLiveStatus] = useState("");"""
mp = mp.replace(old_state, new_state)
print("2. State vars added")

# 3. Add lifecycle functions after delPlan
old_del = '''    try { await deleteMigrationPlan(id); showToast("Plan deleted"); loadPlans(); }
    catch { showToast("Delete failed", "error"); }
  };

  // Styles'''

new_del = '''    try { await deleteMigrationPlan(id); showToast("Plan deleted"); loadPlans(); }
    catch { showToast("Delete failed", "error"); }
  };

  const doUpdateStatus = async (id, newStatus, notes = "") => {
    try {
      await updatePlanStatus(id, { status: newStatus, notes });
      showToast("Status updated to '" + newStatus + "'");
      loadPlans();
    } catch (e) { showToast(e.message || "Status update failed", "error"); }
  };

  const startExecution = async (id) => {
    try {
      await executeMigrationPlan(id);
      showToast("Migration execution started!");
      setPollingPlan(id);
      setExpandedPlan(id);
      loadPlans();
    } catch (e) { showToast(e.message || "Execution failed", "error"); }
  };

  useEffect(() => {
    if (!pollingPlan) return;
    const interval = setInterval(async () => {
      try {
        const r = await fetchPlanEvents(pollingPlan);
        setLiveEvents(r.event_log || []);
        setLiveProgress(r.progress || 0);
        setLiveStatus(r.status || "");
        if (["completed", "failed", "cancelled", "rolled_back"].includes(r.status)) {
          setPollingPlan(null);
          loadPlans();
        }
      } catch {}
    }, 3000);
    fetchPlanEvents(pollingPlan).then(r => {
      setLiveEvents(r.event_log || []);
      setLiveProgress(r.progress || 0);
      setLiveStatus(r.status || "");
    }).catch(() => {});
    return () => clearInterval(interval);
  }, [pollingPlan]);

  useEffect(() => {
    const active = plans.find(pp => ["executing","migrating","validating"].includes(pp.status));
    if (active && !pollingPlan) {
      setPollingPlan(active.id);
      setExpandedPlan(active.id);
    }
  }, [plans]);

  const STATUS_CFG = {
    planned:           { label: "PLANNED",       color: "#5b8def", icon: "\\u{1F4CB}", ord: 0 },
    preflight_running: { label: "PRE-FLIGHT...", color: "#f59e0b", icon: "\\u{1F50D}", ord: 1 },
    preflight_passed:  { label: "PRE-FLIGHT OK", color: "#22c55e", icon: "\\u2705",    ord: 2 },
    preflight_failed:  { label: "PRE-FLIGHT FAIL", color: "#ef4444", icon: "\\u274C",  ord: 2 },
    approved:          { label: "APPROVED",      color: "#8b5cf6", icon: "\\u{1F44D}", ord: 3 },
    executing:         { label: "EXECUTING",     color: "#f59e0b", icon: "\\u26A1",    ord: 4 },
    migrating:         { label: "MIGRATING",     color: "#f97316", icon: "\\u{1F504}", ord: 5 },
    validating:        { label: "VALIDATING",    color: "#06b6d4", icon: "\\u{1F50E}", ord: 6 },
    completed:         { label: "COMPLETED",     color: "#22c55e", icon: "\\u{1F389}", ord: 7 },
    failed:            { label: "FAILED",        color: "#ef4444", icon: "\\u{1F4A5}", ord: -1 },
    cancelled:         { label: "CANCELLED",     color: "#6b7280", icon: "\\u{1F6AB}", ord: -1 },
    rolled_back:       { label: "ROLLED BACK",   color: "#6b7280", icon: "\\u21A9\\uFE0F", ord: -1 },
  };

  const PIPELINE = ["planned","preflight_passed","approved","executing","migrating","validating","completed"];

  const getActions = (plan) => {
    const s = plan.status;
    const acts = [];
    if (s === "planned") {
      acts.push({ label: "\\u{1F50D} Run Pre-flight", color: "#f59e0b", fn: () => doUpdateStatus(plan.id, "preflight_running").then(() => {
        setTimeout(async () => {
          const hasFail = plan.preflight_result?.fail > 0;
          await updatePlanStatus(plan.id, { status: hasFail ? "preflight_failed" : "preflight_passed", notes: "Pre-flight completed" });
          loadPlans();
        }, 3000);
      })});
      acts.push({ label: "\\u2716 Cancel", color: "#6b7280", confirm: true, fn: () => doUpdateStatus(plan.id, "cancelled") });
    } else if (s === "preflight_passed") {
      acts.push({ label: "\\u{1F44D} Approve & Schedule", color: "#8b5cf6", fn: () => doUpdateStatus(plan.id, "approved") });
      acts.push({ label: "\\u{1F504} Re-run Pre-flight", color: "#f59e0b", fn: () => doUpdateStatus(plan.id, "planned") });
    } else if (s === "preflight_failed") {
      acts.push({ label: "\\u{1F504} Re-run Pre-flight", color: "#f59e0b", fn: () => doUpdateStatus(plan.id, "planned") });
      acts.push({ label: "\\u2716 Cancel", color: "#6b7280", confirm: true, fn: () => doUpdateStatus(plan.id, "cancelled") });
    } else if (s === "approved") {
      acts.push({ label: "\\u{1F680} Execute Migration", color: "#22c55e", fn: () => startExecution(plan.id) });
      acts.push({ label: "\\u21A9 Back to Planned", color: "#6b7280", fn: () => doUpdateStatus(plan.id, "planned") });
    } else if (s === "validating") {
      acts.push({ label: "\\u2705 Mark Completed", color: "#22c55e", fn: () => doUpdateStatus(plan.id, "completed") });
      acts.push({ label: "\\u274C Mark Failed", color: "#ef4444", confirm: true, fn: () => doUpdateStatus(plan.id, "failed") });
    } else if (s === "completed") {
      acts.push({ label: "\\u{1F5D1}\\uFE0F Decommission Source", color: "#ef4444", confirm: true, fn: () => showToast("Source VMs flagged for decommission") });
    } else if (["failed","cancelled","rolled_back"].includes(s)) {
      acts.push({ label: "\\u21A9 Reset to Planned", color: "#5b8def", fn: () => doUpdateStatus(plan.id, "planned") });
    }
    return acts;
  };

  // Styles'''

if old_del not in mp:
    print("ERROR: delPlan marker not found!")
    import sys; sys.exit(1)
mp = mp.replace(old_del, new_del)
print("3. Lifecycle functions added")

open(M, 'w', encoding='utf-8').write(mp)
print("4. File saved. Now need to update Plans tab UI...")