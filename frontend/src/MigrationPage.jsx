import { useState, useEffect, useCallback, Fragment } from "react";
import {
  fetchVCenters, fetchVMs, fetchHosts,
  fetchOCPClusters, fetchOCPOperators, fetchOCPLiveNodes, fetchOCPStorageClasses,
  fetchNutanixPCs, fetchNutanixOverview, fetchNutanixClusters, fetchNutanixHosts, fetchNutanixStorage,
  fetchHVHosts, fetchHVStatus, fetchHVVMs,
  fetchDatastores, fetchNetworks,
  fetchMigrationPlans, createMigrationPlan, deleteMigrationPlan, updatePlanStatus, executeMigrationPlan, fetchPlanEvents, runPreflightCheck,
} from "./api";

/* ============================================================
   Magic Migrate - Cross-Hypervisor VM Migration Wizard
   Source: VMware | Target: OpenShift / Nutanix / Hyper-V
   ============================================================ */

const STEPS = [
  { label: "Source VMs", icon: "1" },
  { label: "Target", icon: "2" },
  { label: "Pre-flight", icon: "3" },
  { label: "Mapping", icon: "4" },
  { label: "Review", icon: "5" },
];

const TARGETS = [
  { id: "openshift", label: "Red Hat OpenShift", sub: "KubeVirt Virtualization", icon: "🔴", color: "#ef4444", gradient: "linear-gradient(135deg,#ef4444,#dc2626)" },
  { id: "nutanix",   label: "Nutanix AHV",       sub: "Acropolis Hypervisor",   icon: "🟩", color: "#10b981", gradient: "linear-gradient(135deg,#10b981,#059669)" },
  { id: "hyperv",    label: "Microsoft Hyper-V",  sub: "Windows Server Virtualization", icon: "🪩", color: "#3b82f6", gradient: "linear-gradient(135deg,#3b82f6,#2563eb)" },
];

function LoadDots({ p }) {
  return (
    <div style={{ display: "flex", gap: 6, justifyContent: "center", padding: 40 }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 10, height: 10, borderRadius: "50%", background: p.accent,
          animation: `ldDot 1.4s ease-in-out ${i * 0.16}s infinite both`
        }} />
      ))}
    </div>
  );
}

function Toast({ msg, type, onClose }) {
  if (!msg) return null;
  const bg = type === "error" ? "#ef4444" : "#10b981";
  return (
    <div style={{
      position: "fixed", top: 24, right: 24, zIndex: 9999,
      background: bg, color: "#fff", padding: "12px 24px", borderRadius: 10,
      fontWeight: 700, fontSize: 13, boxShadow: `0 4px 24px ${bg}40`,
      display: "flex", alignItems: "center", gap: 10, animation: "fadeIn .3s ease"
    }}>
      {type === "error" ? "❌" : "✅"} {msg}
      <span onClick={onClose} style={{ cursor: "pointer", marginLeft: 8, opacity: 0.7 }}>✕</span>
    </div>
  );
}

export default function MigrationPage({ currentUser, p }) {
  const [tab, setTab] = useState("new"); // "new" | "plans"
  const [step, setStep] = useState(0);
  const [toast, setToast] = useState(null);

  // Step 1 state
  const [vcenters, setVcenters] = useState([]);
  const [selVC, setSelVC] = useState("");
  const [hosts, setHosts] = useState([]);
  const [selHost, setSelHost] = useState("");
  const [allVMs, setAllVMs] = useState([]);
  const [vmSearch, setVmSearch] = useState("");
  const [selVMs, setSelVMs] = useState({});
  const [loadingVMs, setLoadingVMs] = useState(false);

  // Step 2 state
  const [targetPlatform, setTargetPlatform] = useState("");
  const [ocpClusters, setOcpClusters] = useState([]);
  const [nutPCs, setNutPCs] = useState([]);
  const [nutClusters, setNutClusters] = useState([]);
  const [hvHosts, setHvHosts] = useState([]);
  const [targetDetail, setTargetDetail] = useState({});
  const [loadingTarget, setLoadingTarget] = useState(false);

  // Step 3 state
  const [preflightResults, setPreflightResults] = useState(null);
  const [loadingPreflight, setLoadingPreflight] = useState(false);

  // Step 4 state
  const [networkMap, setNetworkMap] = useState([]);
  const [storageMap, setStorageMap] = useState([]);
  const [targetNetworks, setTargetNetworks] = useState([]);
  const [targetStorage, setTargetStorage] = useState([]);
  const [sourceNetworks, setSourceNetworks] = useState([]);
  const [sourceDatastores, setSourceDatastores] = useState([]);

  // Step 5 state
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
  const [migSchedule, setMigSchedule] = useState("");
  const [migCutoverMode, setMigCutoverMode] = useState("auto");
  const [migCutoverDatetime, setMigCutoverDatetime] = useState("");

  // Migration Options state
  const [plans, setPlans] = useState([]);
  const [loadingPlans, setLoadingPlans] = useState(false);
  const [expandedPlan, setExpandedPlan] = useState(null);
  const [pollingPlan, setPollingPlan] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);
  const [liveProgress, setLiveProgress] = useState(0);
  const [liveStatus, setLiveStatus] = useState("");

  const showToast = (msg, type = "success") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  // Load vCenters on mount
  useEffect(() => {
    fetchVCenters().then(r => setVcenters(Array.isArray(r) ? r : r.vcenters || [])).catch(() => {});
  }, []);

  // Load VMs when vCenter selected
  useEffect(() => {
    if (!selVC) { setAllVMs([]); setHosts([]); return; }
    setLoadingVMs(true);
    Promise.all([fetchVMs(), fetchHosts()])
      .then(([vr, hr]) => {
        const vms = (Array.isArray(vr) ? vr : vr.vms || []).filter(v => v.vcenter_id === selVC);
        const hList = (Array.isArray(hr) ? hr : hr.hosts || []).filter(h => h.vcenter_id === selVC);
        setAllVMs(vms);
        setHosts(hList);
        setSelHost("");
        setSelVMs({});
      })
      .catch(() => showToast("Failed to load VMs", "error"))
      .finally(() => setLoadingVMs(false));
  }, [selVC]);

  // Load plans
  const loadPlans = useCallback(() => {
    setLoadingPlans(true);
    fetchMigrationPlans().then(r => setPlans(r.plans || [])).catch(() => {}).finally(() => setLoadingPlans(false));
  }, []);
  useEffect(() => { if (tab === "plans") loadPlans(); }, [tab]);

  // Derived
  const filteredVMs = allVMs
    .filter(v => !selHost || v.host === selHost)
    .filter(v => !vmSearch || v.name?.toLowerCase().includes(vmSearch.toLowerCase()) || v.guest_os?.toLowerCase().includes(vmSearch.toLowerCase()));
  const selectedVMList = allVMs.filter(v => selVMs[v.moid || v.name]);
  const selCount = selectedVMList.length;
  const totalCPU = selectedVMList.reduce((s, v) => s + (v.cpu || 0), 0);
  const totalRAM = selectedVMList.reduce((s, v) => s + (v.ram_gb || 0), 0);
  const totalDisk = selectedVMList.reduce((s, v) => s + (parseFloat(v.disk_gb) || 0), 0);
  const allChecked = filteredVMs.length > 0 && filteredVMs.every(v => selVMs[v.moid || v.name]);

  const toggleVM = (key) => setSelVMs(prev => ({ ...prev, [key]: !prev[key] }));
  const toggleAll = () => {
    if (allChecked) setSelVMs({});
    else {
      const m = {};
      filteredVMs.forEach(v => m[v.moid || v.name] = true);
      setSelVMs(m);
    }
  };

  // Step 2: load target data
  const loadTargetData = async (platform) => {
    setTargetPlatform(platform);
    setTargetDetail({});
    setLoadingTarget(true);
    try {
      if (platform === "openshift") {
        const r = await fetchOCPClusters();
        setOcpClusters((Array.isArray(r) ? r : r.clusters || []).filter(c => c.status === "connected"));
      } else if (platform === "nutanix") {
        const r = await fetchNutanixPCs();
        setNutPCs((Array.isArray(r) ? r : r.prism_centrals || []).filter(pc => pc.status === "connected"));
        setNutClusters([]);
      } else if (platform === "hyperv") {
        const r = await fetchHVStatus();
        setHvHosts((Array.isArray(r) ? r : r.hosts || []).filter(h => h.success === true));
      }
    } catch { showToast("Failed to load target data", "error"); }
    setLoadingTarget(false);
  };

  const loadNutClusters = async (pcId) => {
    try {
      const r = await fetchNutanixClusters(pcId);
      setNutClusters(Array.isArray(r) ? r : r.clusters || []);
    } catch { setNutClusters([]); }
  };

  // Step 3: run preflight
  const doPreflight = async () => {
    setLoadingPreflight(true);
    try {
      const r = await runPreflightCheck({
        target_platform: targetPlatform,
        vms: selectedVMList.map(v => ({
          name: v.name, power_state: v.status, num_cpu: v.cpu,
          memory_mb: v.ram_gb, storage_used_gb: v.disk_gb,
          guest_os: v.guest_os, snapshot_count: v.snapshot_count || 0,
        })),
        target_detail: targetDetail,
      });
      setPreflightResults(r);
    } catch { showToast("Pre-flight check failed", "error"); }
    setLoadingPreflight(false);
  };
  useEffect(() => { if (step === 2) doPreflight(); }, [step]);

  // Step 4: load source networks/datastores + target mappings
  useEffect(() => {
    if (step === 3) {
      Promise.all([fetchNetworks(), fetchDatastores()]).then(([nr, dr]) => {
        const nets = [...new Set(selectedVMList.map(v => v.network || v.port_group || "Unknown"))];
        const dss = [...new Set(selectedVMList.map(v => v.datastore || "Unknown"))];
        setSourceNetworks(nets);
        setSourceDatastores(dss);
        setNetworkMap(nets.map(n => ({ source: n, target: "" })));
        setStorageMap(dss.map(d => ({ source: d, target: "" })));

        // target-specific options
        if (targetPlatform === "openshift" && targetDetail.cluster_id) {
          fetchOCPStorageClasses(targetDetail.cluster_id).then(r => setTargetStorage(Array.isArray(r) ? r : r.storage_classes || [])).catch(() => {});
          setTargetNetworks([{ name: "Pod Network (default)" }, { name: "Multus SR-IOV" }, { name: "OVN-Kubernetes" }]);
        } else if (targetPlatform === "nutanix" && targetDetail.pc_id) {
          fetchNutanixStorage(targetDetail.pc_id).then(r => setTargetStorage(Array.isArray(r) ? r : r.storage_containers || [])).catch(() => {});
          setTargetNetworks([{ name: "AHV Default VLAN" }, { name: "Managed Network" }]);
        } else if (targetPlatform === "hyperv") {
          setTargetNetworks([{ name: "Default Switch" }, { name: "External Switch" }, { name: "Private Switch" }]);
          setTargetStorage([{ name: "C:\\Hyper-V\\Virtual Hard Disks" }, { name: "D:\\VMs" }]);
        }
      }).catch(() => {});
    }
  }, [step]);

  // Step 5: save plan
  const savePlan = async () => {
    if (!planName.trim()) { showToast("Please enter a plan name", "error"); return; }
    setSaving(true);
    try {
      const tool = { openshift: "MTV (Migration Toolkit for Virtualization)", nutanix: "Nutanix Move", hyperv: "Manual (VMDK → VHDX Conversion)" }[targetPlatform] || "";
      await createMigrationPlan({
        plan_name: planName,
        source_platform: "vmware",
        source_vcenter: { vcenter_id: selVC, vcenter_name: vcenters.find(v => v.id === selVC)?.name || selVC },
        target_platform: targetPlatform,
        target_detail: targetDetail,
        vm_list: selectedVMList.map(v => ({ name: v.name, cpu: v.cpu, ram_mb: v.ram_gb, disk_gb: v.disk_gb, os: v.guest_os })),
        preflight_result: preflightResults?.summary || {},
        network_mapping: networkMap,
        storage_mapping: storageMap,
        migration_tool: tool,
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
          cutover_mode: migCutoverMode,
          cutover_datetime: migCutoverMode === "scheduled" ? migCutoverDatetime : null,
        },
        notes: migNotes,
      });
      showToast("Migration plan created successfully!");
      setTab("plans");
      // Reset wizard
      setStep(0); setSelVC(""); setSelVMs({}); setTargetPlatform(""); setTargetDetail({});
      setPreflightResults(null); setNetworkMap([]); setStorageMap([]); setPlanName("");
      setMigWarm(false); setMigPowerOn(true); setMigKeepSource(true); setMigDecomSource(false);
      setMigSkipConvert(false); setMigPreserveIPs(false); setMigPreflight(true);
      setMigTargetNS("openshift-mtv"); setMigNotes(""); setMigSchedule("");
      setMigSkipConvert(false); setMigPreserveIPs(false); setMigPreflight(true);
      setMigTargetNS("openshift-mtv"); setMigNotes(""); setMigSchedule("");
      setMigSkipConvert(false); setMigPreserveIPs(false); setMigPreflight(true);
      setMigTargetNS("openshift-mtv"); setMigNotes(""); setMigSchedule("");
      loadPlans();
    } catch(e) { showToast(e.message || "Failed to save plan", "error"); }
    setSaving(false);
  };

  // Delete plan
  const delPlan = async (id) => {
    if (!confirm("Delete this migration plan?")) return;
    try { await deleteMigrationPlan(id); showToast("Plan deleted"); loadPlans(); }
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
    planned:           { label: "PLANNED",       color: "#5b8def", icon: "📋", ord: 0 },
    preflight_running: { label: "PRE-FLIGHT...", color: "#f59e0b", icon: "🔍", ord: 1 },
    preflight_passed:  { label: "PRE-FLIGHT OK", color: "#22c55e", icon: "✅",    ord: 2 },
    preflight_failed:  { label: "PRE-FLIGHT FAIL", color: "#ef4444", icon: "❌",  ord: 2 },
    approved:          { label: "APPROVED",      color: "#8b5cf6", icon: "👍", ord: 3 },
    executing:         { label: "EXECUTING",     color: "#f59e0b", icon: "⚡",    ord: 4 },
    migrating:         { label: "MIGRATING",     color: "#f97316", icon: "🔄", ord: 5 },
    validating:        { label: "VALIDATING",    color: "#06b6d4", icon: "🔎", ord: 6 },
    completed:         { label: "COMPLETED",     color: "#22c55e", icon: "🎉", ord: 7 },
    failed:            { label: "FAILED",        color: "#ef4444", icon: "💥", ord: -1 },
    cancelled:         { label: "CANCELLED",     color: "#6b7280", icon: "🚫", ord: -1 },
    rolled_back:       { label: "ROLLED BACK",   color: "#6b7280", icon: "↩️", ord: -1 },
  };

  const PIPELINE = ["planned","preflight_passed","approved","executing","migrating","validating","completed"];

  const getActions = (plan) => {
    const s = plan.status;
    const acts = [];
    if (s === "planned") {
      acts.push({ label: "🔍 Run Pre-flight", color: "#f59e0b", fn: () => doUpdateStatus(plan.id, "preflight_running").then(() => {
        setTimeout(async () => {
          const hasFail = plan.preflight_result?.fail > 0;
          await updatePlanStatus(plan.id, { status: hasFail ? "preflight_failed" : "preflight_passed", notes: "Pre-flight completed" });
          loadPlans();
        }, 3000);
      })});
      acts.push({ label: "✖ Cancel", color: "#6b7280", confirm: true, fn: () => doUpdateStatus(plan.id, "cancelled") });
    } else if (s === "preflight_passed") {
      if (currentUser?.role === "admin") {
        acts.push({ label: "👍 Approve", color: "#8b5cf6", fn: () => {
          const sched = prompt("Schedule execution (leave blank for manual):\nFormat: YYYY-MM-DD HH:MM", "");
          doUpdateStatus(plan.id, "approved", sched ? "Scheduled: " + sched : "");
        }});
      } else {
        acts.push({ label: "🔒 Awaiting Admin Approval", color: "#6b7280", fn: () => showToast("Only admins can approve migration plans", "error") });
      }
      acts.push({ label: "🔄 Re-run Pre-flight", color: "#f59e0b", fn: () => doUpdateStatus(plan.id, "planned") });
    } else if (s === "preflight_failed") {
      acts.push({ label: "🔄 Re-run Pre-flight", color: "#f59e0b", fn: () => doUpdateStatus(plan.id, "planned") });
      acts.push({ label: "✖ Cancel", color: "#6b7280", confirm: true, fn: () => doUpdateStatus(plan.id, "cancelled") });
    } else if (s === "approved") {
      acts.push({ label: "🚀 Execute Migration", color: "#22c55e", fn: () => startExecution(plan.id) });
      acts.push({ label: "↩ Back to Planned", color: "#6b7280", fn: () => doUpdateStatus(plan.id, "planned") });
    } else if (s === "validating") {
      acts.push({ label: "✅ Mark Completed", color: "#22c55e", fn: () => doUpdateStatus(plan.id, "completed") });
      acts.push({ label: "❌ Mark Failed", color: "#ef4444", confirm: true, fn: () => doUpdateStatus(plan.id, "failed") });
    } else if (s === "completed") {
      acts.push({ label: "🗑️ Decommission Source", color: "#ef4444", confirm: true, fn: () => doUpdateStatus(plan.id, "completed", "SOURCE_DECOM_REQUESTED").then(() => showToast("Source VMs flagged for decommission")) });
      acts.push({ label: "↩️ Rollback", color: "#f97316", confirm: true, fn: () => doUpdateStatus(plan.id, "rolled_back", "Rollback requested") });
    } else if (s === "failed") {
      acts.push({ label: "🔄 Retry Migration", color: "#f59e0b", fn: () => doUpdateStatus(plan.id, "approved").then(() => { setTimeout(() => startExecution(plan.id), 500); }) });
      acts.push({ label: "↩ Reset to Planned", color: "#5b8def", fn: () => doUpdateStatus(plan.id, "planned") });
    } else if (["cancelled","rolled_back"].includes(s)) {
      acts.push({ label: "↩ Reset to Planned", color: "#5b8def", fn: () => doUpdateStatus(plan.id, "planned") });
    }
    return acts;
  };

  // Styles
  const card = { background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14, padding: 20, transition: "all .2s ease" };
  const btn = (color = p.accent) => ({
    padding: "10px 24px", borderRadius: 8, border: "none", cursor: "pointer", fontWeight: 700, fontSize: 13,
    background: `linear-gradient(135deg, ${color}, ${color}dd)`, color: "#fff",
    boxShadow: `0 2px 12px ${color}30`, transition: "all .2s ease",
  });
  const btnOutline = { ...btn(p.grey), background: "transparent", color: p.text, border: `1.5px solid ${p.border}`, boxShadow: "none", fontWeight: 700 };
  const thStyle = { padding: "14px 16px", textAlign: "left", fontSize: 13.5, fontWeight: 800, color: p.text, textTransform: "uppercase", letterSpacing: "1px", borderBottom: `2px solid ${p.border}` };
  const tdStyle = { padding: "14px 16px", fontSize: 14.5, fontWeight: 600, color: p.text, borderBottom: `1px solid ${p.border}15` };
  const inputStyle = { padding: "8px 14px", borderRadius: 8, border: `1px solid ${p.border}`, background: p.surface, color: p.text, fontSize: 13, outline: "none", width: "100%" };
  const selectStyle = { ...inputStyle, cursor: "pointer", appearance: "auto", WebkitAppearance: "menulist", colorScheme: p.mode === "dark" ? "dark" : "light" };
  const badge = (bg, fg) => ({ display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 14px", borderRadius: 99, fontSize: 13.5, fontWeight: 800, background: `${bg}22`, color: bg, border: `1.5px solid ${bg}55`, letterSpacing: ".4px", textShadow: `0 0 8px ${bg}30` });

  // ---- RENDER ----
  return (
    <div style={{ padding: "0 4px", maxWidth: 1400, margin: "0 auto" }}>
      <Toast msg={toast?.msg} type={toast?.type} onClose={() => setToast(null)} />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
        <div style={{ fontSize: 28, fontWeight: 900, background: `linear-gradient(135deg, ${p.purple}, ${p.accent}, ${p.cyan})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
          ✨ Magic Migrate
        </div>
        <div style={{ fontSize: 13, color: p.textSub || p.textMute, fontWeight: 600 }}>Cross-Hypervisor VM Migration Wizard</div>
        <div style={{ flex: 1 }} />
        {/* Tab toggle */}
        <div style={{ display: "flex", background: p.surface, borderRadius: 10, border: `1px solid ${p.border}`, overflow: "hidden" }}>
          {[["new", "✨ New Migration"], ["plans", "📋 Plans"]].map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)} style={{
              padding: "8px 20px", fontSize: 12, fontWeight: 700, border: "none", cursor: "pointer",
              background: tab === id ? p.accent : "transparent", color: tab === id ? "#fff" : p.textSub,
              transition: "all .2s ease",
            }}>{label}</button>
          ))}
        </div>
      </div>

      {/* ======================== NEW MIGRATION WIZARD ======================== */}
      {tab === "new" && (<>
        {/* Stepper */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 0, marginBottom: 32, flexWrap: "wrap" }}>
          {STEPS.map((s, i) => (
            <Fragment key={i}>
              {i > 0 && <div style={{ width: 48, height: 3, background: i <= step ? p.accent : p.border, borderRadius: 2, transition: "all .3s ease" }} />}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, cursor: i < step ? "pointer" : "default" }} onClick={() => { if (i < step) setStep(i); }}>
                <div style={{
                  width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                  fontWeight: 800, fontSize: 14, transition: "all .3s ease",
                  background: i < step ? p.green : i === step ? p.accent : p.surface,
                  color: i <= step ? "#fff" : p.textMute,
                  border: `2px solid ${i < step ? p.green : i === step ? p.accent : p.border}`,
                  boxShadow: i === step ? `0 0 16px ${p.accent}40` : "none",
                }}>
                  {i < step ? "✓" : s.icon}
                </div>
                <span style={{ fontSize: 10, fontWeight: 600, color: i <= step ? p.text : p.textMute }}>{s.label}</span>
              </div>
            </Fragment>
          ))}
        </div>

        {/* -------- STEP 1: Source VMs -------- */}
        {step === 0 && (
          <div style={card}>
            <div style={{ fontSize: 18, fontWeight: 800, color: p.text, marginBottom: 4 }}>📤 Source: VMware vSphere</div>
            <div style={{ fontSize: 12, color: p.textMute, marginBottom: 20 }}>Select the vCenter, optionally filter by ESXi host, then pick VMs to migrate.</div>

            <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 18 }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: p.textSub, marginBottom: 4, display: "block" }}>vCenter</label>
                <select value={selVC} onChange={e => setSelVC(e.target.value)} style={selectStyle}>
                  <option value="">-- Select vCenter --</option>
                  {vcenters.map(vc => <option key={vc.id} value={vc.id}>{vc.name} ({vc.host})</option>)}
                </select>
              </div>
              <div style={{ flex: 1, minWidth: 200 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: p.textSub, marginBottom: 4, display: "block" }}>ESXi Host (optional)</label>
                <select value={selHost} onChange={e => setSelHost(e.target.value)} style={selectStyle}>
                  <option value="">All Hosts</option>
                  {hosts.map(h => <option key={h.name} value={h.name}>{h.name}</option>)}
                </select>
              </div>
              <div style={{ flex: 1, minWidth: 200 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: p.textSub, marginBottom: 4, display: "block" }}>Search VMs</label>
                <input value={vmSearch} onChange={e => setVmSearch(e.target.value)} placeholder="Filter by name or OS..." style={inputStyle} />
              </div>
            </div>

            {loadingVMs ? <LoadDots p={p} /> : selVC && (
              <>
                {/* Selection stat bar */}
                {selCount > 0 && (
                  <div style={{
                    display: "flex", gap: 20, flexWrap: "wrap", padding: "10px 16px", marginBottom: 14,
                    borderRadius: 10, background: `${p.accent}10`, border: `1px solid ${p.accent}25`,
                  }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: p.accent }}>{selCount} VM{selCount !== 1 ? "s" : ""} selected</span>
                    <span style={{ fontSize: 12, color: p.textSub }}>🖥️ {totalCPU} vCPUs</span>
                    <span style={{ fontSize: 12, color: p.textSub }}>🧠 {totalRAM.toFixed(1)} GB RAM</span>
                    <span style={{ fontSize: 12, color: p.textSub }}>💾 {totalDisk.toFixed(1)} GB Storage</span>
                  </div>
                )}

                <div style={{ maxHeight: 420, overflowY: "auto", borderRadius: 10, border: `1px solid ${p.border}` }}>
                  <table style={{ width: "100%", borderCollapse: "collapse" }}>
                    <thead style={{ position: "sticky", top: 0, background: p.panelAlt, zIndex: 1 }}>
                      <tr>
                        <th style={thStyle}><input type="checkbox" checked={allChecked} onChange={toggleAll} /></th>
                        <th style={thStyle}>VM Name</th>
                        <th style={thStyle}>Power</th>
                        <th style={thStyle}>CPU</th>
                        <th style={thStyle}>RAM (GB)</th>
                        <th style={thStyle}>Disk (GB)</th>
                        <th style={thStyle}>Guest OS</th>
                        <th style={thStyle}>ESXi Host</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredVMs.length === 0 ? (
                        <tr><td colSpan={8} style={{ ...tdStyle, textAlign: "center", color: p.textMute, padding: 30 }}>No VMs found</td></tr>
                      ) : filteredVMs.map(vm => {
                        const key = vm.moid || vm.name;
                        const sel = !!selVMs[key];
                        return (
                          <tr key={key} onClick={() => toggleVM(key)} style={{ cursor: "pointer", background: sel ? `${p.accent}08` : "transparent", transition: "background .15s" }}>
                            <td style={tdStyle}><input type="checkbox" checked={sel} onChange={() => toggleVM(key)} /></td>
                            <td style={{ ...tdStyle, fontWeight: 600 }}>{vm.name}</td>
                            <td style={tdStyle}>
                              <span style={badge(vm.status === "poweredOn" ? p.green : p.grey)}>{vm.status === "poweredOn" ? "ON" : "OFF"}</span>
                            </td>
                            <td style={tdStyle}>{vm.cpu || "-"}</td>
                            <td style={tdStyle}>{vm.ram_gb ? (vm.ram_gb || 0).toFixed(1) : "-"}</td>
                            <td style={tdStyle}>{vm.disk_gb ? parseFloat(vm.disk_gb).toFixed(1) : "-"}</td>
                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.guest_os || "-"}</td>
                            <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500 }}>{vm.host || "-"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div style={{ textAlign: "right", marginTop: 16 }}>
                  <button disabled={selCount === 0} onClick={() => setStep(1)} style={{ ...btn(), opacity: selCount === 0 ? 0.4 : 1 }}>
                    Continue → Select Target
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* -------- STEP 2: Target Platform -------- */}
        {step === 1 && (
          <div style={card}>
            <div style={{ fontSize: 18, fontWeight: 800, color: p.text, marginBottom: 4 }}>🎯 Target Platform</div>
            <div style={{ fontSize: 12, color: p.textMute, marginBottom: 24 }}>Where do you want to migrate {selCount} VM{selCount !== 1 ? "s" : ""}?</div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16, marginBottom: 20 }}>
              {TARGETS.map(t => (
                <div key={t.id} onClick={() => loadTargetData(t.id)} style={{
                  ...card, cursor: "pointer", borderLeft: `4px solid ${t.color}`,
                  background: targetPlatform === t.id ? `${t.color}0a` : p.panel,
                  borderColor: targetPlatform === t.id ? t.color : p.border,
                  boxShadow: targetPlatform === t.id ? `0 4px 20px ${t.color}20` : "none",
                  transform: targetPlatform === t.id ? "scale(1.02)" : "scale(1)",
                }}>
                  <div style={{ fontSize: 36, marginBottom: 8 }}>{t.icon}</div>
                  <div style={{ fontSize: 20, fontWeight: 900, color: p.text }}>{t.label}</div>
                  <div style={{ fontSize: 11, color: p.textMute, marginTop: 2 }}>{t.sub}</div>
                  {targetPlatform === t.id && <div style={{ marginTop: 8, fontSize: 11, fontWeight: 700, color: t.color }}>✓ Selected</div>}
                </div>
              ))}
            </div>

            {/* Sub-selection */}
            {loadingTarget ? <LoadDots p={p} /> : targetPlatform && (
              <div style={{ ...card, background: p.panelAlt, marginBottom: 16 }}>
                {targetPlatform === "openshift" && (<>
                  <label style={{ fontSize: 11, fontWeight: 700, color: p.textSub, marginBottom: 6, display: "block" }}>OpenShift Cluster</label>
                  <select value={targetDetail.cluster_id || ""} onChange={e => setTargetDetail({ cluster_id: parseInt(e.target.value), cluster_name: ocpClusters.find(c => c.id === parseInt(e.target.value))?.name })} style={selectStyle}>
                    <option value="">-- Select Cluster --</option>
                    {ocpClusters.map(c => <option key={c.id} value={c.id}>{c.name} ({c.api_url})</option>)}
                  </select>
                  {ocpClusters.length === 0 && <div style={{ fontSize: 12, color: p.yellow, marginTop: 8 }}>⚠️ No connected OpenShift clusters found</div>}
                </>)}
                {targetPlatform === "nutanix" && (<>
                  <label style={{ fontSize: 11, fontWeight: 700, color: p.textSub, marginBottom: 6, display: "block" }}>Prism Central</label>
                  <select value={targetDetail.pc_id || ""} onChange={e => { const id = parseInt(e.target.value); setTargetDetail({ pc_id: id, pc_name: nutPCs.find(pc => pc.id === id)?.name }); if (id) loadNutClusters(id); }} style={selectStyle}>
                    <option value="">-- Select Prism Central --</option>
                    {nutPCs.map(pc => <option key={pc.id} value={pc.id}>{pc.name} ({pc.host})</option>)}
                  </select>
                  {targetDetail.pc_id && nutClusters.length > 0 && (<>
                    <label style={{ fontSize: 11, fontWeight: 700, color: p.textSub, marginTop: 12, marginBottom: 6, display: "block" }}>AHV Cluster</label>
                    <select value={targetDetail.cluster_uuid || ""} onChange={e => setTargetDetail(prev => ({ ...prev, cluster_uuid: e.target.value, cluster_name: nutClusters.find(c => c.uuid === e.target.value)?.name }))} style={selectStyle}>
                      <option value="">-- Select Cluster --</option>
                      {nutClusters.map(c => <option key={c.uuid || c.name} value={c.uuid}>{c.name}</option>)}
                    </select>
                  </>)}
                </>)}
                {targetPlatform === "hyperv" && (<>
                  <label style={{ fontSize: 11, fontWeight: 700, color: p.textSub, marginBottom: 6, display: "block" }}>Hyper-V Host</label>
                  <select value={targetDetail.host_id || ""} onChange={e => setTargetDetail({ host_id: parseInt(e.target.value), host_name: hvHosts.find(h => h.id === parseInt(e.target.value))?.hostname })} style={selectStyle}>
                    <option value="">-- Select Host --</option>
                    {hvHosts.map(h => <option key={h.id} value={h.id}>{h.hostname || h.ip}</option>)}
                  </select>
                  {hvHosts.length === 0 && <div style={{ fontSize: 12, color: p.yellow, marginTop: 8 }}>⚠️ No connected Hyper-V hosts found</div>}
                </>)}
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 16 }}>
              <button onClick={() => setStep(0)} style={btnOutline}>← Back</button>
              <button disabled={!targetPlatform || !Object.keys(targetDetail).length} onClick={() => setStep(2)}
                style={{ ...btn(), opacity: !targetPlatform || !Object.keys(targetDetail).length ? 0.4 : 1 }}>
                Continue → Pre-flight Check
              </button>
            </div>
          </div>
        )}

        {/* -------- STEP 3: Pre-flight -------- */}
        {step === 2 && (
          <div style={card}>
            <div style={{ fontSize: 18, fontWeight: 800, color: p.text, marginBottom: 4 }}>🔍 Pre-flight Compatibility Assessment</div>
            <div style={{ fontSize: 12, color: p.textMute, marginBottom: 20 }}>Checking {selCount} VM{selCount !== 1 ? "s" : ""} for migration readiness to {TARGETS.find(t => t.id === targetPlatform)?.label}.</div>

            {loadingPreflight ? <LoadDots p={p} /> : preflightResults && (<>
              {/* OCP Operator banner */}
              {targetPlatform === "openshift" && preflightResults.ocp_operator_found !== null && (
                <div style={{
                  padding: "12px 20px", borderRadius: 10, marginBottom: 16,
                  background: preflightResults.ocp_operator_found ? `${p.green}12` : `${p.red}12`,
                  border: `1px solid ${preflightResults.ocp_operator_found ? p.green : p.red}30`,
                  display: "flex", alignItems: "center", gap: 10,
                }}>
                  <span style={{ fontSize: 20 }}>{preflightResults.ocp_operator_found ? "✅" : "❌"}</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13, color: preflightResults.ocp_operator_found ? p.green : p.red }}>
                      {preflightResults.ocp_operator_found ? "OpenShift Virtualization operator detected" : "OpenShift Virtualization operator NOT found"}
                    </div>
                    <div style={{ fontSize: 11, color: p.textMute }}>
                      {preflightResults.ocp_operator_found ? "Cluster is ready for KubeVirt VM workloads" : "Install the operator before proceeding with migration"}
                    </div>
                  </div>
                </div>
              )}

              {/* Summary bar */}
              <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
                {[
                  { label: "Total", val: preflightResults.summary?.total, color: p.accent },
                  { label: "Pass", val: preflightResults.summary?.pass, color: p.green },
                  { label: "Warning", val: preflightResults.summary?.warning, color: p.yellow },
                  { label: "Fail", val: preflightResults.summary?.fail, color: p.red },
                ].map(s => (
                  <div key={s.label} style={{ padding: "10px 20px", borderRadius: 10, background: `${s.color}10`, border: `1px solid ${s.color}25`, minWidth: 90, textAlign: "center" }}>
                    <div style={{ fontSize: 22, fontWeight: 900, color: s.color }}>{s.val || 0}</div>
                    <div style={{ fontSize: 10, fontWeight: 600, color: p.textMute }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {/* Results table */}
              <div style={{ maxHeight: 380, overflowY: "auto", borderRadius: 10, border: `1px solid ${p.border}` }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead style={{ position: "sticky", top: 0, background: p.panelAlt, zIndex: 1 }}>
                    <tr>
                      <th style={thStyle}>VM Name</th>
                      <th style={thStyle}>CPU</th>
                      <th style={thStyle}>Disk Format</th>
                      <th style={thStyle}>Snapshots</th>
                      <th style={thStyle}>VM Tools</th>
                      <th style={thStyle}>Status</th>
                      <th style={thStyle}>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(preflightResults.results || []).map((r, i) => (
                      <tr key={i} style={{ background: i % 2 === 0 ? "transparent" : `${p.surface}80` }}>
                        <td style={{ ...tdStyle, fontWeight: 600 }}>{r.vm_name}</td>
                        <td style={tdStyle}><span style={{ color: r.cpu_compatible ? p.green : p.red }}>{r.cpu_compatible ? "✅" : "❌"}</span></td>
                        <td style={tdStyle}><span style={{ fontSize: 11 }}>{r.disk_format} → {r.target_format}</span></td>
                        <td style={tdStyle}><span style={{ color: r.snapshots_present ? p.yellow : p.green }}>{r.snapshots_present ? "⚠️ Yes" : "✅ None"}</span></td>
                        <td style={tdStyle}><span style={{ color: p.green }}>✅</span></td>
                        <td style={tdStyle}><span style={badge(r.overall === "pass" ? p.green : r.overall === "warning" ? p.yellow : p.red)}>{r.overall.toUpperCase()}</span></td>
                        <td style={{ ...tdStyle, fontSize: 12, fontWeight: 500, color: p.textMute, maxWidth: 300 }}>{(r.notes || []).join(" | ") || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 16 }}>
                <button onClick={() => setStep(1)} style={btnOutline}>← Back</button>
                <div style={{ display: "flex", gap: 10 }}>
                  <button onClick={doPreflight} style={btnOutline}>🔄 Re-run</button>
                  <button onClick={() => setStep(3)} style={btn()}>Continue → Mapping</button>
                </div>
              </div>
            </>)}
          </div>
        )}

        {/* -------- STEP 4: Mapping -------- */}
        {step === 3 && (
          <div style={card}>
            <div style={{ fontSize: 18, fontWeight: 800, color: p.text, marginBottom: 4 }}>🔗 Resource Mapping</div>
            <div style={{ fontSize: 12, color: p.textMute, marginBottom: 24 }}>Map source VMware networks and storage to the target platform.</div>

            {/* Network mapping */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: p.cyan, marginBottom: 10 }}>🌐 Network Mapping</div>
              <div style={{ borderRadius: 10, border: `1px solid ${p.border}`, overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>
                    <th style={thStyle}>Source (VMware Port Group)</th>
                    <th style={{ ...thStyle, textAlign: "center" }}>→</th>
                    <th style={thStyle}>Target Network</th>
                  </tr></thead>
                  <tbody>
                    {networkMap.map((m, i) => (
                      <tr key={i}>
                        <td style={tdStyle}><span style={{ fontWeight: 600 }}>{m.source}</span></td>
                        <td style={{ ...tdStyle, textAlign: "center", color: p.accent }}>➔</td>
                        <td style={tdStyle}>
                          <select value={m.target} onChange={e => { const nm = [...networkMap]; nm[i].target = e.target.value; setNetworkMap(nm); }} style={selectStyle}>
                            <option value="">-- Select --</option>
                            {targetNetworks.map(n => <option key={n.name} value={n.name}>{n.name}</option>)}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Storage mapping */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: p.purple, marginBottom: 10 }}>💾 Storage Mapping</div>
              <div style={{ borderRadius: 10, border: `1px solid ${p.border}`, overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead><tr>
                    <th style={thStyle}>Source (VMware Datastore)</th>
                    <th style={{ ...thStyle, textAlign: "center" }}>→</th>
                    <th style={thStyle}>Target Storage</th>
                  </tr></thead>
                  <tbody>
                    {storageMap.map((m, i) => (
                      <tr key={i}>
                        <td style={tdStyle}><span style={{ fontWeight: 600 }}>{m.source}</span></td>
                        <td style={{ ...tdStyle, textAlign: "center", color: p.purple }}>➔</td>
                        <td style={tdStyle}>
                          {targetPlatform === "hyperv" ? (
                            <input value={m.target} onChange={e => { const sm = [...storageMap]; sm[i].target = e.target.value; setStorageMap(sm); }} placeholder="e.g. D:\\VMs\\Disks" style={inputStyle} />
                          ) : (
                            <select value={m.target} onChange={e => { const sm = [...storageMap]; sm[i].target = e.target.value; setStorageMap(sm); }} style={selectStyle}>
                              <option value="">-- Select --</option>
                              {targetStorage.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
                            </select>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <button onClick={() => setStep(2)} style={btnOutline}>← Back</button>
              <button onClick={() => setStep(4)} style={btn()}>Continue → Review</button>
            </div>
          </div>
        )}

        {/* -------- STEP 5: Review -------- */}
        {step === 4 && (
          <div style={card}>
            <div style={{ fontSize: 18, fontWeight: 800, color: p.text, marginBottom: 20 }}>📋 Review & Create Migration Plan</div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ fontSize: 11, fontWeight: 700, color: p.textSub, marginBottom: 6, display: "block" }}>Plan Name *</label>
              <input value={planName} onChange={e => setPlanName(e.target.value)} placeholder="e.g. DC1 VMware to Nutanix - Batch 1" style={{ ...inputStyle, maxWidth: 500, fontSize: 14, padding: "10px 16px" }} />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16, marginBottom: 20 }}>
              {/* Source summary */}
              <div style={{ ...card, background: p.panelAlt, borderLeft: `4px solid ${p.accent}` }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: p.accent, marginBottom: 10 }}>📤 SOURCE</div>
                <div style={{ fontSize: 12, color: p.text, lineHeight: 2 }}>
                  <div><b>Platform:</b> VMware vSphere</div>
                  <div><b>vCenter:</b> {vcenters.find(v => v.id === selVC)?.name || selVC}</div>
                  <div><b>VMs:</b> {selCount} selected</div>
                  <div><b>Resources:</b> {totalCPU} vCPUs · {totalRAM.toFixed(1)} GB RAM · {totalDisk.toFixed(1)} GB Disk</div>
                </div>
              </div>

              {/* Target summary */}
              <div style={{ ...card, background: p.panelAlt, borderLeft: `4px solid ${TARGETS.find(t => t.id === targetPlatform)?.color || p.green}` }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: TARGETS.find(t => t.id === targetPlatform)?.color || p.green, marginBottom: 10 }}>🎯 TARGET</div>
                <div style={{ fontSize: 12, color: p.text, lineHeight: 2 }}>
                  <div><b>Platform:</b> {TARGETS.find(t => t.id === targetPlatform)?.label}</div>
                  <div><b>Destination:</b> {targetDetail.cluster_name || targetDetail.pc_name || targetDetail.host_name || "-"}</div>
                  <div><b>Migration Tool:</b> {{ openshift: "MTV (Migration Toolkit)", nutanix: "Nutanix Move", hyperv: "Manual VMDK→VHDX" }[targetPlatform] || "-"}</div>
                </div>
              </div>

              {/* Pre-flight summary */}
              <div style={{ ...card, background: p.panelAlt, borderLeft: `4px solid ${p.green}` }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: p.green, marginBottom: 10 }}>✅ PRE-FLIGHT</div>
                <div style={{ fontSize: 12, color: p.text, lineHeight: 2 }}>
                  <div><b>Pass:</b> <span style={{ color: p.green }}>{preflightResults?.summary?.pass || 0}</span></div>
                  <div><b>Warnings:</b> <span style={{ color: p.yellow }}>{preflightResults?.summary?.warning || 0}</span></div>
                  <div><b>Failures:</b> <span style={{ color: p.red }}>{preflightResults?.summary?.fail || 0}</span></div>
                </div>
              </div>
            </div>

            {/* Migration Options */}
            <div style={{ ...card, background: p.panelAlt, marginBottom: 20, border: `1.5px solid ${p.border}` }}>
              <div style={{ fontSize: 14, fontWeight: 800, color: p.accent, marginBottom: 16 }}>⚙️ Migration Options</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>

                {/* Cold / Warm toggle */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }} onClick={() => setMigWarm(!migWarm)}>
                  <div style={{ width: 40, height: 22, borderRadius: 11, background: migWarm ? "#f59e0b" : "#5b8def", transition: "background .2s", position: "relative" }}>
                    <div style={{ width: 18, height: 18, borderRadius: "50%", background: "#fff", position: "absolute", top: 2, left: migWarm ? 20 : 2, transition: "left .2s", boxShadow: "0 1px 3px #0003" }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>{migWarm ? "☀️ Warm Migration" : "❄️ Cold Migration"}</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>{migWarm ? "Live precopy, minimal downtime (requires CBT)" : "Power off source VM first, then transfer disks"}</div>
                  </div>
                </div>

                {/* Power on target */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migPowerOn} onChange={e => setMigPowerOn(e.target.checked)} style={{ width: 18, height: 18, accentColor: p.green }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>⚡ Power On After Migration</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Automatically start the VM on the target platform</div>
                  </div>
                </label>

                {/* Keep source */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migKeepSource} onChange={e => { setMigKeepSource(e.target.checked); if (e.target.checked) setMigDecomSource(false); }} style={{ width: 18, height: 18, accentColor: "#5b8def" }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>💾 Keep Source VM</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Retain source VM after migration (powered off)</div>
                  </div>
                </label>

                {/* Decommission source */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: migDecomSource ? `${p.red}10` : p.surface, border: `1px solid ${migDecomSource ? p.red + "40" : p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migDecomSource} onChange={e => { setMigDecomSource(e.target.checked); if (e.target.checked) setMigKeepSource(false); }} style={{ width: 18, height: 18, accentColor: p.red }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: migDecomSource ? p.red : p.text }}>🗑️ Decommission Source</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Remove source VM from vCenter after successful migration</div>
                  </div>
                </label>

                {/* Skip guest conversion */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migSkipConvert} onChange={e => setMigSkipConvert(e.target.checked)} style={{ width: 18, height: 18, accentColor: "#f59e0b" }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>⏩ Skip Guest Conversion</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Skip virt-v2v (faster, but may need manual virtio drivers)</div>
                  </div>
                </label>

                {/* Preserve IPs */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migPreserveIPs} onChange={e => setMigPreserveIPs(e.target.checked)} style={{ width: 18, height: 18, accentColor: "#06b6d4" }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>🌐 Preserve Static IPs</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>Keep VM IP addresses (requires bridge/Multus networking)</div>
                  </div>
                </label>

                {/* Pre-flight inspection */}
                <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, cursor: "pointer" }}>
                  <input type="checkbox" checked={migPreflight} onChange={e => setMigPreflight(e.target.checked)} style={{ width: 18, height: 18, accentColor: p.green }} />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>🔍 Run Pre-flight Inspection</div>
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 2 }}>MTV inspects VM compatibility before migration</div>
                  </div>
                </label>

                {/* Target Namespace (OpenShift only) */}
                {targetPlatform === "openshift" && (
                  <div style={{ padding: "10px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}` }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text, marginBottom: 6 }}>🎯 Target Namespace</div>
                    <input value={migTargetNS} onChange={e => setMigTargetNS(e.target.value)} placeholder="openshift-mtv" style={{ ...inputStyle, width: "100%" }} />
                    <div style={{ fontSize: 11, color: p.textSub, marginTop: 4 }}>OCP namespace where migrated VMs will be created</div>
                  </div>
                )}

                {/* Cutover Mode (Nutanix only) */}
                {targetPlatform === "nutanix" && (
                  <div style={{ padding: "12px 14px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, gridColumn: "1 / -1" }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: p.text, marginBottom: 10 }}>{String.fromCodePoint(0x2702, 0xFE0F)} Cutover Mode <span style={{fontSize:11,fontWeight:400,color:p.textSub}}>(when to switch over to target VM)</span></div>
                    <div style={{ display: "flex", gap: 10, marginBottom: 6 }}>
                      {[{val:"auto",icon:String.fromCodePoint(0x26A1),label:"Auto Cutover",desc:"Immediately after seeding completes (recommended)",color:"#22c55e"},
                        {val:"scheduled",icon:String.fromCodePoint(0x1F4C5),label:"Scheduled Cutover",desc:"Pick a date/time for cutover",color:"#f59e0b"},
                        {val:"manual",icon:String.fromCodePoint(0x1F5B1, 0xFE0F),label:"Manual Cutover",desc:"You trigger cutover from Move UI",color:"#8b5cf6"}
                      ].map(opt => (
                        <div key={opt.val} onClick={() => setMigCutoverMode(opt.val)}
                          style={{ flex: 1, padding: "10px 12px", borderRadius: 10, cursor: "pointer",
                            background: migCutoverMode === opt.val ? opt.color + "18" : p.panelAlt,
                            border: `2px solid ${migCutoverMode === opt.val ? opt.color : "transparent"}`,
                            transition: "all .2s" }}>
                          <div style={{ fontSize: 13, fontWeight: 700, color: migCutoverMode === opt.val ? opt.color : p.text }}>{opt.icon} {opt.label}</div>
                          <div style={{ fontSize: 11, color: p.textSub, marginTop: 3 }}>{opt.desc}</div>
                        </div>
                      ))}
                    </div>
                    {migCutoverMode === "scheduled" && (
                      <div style={{ marginTop: 8, padding: "8px 12px", borderRadius: 8, background: p.panelAlt }}>
                        <label style={{ fontSize: 12, fontWeight: 700, color: p.text, marginBottom: 4, display: "block" }}>Cutover Date/Time</label>
                        <input type="datetime-local" value={migCutoverDatetime} onChange={e => setMigCutoverDatetime(e.target.value)}
                          style={{ ...inputStyle, width: "100%", maxWidth: 280 }} />
                        <div style={{ fontSize: 11, color: "#f59e0b", marginTop: 4 }}>Seeding starts now. Cutover triggers at the scheduled time.</div>
                      </div>
                    )}
                    {migCutoverMode === "manual" && (
                      <div style={{ fontSize: 11, color: "#8b5cf6", marginTop: 4, padding: "6px 10px", borderRadius: 6, background: "#8b5cf610" }}>After seeding, open Move UI at https://172.16.146.117 to click Cutover.</div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Schedule & Notes */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: p.text, marginBottom: 6, display: "block" }}>📅 Schedule Migration (optional)</label>
                <input type="datetime-local" value={migSchedule} onChange={e => setMigSchedule(e.target.value)} style={{ ...inputStyle, width: "100%" }} />
                <div style={{ fontSize: 11, color: p.textSub, marginTop: 4 }}>Leave empty for manual execution after approval</div>
              </div>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: p.text, marginBottom: 6, display: "block" }}>📝 Notes / Change Ticket</label>
                <input value={migNotes} onChange={e => setMigNotes(e.target.value)} placeholder="e.g. CHG-12345 or JIRA-678" style={{ ...inputStyle, width: "100%" }} />
                <div style={{ fontSize: 11, color: p.textSub, marginTop: 4 }}>Reference ticket or migration notes</div>
              </div>
            </div>

            {/* Effort estimate */}
            <div style={{ padding: "12px 20px", borderRadius: 10, background: `${p.purple}10`, border: `1px solid ${p.purple}25`, marginBottom: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: p.purple }}>⏱️ Estimated Effort</div>
              <div style={{ fontSize: 11, color: p.textSub, marginTop: 4 }}>
                {totalDisk < 500 ? "Low (∼1-2 hours)" : totalDisk < 2000 ? "Medium (∼2-6 hours)" : "High (∼6-12+ hours)"} based on {totalDisk.toFixed(0)} GB total disk.
                Actual time depends on network throughput and target platform processing speed.
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <button onClick={() => setStep(3)} style={btnOutline}>← Back</button>
              <button onClick={savePlan} disabled={saving || !planName.trim()} style={{ ...btn(p.green), opacity: saving || !planName.trim() ? 0.5 : 1 }}>
                {saving ? "Saving..." : "🚀 Create Migration Plan"}
              </button>
            </div>
          </div>
        )}
      </>)}

      {/* ======================== PLANS TAB ======================== */}
      {tab === "plans" && (
        <div style={card}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ fontSize: 20, fontWeight: 900, color: p.text }}>{"📋"} Migration Plans</div>
            <button onClick={loadPlans} style={btnOutline}>{"🔄"} Refresh</button>
          </div>

          {loadingPlans ? <LoadDots p={p} /> : plans.length === 0 ? (
            <div style={{ textAlign: "center", padding: 60, color: p.textMute }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>{"📦"}</div>
              <div style={{ fontSize: 18, fontWeight: 800, marginBottom: 8, color: p.text }}>No migration plans yet</div>
              <div style={{ fontSize: 13, color: p.textSub }}>Create your first plan using the "New Migration" tab.</div>
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
                        <td style={{ ...tdStyle, fontWeight: 800, fontSize: 14 }}>{plan.plan_name}</td>
                        <td style={tdStyle}>VMware</td>
                        <td style={tdStyle}><span style={badge(TARGETS.find(t => t.id === plan.target_platform)?.color || p.grey)}>{TARGETS.find(t => t.id === plan.target_platform)?.label || plan.target_platform}</span></td>
                        <td style={tdStyle}>{Array.isArray(plan.vm_list) ? plan.vm_list.length : "-"}</td>
                        <td style={tdStyle}><span style={badge(sCfg.color)}>{sCfg.icon} {sCfg.label}</span></td>
                        <td style={tdStyle}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 80 }}>
                            <div style={{ flex: 1, height: 10, borderRadius: 5, background: `${p.textMute}22` }}>
                              <div style={{ height: "100%", borderRadius: 3, background: sCfg.color, width: `${pProgress}%`, transition: "width .5s ease" }} />
                            </div>
                            <span style={{ fontSize: 15, color: sCfg.color, fontWeight: 900, minWidth: 38, textShadow: `0 0 6px ${sCfg.color}30` }}>{pProgress}%</span>
                          </div>
                        </td>
                        <td style={{ ...tdStyle, fontSize: 13, fontWeight: 600 }}>{plan.created_at || "-"}</td>
                        <td style={tdStyle} onClick={e => e.stopPropagation()}>
                          <button onClick={() => delPlan(plan.id)} style={{ background: "transparent", border: "none", cursor: "pointer", color: p.red, fontWeight: 700, fontSize: 11 }}>{"🗑️"}</button>
                        </td>
                      </tr>
                      {expandedPlan === plan.id && (
                        <tr><td colSpan={8} style={{ padding: 0, background: p.panelAlt, borderBottom: `1px solid ${p.border}` }}>
                          <div style={{ padding: "16px 20px" }}>
                            <div style={{ display: "flex", alignItems: "center", margin: "0 0 16px", padding: "12px 16px", background: p.surface, borderRadius: 10, border: `1px solid ${p.border}` }}>
                              {PIPELINE.map((stg, i) => {
                                const sc = STATUS_CFG[stg];
                                const currentOrd = STATUS_CFG[plan.status]?.ord ?? -1;
                                const isReached = currentOrd >= sc.ord && currentOrd >= 0;
                                const isCurrent = plan.status === stg || (stg === "preflight_passed" && plan.status === "preflight_running");
                                return <Fragment key={stg}>
                                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
                                    <div style={{ width: 34, height: 34, borderRadius: "50%", background: isReached ? sc.color : `${p.textMute}22`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, border: isCurrent ? `2.5px solid ${sc.color}` : "2.5px solid transparent", boxShadow: isCurrent ? `0 0 12px ${sc.color}44` : "none", transition: "all .3s", animation: isCurrent && ["executing","migrating","validating","preflight_running"].includes(plan.status) ? "pulse 2s infinite" : "none" }}>{sc.icon}</div>
                                    <div style={{ fontSize: 11.5, marginTop: 4, color: isReached ? sc.color : p.textMute, fontWeight: isCurrent ? 800 : 600, textAlign: "center", letterSpacing: ".3px" }}>{sc.label}</div>
                                  </div>
                                  {i < PIPELINE.length - 1 && <div style={{ flex: 1.5, height: 3, borderRadius: 2, background: currentOrd > sc.ord && currentOrd >= 0 ? STATUS_CFG[PIPELINE[i+1]]?.color || p.textMute : `${p.textMute}22`, transition: "background .5s", marginBottom: 16 }} />}
                                </Fragment>;
                              })}
                              {["failed","cancelled","rolled_back","preflight_failed"].includes(plan.status) && (
                                <div style={{ marginLeft: 8, display: "flex", flexDirection: "column", alignItems: "center" }}>
                                  <div style={{ width: 34, height: 34, borderRadius: "50%", background: sCfg.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, border: `2.5px solid ${sCfg.color}`, boxShadow: `0 0 12px ${sCfg.color}44` }}>{sCfg.icon}</div>
                                  <div style={{ fontSize: 11.5, marginTop: 4, color: sCfg.color, fontWeight: 800 }}>{sCfg.label}</div>
                                </div>
                              )}
                            </div>
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, fontSize: 14.5, color: p.text, marginBottom: 14 }}>
                              <div><b>Migration Tool:</b> {plan.migration_tool || "-"}</div>
                              <div><b>Created By:</b> {plan.created_by || "-"}</div>
                              <div><b>Created:</b> {plan.created_at || "-"}</div>
                              {plan.approved_by && <div><b>Approved By:</b> {plan.approved_by} @ {plan.approved_at}</div>}
              {plan.notes && <div><b>Notes:</b> {plan.notes}</div>}
              {plan.notes && <div><b>Notes:</b> {plan.notes}</div>}
              {plan.notes && <div><b>Notes:</b> {plan.notes}</div>}
                              {plan.started_at && <div><b>Started:</b> {plan.started_at}</div>}
                              {plan.completed_at && <div><b>Completed:</b> {plan.completed_at}</div>}
                            </div>
                            {Array.isArray(plan.vm_list) && plan.vm_list.length > 0 && (
                              <div style={{ marginBottom: 14 }}>
                                <div style={{ fontSize: 13.5, fontWeight: 800, color: p.text, marginBottom: 8, textTransform: "uppercase", letterSpacing: ".5px" }}>VMs in this plan</div>
                                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                                  {plan.vm_list.map((vm, vi) => <div key={vi} style={{ padding: "7px 14px", borderRadius: 8, background: `${p.border}40`, fontSize: 13.5, fontWeight: 700, color: p.text }}>{vm.name || vm}</div>)}
                                </div>
                              </div>
                            )}
                            {["executing","migrating","validating"].includes(plan.status) && (
                              <div style={{ marginBottom: 14, padding: 12, borderRadius: 8, background: `${sCfg.color}08`, border: `1px solid ${sCfg.color}25` }}>
                                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 15, fontWeight: 800, marginBottom: 8 }}>
                                  <span style={{ color: sCfg.color, textShadow: `0 0 10px ${sCfg.color}50` }}>{sCfg.icon} {sCfg.label}</span>
                                  <span style={{ color: sCfg.color, fontWeight: 900, fontSize: 16 }}>{pProgress}% complete</span>
                                </div>
                                <div style={{ height: 20, borderRadius: 10, background: `${p.textMute}20` }}>
                                  <div style={{ height: "100%", borderRadius: 10, background: `linear-gradient(90deg, ${sCfg.color}, ${sCfg.color}cc)`, width: `${pProgress}%`, transition: "width 1s ease", boxShadow: `0 0 8px ${sCfg.color}40` }} />
                                </div>
                              </div>
                            )}
                            {actions.length > 0 && (
                              <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
                                {actions.map((act, ai) => (
                                  <button key={ai} onClick={() => act.confirm ? (confirm("Are you sure?") && act.fn()) : act.fn()} style={{ padding: "10px 20px", borderRadius: 8, border: `1px solid ${act.color}`, background: `${act.color}15`, color: act.color, fontWeight: 700, fontSize: 13.5, cursor: "pointer", transition: "all .15s" }} onMouseEnter={e => { e.target.style.background = act.color; e.target.style.color = "#fff"; }} onMouseLeave={e => { e.target.style.background = `${act.color}12`; e.target.style.color = act.color; }}>{act.label}</button>
                                ))}
                              </div>
                            )}
                            {(() => {
                              const events = (pollingPlan === plan.id && liveEvents.length > 0) ? liveEvents : (plan.event_log || []);
                              if (!events.length) return null;
                              return (
                                <div style={{ borderRadius: 8, border: `1px solid ${p.border}`, overflow: "hidden" }}>
                                  <div style={{ padding: "12px 16px", background: `${p.border}33`, fontSize: 15, fontWeight: 800, color: p.text }}>{"📜"} Activity Log ({events.length})</div>
                                  <div style={{ maxHeight: 200, overflowY: "auto", padding: "6px 0" }} ref={el => { if (el) el.scrollTop = el.scrollHeight; }}>
                                    {events.map((ev, ei) => (
                                      <div key={ei} style={{ padding: "5px 14px", fontSize: 13.5, color: p.text, display: "flex", gap: 10, borderBottom: `1px solid ${p.border}10` }}>
                                        <span style={{ color: p.textSub || p.textMute, fontFamily: "monospace", whiteSpace: "nowrap", minWidth: 155, fontWeight: 600, fontSize: 12.5 }}>{ev.ts}</span>
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
