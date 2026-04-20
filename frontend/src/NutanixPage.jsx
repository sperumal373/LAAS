import { useState, useEffect, useCallback } from "react";
import {
  fetchNutanixPCs, createNutanixPC, updateNutanixPC, deleteNutanixPC,
  testNutanixPC, fetchNutanixOverview, fetchNutanixClusters,
  fetchNutanixVMs, fetchNutanixHosts, fetchNutanixStorage,
  fetchNutanixAlerts, fetchNutanixNetworks,
  fetchNutanixImages, submitNutanixVMRequest,
  nutanixVMPower, nutanixVMSnapshot,
} from "./api";

// ── Shared helpers (code-split: must be defined locally) ──────────────
function LoadState({ msg }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
                  justifyContent: "center", padding: 48, gap: 14 }}>
      <div className="spinner" />
      <span style={{ fontSize: 13, color: "#475569" }}>{msg || "Loading…"}</span>
    </div>
  );
}
function ErrState({ msg, onRetry }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
                  justifyContent: "center", padding: 40, gap: 12 }}>
      <div style={{ fontSize: 36 }}>⚠️</div>
      <div style={{ fontWeight: 600, color: "#ef4444" }}>Connection Error</div>
      <div style={{ fontSize: 13, color: "#475569", textAlign: "center", maxWidth: 340 }}>{msg}</div>
      <button className="btn btn-danger" onClick={onRetry}>↺ Retry</button>
    </div>
  );
}

// ── Utility functions ─────────────────────────────────────────────────
function _fmtBytes(b) {
  if (b == null || b === 0) return "—";
  const gib = b / 1073741824;
  if (gib >= 1) return `${gib.toFixed(1)} GiB`;
  return `${(b / 1048576).toFixed(0)} MiB`;
}
function _pct(used, total) {
  if (!total) return 0;
  return Math.round((used / total) * 100);
}
function _ago(iso) {
  if (!iso) return "—";
  const d = Math.floor((Date.now() - new Date(iso)) / 86400000);
  if (d < 1) return "<1d";
  if (d < 30) return `${d}d`;
  return `${Math.floor(d / 30)}mo`;
}

// ── Mini components ───────────────────────────────────────────────────
function NtxBar({ pct, color }) {
  const c = color || (pct > 85 ? "#ef4444" : pct > 65 ? "#f59e0b" : "#10b981");
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 3, background: "#1e293b", overflow: "hidden" }}>
        <div style={{ width: `${Math.min(100, pct || 0)}%`, height: "100%", background: c, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 11, color: c, fontWeight: 600, minWidth: 34 }}>{pct || 0}%</span>
    </div>
  );
}
function PowerBadge({ state }) {
  const on  = state?.toUpperCase() === "ON";
  const off = state?.toUpperCase() === "OFF" || state?.toUpperCase() === "POWERED_OFF";
  const c   = on ? "#10b981" : off ? "#ef4444" : "#f59e0b";
  const lbl = on ? "ON" : off ? "OFF" : state || "—";
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4,
                   background: `${c}18`, border: `1px solid ${c}40`, color: c }}>
      {lbl}
    </span>
  );
}
function SeverityBadge({ severity }) {
  const sc = { critical: "#ef4444", warning: "#f59e0b", info: "#3b82f6" };
  const c = sc[severity] || "#64748b";
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4,
                   background: `${c}18`, border: `1px solid ${c}40`, color: c,
                   textTransform: "uppercase" }}>
      {severity || "info"}
    </span>
  );
}
function StateBadge({ state }) {
  const ok  = state === "COMPLETE" || state === "NORMAL" || state === "STABLE";
  const err = state === "ERROR" || state === "FAULT";
  const c   = ok ? "#10b981" : err ? "#ef4444" : "#f59e0b";
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4,
                   background: `${c}18`, border: `1px solid ${c}40`, color: c }}>
      {state || "—"}
    </span>
  );
}
function FieldRow({ label, value, mono, p }) {
  return (
    <div style={{ background: p.surface, borderRadius: 6, padding: "5px 10px",
                  border: `1px solid ${p.border}` }}>
      <div style={{ fontSize: 9, color: p.textMute, fontWeight: 700, textTransform: "uppercase",
                    letterSpacing: ".5px", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 12, fontWeight: 500, wordBreak: "break-all",
                    fontFamily: mono ? "monospace" : "inherit" }}>{value || "—"}</div>
    </div>
  );
}

// ── Add / Edit Prism Central Modal ────────────────────────────────────
function PCModal({ mode, initial, onClose, onSaved, p }) {
  const [form, setForm] = useState(
    initial
      ? { name: initial.name, host: initial.host, username: initial.username || "",
          password: "", site: initial.site || "DC", description: initial.description || "" }
      : { name: "", host: "", username: "", password: "", site: "DC", description: "" }
  );
  const [busy, setBusy] = useState(false);
  const [err,  setErr]  = useState(null);
  const [showPw, setShowPw] = useState(false);

  const inp = (field) => ({
    value: form[field],
    onChange: (e) => setForm((f) => ({ ...f, [field]: e.target.value })),
    style: { width: "100%", padding: "8px 10px", borderRadius: 7, fontSize: 13,
             background: p.surface, border: `1px solid ${p.border}`, color: p.text,
             outline: "none", boxSizing: "border-box" },
  });

  async function save() {
    if (!form.name.trim() || !form.host.trim()) {
      setErr("Name and Host/IP are required"); return;
    }
    if (mode === "add" && (!form.username.trim() || !form.password.trim())) {
      setErr("Username and Password are required"); return;
    }
    setBusy(true); setErr(null);
    try {
      const payload = { ...form };
      if (mode === "edit" && !payload.password) delete payload.password;
      if (mode === "add") await createNutanixPC(payload);
      else                await updateNutanixPC(initial.id, payload);
      onSaved();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  }

  const fieldLbl = (t) => (
    <div style={{ fontSize: 12, color: p.textSub, fontWeight: 600, marginBottom: 4 }}>{t}</div>
  );

  return (
    <div className="modal-backdrop" style={{ position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,.65)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14,
                    padding: 28, width: "100%", maxWidth: 520, maxHeight: "90vh", overflowY: "auto" }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 34, height: 34, borderRadius: 9, background: "linear-gradient(135deg,#024DA1,#0066cc)",
                          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>🟦</div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                {mode === "add" ? "Add Prism Central" : `Edit — ${initial?.name}`}
              </div>
              <div style={{ fontSize: 11, color: p.textMute }}>Nutanix Prism Central credentials</div>
            </div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: p.textMute,
                                             cursor: "pointer", fontSize: 20, padding: 4 }}>✕</button>
        </div>

        {err && (
          <div style={{ marginBottom: 14, padding: "8px 12px", borderRadius: 7,
                        background: `${p.red}15`, border: `1px solid ${p.red}35`,
                        color: p.red, fontSize: 13 }}>{err}</div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <div style={{ gridColumn: "1/-1" }}>
            {fieldLbl("Display Name *")}
            <input {...inp("name")} placeholder="e.g. DC-PC-01" />
          </div>
          <div style={{ gridColumn: "1/-1" }}>
            {fieldLbl("Host / IP Address *")}
            <input {...inp("host")} placeholder="10.0.0.1  (port 9440 assumed)" />
          </div>
          <div>
            {fieldLbl("Username *")}
            <input {...inp("username")} placeholder="admin" autoComplete="off" />
          </div>
          <div>
            {fieldLbl(mode === "edit" ? "Password (leave blank to keep)" : "Password *")}
            <div style={{ position: "relative" }}>
              <input {...inp("password")} type={showPw ? "text" : "password"}
                     placeholder={mode === "edit" ? "••••••" : "Enter password"} autoComplete="new-password"
                     style={{ ...inp("password").style, paddingRight: 36 }} />
              <button onClick={() => setShowPw((s) => !s)}
                style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                         background: "none", border: "none", cursor: "pointer", color: p.textMute, fontSize: 14 }}>
                {showPw ? "🙈" : "👁️"}
              </button>
            </div>
          </div>
          <div>
            {fieldLbl("Site")}
            <select {...inp("site")} style={{ ...inp("site").style }}>
              <option value="DC">DC (Primary)</option>
              <option value="DR">DR (Disaster Recovery)</option>
            </select>
          </div>
          <div>
            {fieldLbl("Description")}
            <input {...inp("description")} placeholder="Optional note" />
          </div>
        </div>

        <div style={{ marginTop: 10, padding: "8px 12px", borderRadius: 7, fontSize: 11,
                      background: `${p.cyan}10`, border: `1px solid ${p.cyan}25`, color: p.cyan }}>
          💡 Prism Central REST API will be accessed at <strong>https://&lt;host&gt;:9440</strong>
        </div>

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 20 }}>
          <button className="btn" onClick={onClose}
            style={{ background: p.surface, border: `1px solid ${p.border}`, color: p.textSub }}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>
            {busy ? "⏳ Saving…" : mode === "add" ? "+ Add Prism Central" : "💾 Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── VM Power Confirm Modal ────────────────────────────────────────────
function VMPowerModal({ vm, action, onClose, onConfirm, p }) {
  const actionMeta = {
    ON:     { label: "Power On",  icon: "▶️",  color: "#10b981", desc: "Start the VM" },
    OFF:    { label: "Power Off", icon: "⏹️",  color: "#ef4444", desc: "Force power off" },
    REBOOT: { label: "Reboot",    icon: "🔄",  color: "#f59e0b", desc: "Soft reboot the VM" },
  };
  const m = actionMeta[action] || actionMeta.ON;
  const [busy, setBusy] = useState(false);
  async function confirm() {
    setBusy(true);
    await onConfirm(action);
    setBusy(false);
    onClose();
  }
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.65)",
                  display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14,
                    padding: 28, width: "100%", maxWidth: 420 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 20 }}>
          <div style={{ fontSize: 36 }}>{m.icon}</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
              {m.label}: <span style={{ color: m.color }}>{vm.name}</span>
            </div>
            <div style={{ fontSize: 13, color: p.textMute }}>{m.desc}</div>
          </div>
        </div>
        <div style={{ padding: "10px 14px", borderRadius: 8, background: `${m.color}12`,
                      border: `1px solid ${m.color}30`, fontSize: 13, color: m.color, marginBottom: 20 }}>
          ⚠️ This action will be submitted to Prism Central immediately.
        </div>
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn" onClick={onClose}
            style={{ background: p.surface, border: `1px solid ${p.border}`, color: p.textSub }}>
            Cancel
          </button>
          <button className="btn" onClick={confirm} disabled={busy}
            style={{ background: m.color, border: "none", color: "#fff", fontWeight: 700 }}>
            {busy ? "⏳ Submitting…" : `Confirm ${m.label}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── VM Snapshot Modal ─────────────────────────────────────────────────
function VMSnapshotModal({ vm, pcId, onClose, onDone, p }) {
  const dflt = `snap-${vm.name}-${new Date().toISOString().slice(0, 10)}`;
  const [name, setName] = useState(dflt);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  async function create() {
    if (!name.trim()) return;
    setBusy(true); setResult(null);
    const r = await nutanixVMSnapshot(pcId, vm.uuid, name.trim());
    setResult(r);
    setBusy(false);
    if (r.success) setTimeout(onDone, 1500);
  }
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.65)",
                  display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14,
                    padding: 28, width: "100%", maxWidth: 440 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>📸 Create Snapshot</div>
            <div style={{ fontSize: 12, color: p.textMute, marginTop: 2 }}>VM: <strong>{vm.name}</strong></div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: p.textMute,
                                             cursor: "pointer", fontSize: 20 }}>✕</button>
        </div>
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 12, color: p.textSub, fontWeight: 600, marginBottom: 6 }}>Snapshot Name</div>
          <input value={name} onChange={(e) => setName(e.target.value)}
            style={{ width: "100%", padding: "8px 10px", borderRadius: 7, fontSize: 13,
                     background: p.surface, border: `1px solid ${p.border}`, color: p.text,
                     outline: "none", boxSizing: "border-box" }} />
        </div>
        {result && (
          <div style={{ marginBottom: 14, padding: "8px 12px", borderRadius: 7,
                        background: result.success ? `${p.green}12` : `${p.red}12`,
                        border: `1px solid ${result.success ? p.green : p.red}35`,
                        color: result.success ? p.green : p.red, fontSize: 13 }}>
            {result.success ? "✅" : "❌"} {result.message}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn" onClick={onClose}
            style={{ background: p.surface, border: `1px solid ${p.border}`, color: p.textSub }}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={create} disabled={busy || !name.trim()}>
            {busy ? "⏳ Creating…" : "📸 Create Snapshot"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Tab: Overview ─────────────────────────────────────────────────────
function TabOverview({ overview, p }) {
  if (!overview) return <div style={{ padding: 40, textAlign: "center", color: p.textMute, fontSize: 13 }}>Click Refresh to load overview.</div>;
  if (overview.error) return <ErrState msg={overview.error} onRetry={() => {}} />;

  const kpis = [
    { icon: "🟦", label: "Clusters",        val: overview.clusters,               sub: "managed by PC",       color: "#024DA1" },
    { icon: "💻", label: "Virtual Machines", val: overview.vms?.total || 0,        sub: `${overview.vms?.running || 0} running · ${overview.vms?.off || 0} off`, color: overview.vms?.running > 0 ? "#10b981" : "#64748b" },
    { icon: "🖥️", label: "Hosts (Nodes)",    val: overview.hosts,                  sub: `${overview.total_vcpus || 0} total vCPUs`, color: "#06b6d4" },
    { icon: "💾", label: "Total Memory",     val: `${overview.total_memory_gib || 0} GiB`, sub: "across all hosts",  color: "#a855f7" },
    { icon: "🔴", label: "Critical Alerts", val: overview.alerts?.critical || 0,  sub: `${overview.alerts?.warning || 0} warnings`, color: overview.alerts?.critical > 0 ? "#ef4444" : "#10b981" },
    { icon: "📊", label: "Total Alerts",    val: overview.alerts?.total || 0,     sub: "unresolved",           color: overview.alerts?.total > 0 ? "#f59e0b" : "#10b981" },
  ];

  return (
    <div className="g-gap">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: 12 }}>
        {kpis.map((k, i) => (
          <div key={i} className="card" style={{ padding: "16px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span style={{ fontSize: 22 }}>{k.icon}</span>
              <span style={{ fontSize: 12, color: p.textMute, fontWeight: 600 }}>{k.label}</span>
            </div>
            <div style={{ fontSize: 30, fontWeight: 800, color: k.color, lineHeight: 1 }}>{k.val}</div>
            <div style={{ fontSize: 11, color: p.textMute, marginTop: 5 }}>{k.sub}</div>
          </div>
        ))}
      </div>
      <div style={{ padding: "12px 16px", borderRadius: 10, background: `#024DA110`,
                    border: `1px solid #024DA130`, fontSize: 12, color: "#4a90d9" }}>
        💡 Click a tab above to fetch live data from Prism Central API.
        Data is fetched on demand to avoid unnecessary API calls.
      </div>
    </div>
  );
}

// ── Tab: Clusters ─────────────────────────────────────────────────────
function TabClusters({ clusters, p }) {
  const [q, setQ] = useState("");
  const rows = clusters.filter((c) =>
    !q || [c.name, c.state, c.hypervisor, c.external_ip, c.aos_version].some(
      (s) => s?.toLowerCase().includes(q.toLowerCase())
    )
  );
  return (
    <div className="g-gap">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: p.text }}>AHV Clusters</span>
        <span style={{ fontSize: 12, color: p.textMute }}>{rows.length} / {clusters.length}</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter clusters…"
          style={{ marginLeft: "auto", padding: "5px 10px", borderRadius: 7, fontSize: 12, width: 200,
                   background: p.surface, border: `1px solid ${p.border}`, color: p.text, outline: "none" }} />
      </div>
      {rows.length === 0
        ? <div style={{ textAlign: "center", padding: 40, color: p.textMute, fontSize: 13 }}>No clusters found</div>
        : <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(360px,1fr))", gap: 12 }}>
            {rows.map((c) => (
              <div key={c.uuid} style={{ background: p.panel, border: `1px solid ${p.border}`,
                                         borderRadius: 12, padding: "14px 18px" }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14, color: "#024DA1", marginBottom: 2 }}>{c.name}</div>
                    <div style={{ fontSize: 11, color: p.textMute, fontFamily: "monospace" }}>{c.external_ip || "—"}</div>
                  </div>
                  <StateBadge state={c.state} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                  {[
                    { label: "AOS Version",  val: c.aos_version,  color: "#024DA1" },
                    { label: "Hypervisor",   val: c.hypervisor },
                    { label: "Nodes",        val: c.num_nodes },
                    { label: "Redundancy",   val: `RF-${c.redundancy}` },
                    { label: "NCC Version",  val: c.ncc_version },
                    { label: "Timezone",     val: c.timezone },
                  ].map((f, i) => (
                    <div key={i} style={{ background: p.surface, borderRadius: 6, padding: "5px 10px",
                                          border: `1px solid ${p.border}` }}>
                      <div style={{ fontSize: 9, color: p.textMute, fontWeight: 700, textTransform: "uppercase",
                                    letterSpacing: ".5px", marginBottom: 2 }}>{f.label}</div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: f.color || p.text }}>{f.val || "—"}</div>
                    </div>
                  ))}
                </div>
                {c.data_services_ip && (
                  <div style={{ marginTop: 8, fontSize: 11, color: p.textMute }}>
                    Data Services IP: <code style={{ color: p.cyan }}>{c.data_services_ip}</code>
                  </div>
                )}
              </div>
            ))}
          </div>
      }
    </div>
  );
}

// ── Tab: VMs ──────────────────────────────────────────────────────────
function TabVMs({ vms, pcId, canAct, p }) {
  const [q,         setQ]         = useState("");
  const [stateF,    setStateF]    = useState("all");
  const [clusterF,  setClusterF]  = useState("all");
  const [powerModal,setPowerModal] = useState(null);   // { vm, action }
  const [snapModal,  setSnapModal] = useState(null);   // vm
  const [actionMsg,  setActionMsg] = useState(null);

  const clusters = [...new Set(vms.map((v) => v.cluster_name).filter(Boolean))].sort();
  const states   = [...new Set(vms.map((v) => v.power_state).filter(Boolean))].sort();

  const rows = vms.filter((v) => {
    if (stateF   !== "all" && v.power_state !== stateF)    return false;
    if (clusterF !== "all" && v.cluster_name !== clusterF)  return false;
    if (q && ![v.name, v.ip_display, v.cluster_name, v.project, v.guest_os].some(
      (s) => s?.toLowerCase().includes(q.toLowerCase()))) return false;
    return true;
  });

  async function doPower(action) {
    if (!powerModal) return;
    const r = await nutanixVMPower(pcId, powerModal.vm.uuid, action);
    setActionMsg(r);
    setPowerModal(null);
    setTimeout(() => setActionMsg(null), 4000);
  }

  const TH = ({ ch }) => (
    <th style={{ padding: "8px 12px", fontWeight: 700, fontSize: 11, textAlign: "left",
                 textTransform: "uppercase", letterSpacing: ".5px", color: p.textMute,
                 borderBottom: `1px solid ${p.border}`, whiteSpace: "nowrap", background: p.panelAlt || p.surface }}>
      {ch}
    </th>
  );

  return (
    <div className="g-gap">
      {/* Filters */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Virtual Machines</span>
        <span style={{ fontSize: 12, color: p.textMute }}>{rows.length} / {vms.length}</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search VMs…"
          style={{ padding: "5px 10px", borderRadius: 7, fontSize: 12, width: 180,
                   background: p.surface, border: `1px solid ${p.border}`, color: p.text, outline: "none" }} />
        <select value={stateF} onChange={(e) => setStateF(e.target.value)}
          style={{ padding: "5px 8px", borderRadius: 7, fontSize: 12,
                   background: p.surface, border: `1px solid ${p.border}`, color: p.text }}>
          <option value="all">All States</option>
          {states.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        {clusters.length > 1 && (
          <select value={clusterF} onChange={(e) => setClusterF(e.target.value)}
            style={{ padding: "5px 8px", borderRadius: 7, fontSize: 12,
                     background: p.surface, border: `1px solid ${p.border}`, color: p.text }}>
            <option value="all">All Clusters</option>
            {clusters.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        )}
      </div>

      {actionMsg && (
        <div style={{ padding: "8px 14px", borderRadius: 8, fontSize: 13,
                      background: actionMsg.success ? `${p.green}12` : `${p.red}12`,
                      border: `1px solid ${actionMsg.success ? p.green : p.red}30`,
                      color:   actionMsg.success ? p.green : p.red }}>
          {actionMsg.success ? "✅" : "❌"} {actionMsg.message}
        </div>
      )}

      {rows.length === 0
        ? <div style={{ textAlign: "center", padding: 40, color: p.textMute, fontSize: 13 }}>No VMs found</div>
        : <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <TH ch="Name" /><TH ch="State" /><TH ch="vCPUs" /><TH ch="RAM" />
                  <TH ch="IP Address" /><TH ch="Cluster" /><TH ch="Project" />
                  {canAct && <TH ch="Actions" />}
                </tr>
              </thead>
              <tbody>
                {rows.map((v) => (
                  <tr key={v.uuid} style={{ borderBottom: `1px solid ${p.border}20` }}>
                    <td style={{ padding: "8px 12px" }}>
                      <div style={{ fontWeight: 600, fontSize: 13, wordBreak: "break-all" }}>{v.name}</div>
                      {v.guest_os && <div style={{ fontSize: 10, color: p.textMute }}>{v.guest_os}</div>}
                    </td>
                    <td style={{ padding: "8px 12px" }}><PowerBadge state={v.power_state} /></td>
                    <td style={{ padding: "8px 12px", fontSize: 13, color: p.cyan }}>{v.num_vcpus}</td>
                    <td style={{ padding: "8px 12px", fontSize: 13 }}>{v.memory_gib} GiB</td>
                    <td style={{ padding: "8px 12px", fontSize: 12, fontFamily: "monospace", color: p.text }}>
                      {v.ip_display}
                    </td>
                    <td style={{ padding: "8px 12px", fontSize: 12, color: p.textSub }}>{v.cluster_name || "—"}</td>
                    <td style={{ padding: "8px 12px", fontSize: 12, color: p.textSub }}>{v.project || "—"}</td>
                    {canAct && (
                      <td style={{ padding: "8px 12px" }}>
                        <div style={{ display: "flex", gap: 4, flexWrap: "nowrap" }}>
                          {v.power_state?.toUpperCase() !== "ON" && (
                            <button title="Power On"
                              onClick={() => setPowerModal({ vm: v, action: "ON" })}
                              style={{ background: "#10b98115", border: "1px solid #10b98135",
                                       borderRadius: 5, padding: "3px 8px", cursor: "pointer",
                                       fontSize: 11, color: "#10b981", fontWeight: 700 }}>▶ On</button>
                          )}
                          {v.power_state?.toUpperCase() === "ON" && (
                            <button title="Reboot"
                              onClick={() => setPowerModal({ vm: v, action: "REBOOT" })}
                              style={{ background: "#f59e0b15", border: "1px solid #f59e0b35",
                                       borderRadius: 5, padding: "3px 8px", cursor: "pointer",
                                       fontSize: 11, color: "#f59e0b", fontWeight: 700 }}>🔄</button>
                          )}
                          {v.power_state?.toUpperCase() === "ON" && (
                            <button title="Power Off"
                              onClick={() => setPowerModal({ vm: v, action: "OFF" })}
                              style={{ background: "#ef444415", border: "1px solid #ef444435",
                                       borderRadius: 5, padding: "3px 8px", cursor: "pointer",
                                       fontSize: 11, color: "#ef4444", fontWeight: 700 }}>⏹</button>
                          )}
                          <button title="Snapshot"
                            onClick={() => setSnapModal(v)}
                            style={{ background: "#6366f115", border: "1px solid #6366f135",
                                     borderRadius: 5, padding: "3px 8px", cursor: "pointer",
                                     fontSize: 11, color: "#6366f1", fontWeight: 700 }}>📸</button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      }

      {powerModal && (
        <VMPowerModal vm={powerModal.vm} action={powerModal.action}
          onClose={() => setPowerModal(null)} onConfirm={doPower} p={p} />
      )}
      {snapModal && (
        <VMSnapshotModal vm={snapModal} pcId={pcId}
          onClose={() => setSnapModal(null)} onDone={() => setSnapModal(null)} p={p} />
      )}
    </div>
  );
}

// ── Tab: Hosts ────────────────────────────────────────────────────────
function TabHosts({ hosts, p }) {
  const [q, setQ] = useState("");
  const rows = hosts.filter((h) =>
    !q || [h.name, h.cvm_ip, h.hypervisor_ip, h.cluster_name, h.cpu_model, h.serial].some(
      (s) => s?.toLowerCase().includes(q.toLowerCase())
    )
  );
  return (
    <div className="g-gap">
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Hypervisor Hosts</span>
        <span style={{ fontSize: 12, color: p.textMute }}>{rows.length} / {hosts.length}</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter hosts…"
          style={{ marginLeft: "auto", padding: "5px 10px", borderRadius: 7, fontSize: 12, width: 200,
                   background: p.surface, border: `1px solid ${p.border}`, color: p.text, outline: "none" }} />
      </div>
      {rows.length === 0
        ? <div style={{ padding: 40, textAlign: "center", color: p.textMute, fontSize: 13 }}>No hosts found</div>
        : <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(360px,1fr))", gap: 12 }}>
            {rows.map((h) => (
              <div key={h.uuid} style={{ background: p.panel, border: `1px solid ${h.maintenance ? "#f59e0b50" : p.border}`,
                                         borderRadius: 12, padding: "14px 18px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 14, color: "#024DA1", marginBottom: 2 }}>{h.name}</div>
                    {h.cluster_name && <div style={{ fontSize: 11, color: p.textMute }}>Cluster: {h.cluster_name}</div>}
                  </div>
                  <div style={{ display: "flex", gap: 5 }}>
                    <StateBadge state={h.state} />
                    {h.maintenance && (
                      <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4,
                                     background: "#f59e0b18", border: "1px solid #f59e0b40", color: "#f59e0b" }}>
                        MAINTENANCE
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 8 }}>
                  {[
                    { label: "CPU Model",        val: h.cpu_model,          span: 2 },
                    { label: "Sockets × Cores",  val: h.num_cpu_sockets && h.num_cpu_cores ? `${h.num_cpu_sockets} × ${h.num_cpu_cores / h.num_cpu_sockets}` : "—" },
                    { label: "Total vCPUs",      val: h.total_vcpus },
                    { label: "Memory",           val: `${h.memory_gib} GiB` },
                    { label: "VMs Running",      val: h.num_vms,            color: "#10b981" },
                    { label: "Hypervisor",       val: h.hypervisor_type },
                    { label: "HV Version",       val: h.hypervisor_version, span: 2 },
                    { label: "CVM IP",           val: h.cvm_ip,             mono: true },
                    { label: "AHV IP",           val: h.hypervisor_ip,      mono: true },
                    { label: "IPMI IP",          val: h.ipmi_ip,            mono: true },
                    { label: "Serial",           val: h.serial,             mono: true },
                  ].map((f, i) => (
                    <div key={i} style={{ gridColumn: f.span === 2 ? "1/-1" : undefined,
                                          background: p.surface, borderRadius: 6, padding: "5px 10px",
                                          border: `1px solid ${p.border}` }}>
                      <div style={{ fontSize: 9, color: p.textMute, fontWeight: 700, textTransform: "uppercase",
                                    letterSpacing: ".5px", marginBottom: 2 }}>{f.label}</div>
                      <div style={{ fontSize: 12, fontWeight: 500, color: f.color || p.text,
                                    fontFamily: f.mono ? "monospace" : "inherit" }}>{f.val || "—"}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
      }
    </div>
  );
}

// ── Tab: Storage ──────────────────────────────────────────────────────
function TabStorage({ containers, p }) {
  const [q, setQ] = useState("");
  const rows = containers.filter((c) =>
    !("error" in c) &&
    (!q || [c.name, c.cluster_name].some((s) => s?.toLowerCase().includes(q.toLowerCase())))
  );
  if (containers[0]?.error) {
    return <ErrState msg={containers[0].error} onRetry={() => {}} />;
  }
  return (
    <div className="g-gap">
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Storage Containers</span>
        <span style={{ fontSize: 12, color: p.textMute }}>{rows.length} container{rows.length !== 1 ? "s" : ""}</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…"
          style={{ marginLeft: "auto", padding: "5px 10px", borderRadius: 7, fontSize: 12, width: 200,
                   background: p.surface, border: `1px solid ${p.border}`, color: p.text, outline: "none" }} />
      </div>
      {rows.length === 0
        ? <div style={{ padding: 40, textAlign: "center", color: p.textMute, fontSize: 13 }}>No storage containers found</div>
        : <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(340px,1fr))", gap: 12 }}>
            {rows.map((sc, i) => {
              const usedPct = sc.used_pct || 0;
              const barColor = usedPct > 85 ? "#ef4444" : usedPct > 65 ? "#f59e0b" : "#10b981";
              return (
                <div key={i} style={{ background: p.panel, border: `1px solid ${p.border}`,
                                       borderRadius: 12, padding: "14px 18px" }}>
                  <div style={{ fontWeight: 700, fontSize: 14, color: "#024DA1", marginBottom: 4 }}>{sc.name}</div>
                  {sc.cluster_name && <div style={{ fontSize: 11, color: p.textMute, marginBottom: 8 }}>Cluster: {sc.cluster_name}</div>}
                  <div style={{ marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11,
                                  color: p.textMute, marginBottom: 4 }}>
                      <span>Used: {_fmtBytes(sc.usage_bytes)}</span>
                      <span>Free: {_fmtBytes(sc.free_bytes)}</span>
                      <span>Total: {_fmtBytes(sc.capacity_bytes)}</span>
                    </div>
                    <NtxBar pct={usedPct} color={barColor} />
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                    {[
                      { label: "RF",          val: `RF-${sc.replication_factor}` },
                      sc.compression && { label: "Compression", val: "✅" },
                      sc.dedup        && { label: "Dedup",       val: "✅" },
                      sc.erasure_code !== "OFF" && { label: "EC",  val: sc.erasure_code },
                    ].filter(Boolean).map((tag, ti) => (
                      <span key={ti} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10,
                                              background: `#024DA112`, border: `1px solid #024DA130`,
                                              color: "#4a90d9" }}>
                        {tag.label}: {tag.val}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
      }
    </div>
  );
}

// ── Tab: Networks ─────────────────────────────────────────────────────
function TabNetworks({ networks, p }) {
  const [q, setQ] = useState("");
  const rows = networks.filter((n) =>
    !q || [n.name, n.cidr, n.gateway, n.cluster_name, String(n.vlan_id)].some(
      (s) => s?.toLowerCase().includes(q.toLowerCase())
    )
  );
  return (
    <div className="g-gap">
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Networks / Subnets</span>
        <span style={{ fontSize: 12, color: p.textMute }}>{rows.length} / {networks.length}</span>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter networks…"
          style={{ marginLeft: "auto", padding: "5px 10px", borderRadius: 7, fontSize: 12, width: 200,
                   background: p.surface, border: `1px solid ${p.border}`, color: p.text, outline: "none" }} />
      </div>
      {rows.length === 0
        ? <div style={{ padding: 40, textAlign: "center", color: p.textMute, fontSize: 13 }}>No networks found</div>
        : <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(320px,1fr))", gap: 12 }}>
            {rows.map((n) => (
              <div key={n.uuid} style={{ background: p.panel, border: `1px solid ${p.border}`,
                                          borderRadius: 12, padding: "14px 18px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <div style={{ fontWeight: 700, fontSize: 14, color: "#024DA1" }}>{n.name}</div>
                  <div style={{ display: "flex", gap: 5 }}>
                    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4,
                                   background: "#3b82f618", border: "1px solid #3b82f640", color: "#3b82f6" }}>
                      {n.subnet_type}
                    </span>
                    {n.dhcp_enabled && (
                      <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4,
                                     background: "#10b98118", border: "1px solid #10b98140", color: "#10b981" }}>
                        DHCP
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                  {[
                    { label: "VLAN ID",  val: n.vlan_id || 0 },
                    { label: "Cluster",  val: n.cluster_name },
                    { label: "CIDR",     val: n.cidr,    mono: true, span: n.gateway ? 1 : 2 },
                    n.gateway && { label: "Gateway", val: n.gateway, mono: true },
                    n.pool_list?.length && { label: "IP Pool", val: n.pool_list.join(", "), mono: true, span: 2 },
                  ].filter(Boolean).map((f, i) => (
                    <div key={i} style={{ gridColumn: f.span === 2 ? "1/-1" : undefined,
                                          background: p.surface, borderRadius: 6, padding: "5px 10px",
                                          border: `1px solid ${p.border}` }}>
                      <div style={{ fontSize: 9, color: p.textMute, fontWeight: 700, textTransform: "uppercase",
                                    letterSpacing: ".5px", marginBottom: 2 }}>{f.label}</div>
                      <div style={{ fontSize: 12, fontWeight: 500, fontFamily: f.mono ? "monospace" : "inherit" }}>
                        {f.val || "—"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
      }
    </div>
  );
}

// ── Tab: Alerts ───────────────────────────────────────────────────────
function TabAlerts({ alerts, p }) {
  const [q,      setQ]      = useState("");
  const [sevF,   setSevF]   = useState("all");
  const rows = alerts.filter((a) => {
    if (a.error) return true;
    if (sevF !== "all" && a.severity !== sevF) return false;
    if (q && ![a.title, a.message, a.entity_name, a.entity_type, a.alert_type].some(
      (s) => s?.toLowerCase().includes(q.toLowerCase()))) return false;
    return true;
  });
  const critical = alerts.filter((a) => a.severity === "critical").length;
  const warning  = alerts.filter((a) => a.severity === "warning").length;
  return (
    <div className="g-gap">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Alerts</span>
        <span style={{ fontSize: 12, color: p.textMute }}>{rows.length} / {alerts.length}</span>
        {critical > 0 && (
          <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 10,
                         background: "#ef444418", border: "1px solid #ef444440", color: "#ef4444" }}>
            🔴 {critical} critical
          </span>
        )}
        {warning > 0 && (
          <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 10,
                         background: "#f59e0b18", border: "1px solid #f59e0b40", color: "#f59e0b" }}>
            ⚠️ {warning} warnings
          </span>
        )}
        <select value={sevF} onChange={(e) => setSevF(e.target.value)}
          style={{ padding: "5px 8px", borderRadius: 7, fontSize: 12, marginLeft: "auto",
                   background: p.surface, border: `1px solid ${p.border}`, color: p.text }}>
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search alerts…"
          style={{ padding: "5px 10px", borderRadius: 7, fontSize: 12, width: 180,
                   background: p.surface, border: `1px solid ${p.border}`, color: p.text, outline: "none" }} />
      </div>
      {rows.length === 0
        ? <div style={{ padding: 40, textAlign: "center", color: "#10b981", fontSize: 13 }}>✅ No alerts found</div>
        : <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {rows.map((a, i) => {
              const sevC = { critical: "#ef4444", warning: "#f59e0b", info: "#3b82f6" }[a.severity] || "#64748b";
              return (
                <div key={i} style={{ background: p.panel, border: `1px solid ${sevC}30`,
                                       borderLeft: `3px solid ${sevC}`, borderRadius: 10,
                                       padding: "12px 16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                    <div style={{ fontWeight: 600, fontSize: 13, color: p.text, flex: 1, paddingRight: 12 }}>
                      {a.title || a.alert_type || "Alert"}
                    </div>
                    <div style={{ display: "flex", gap: 5, flexShrink: 0 }}>
                      <SeverityBadge severity={a.severity} />
                      {a.acknowledged && (
                        <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 4,
                                       background: "#64748b18", color: "#64748b" }}>ACK</span>
                      )}
                    </div>
                  </div>
                  {a.message && <div style={{ fontSize: 12, color: p.textMute, marginBottom: 6 }}>{a.message}</div>}
                  <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                    {a.entity_name && (
                      <span style={{ fontSize: 11, color: p.cyan }}>
                        🖥️ {a.entity_type && <span style={{ color: p.textMute }}>{a.entity_type}: </span>}
                        {a.entity_name}
                      </span>
                    )}
                    {a.created_at && (
                      <span style={{ fontSize: 11, color: p.textMute }}>{_ago(a.created_at)} ago</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
      }
    </div>
  );
}

// ── Export helpers ────────────────────────────────────────────────────
function exportVMsCSV(vms) {
  const hdr = ["Name", "Power State", "vCPUs", "Memory GiB", "IP", "Cluster", "Project", "Guest OS"];
  const rows = vms.map((v) => [v.name, v.power_state, v.num_vcpus, v.memory_gib,
                                v.ip_display, v.cluster_name, v.project, v.guest_os]);
  const csv = [hdr, ...rows].map((r) =>
    r.map((c) => `"${String(c == null ? "" : c).replace(/"/g, '""')}"`).join(",")
  ).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a"); a.href = url; a.download = "nutanix-vms.csv"; a.click();
}

// ── Request VM Wizard ─────────────────────────────────────────────────
function TabRequestVM({ pcs, selPC: initialPC, p, currentUser }) {
  const STEPS    = ["PC & Cluster", "VM Config", "Storage", "Networks", "Preview"];
  const DISK_BUS = { DISK: ["SCSI", "SATA", "IDE", "PCI"], CDROM: ["IDE", "SATA"] };
  const NTX_BLUE = "#024DA1";

  const [step,     setStep]     = useState(0);
  const [wizPC,    setWizPC]    = useState(initialPC);
  const [cluster,  setCluster]  = useState({ uuid: "", name: "", nodes: 0, hypervisor: "" });
  const [vmName,   setVmName]   = useState("");
  const [numVCPU,  setNumVCPU]  = useState(2);
  const [numCores, setNumCores] = useState(1);
  const [memGib,   setMemGib]   = useState(4);
  const [disks, setDisks] = useState([
    { id: 1, type: "DISK", bus_type: "SCSI", size_gib: 50, size_unit: "GiB",
      sc_uuid: "", sc_name: "", image_uuid: "", image_name: "", clone_image: false },
  ]);
  const [nics, setNics] = useState([
    { id: 1, subnet_uuid: "", subnet_name: "", vlan_id: 0, cidr: "", gateway: "", dhcp: false },
  ]);
  const [notes,      setNotes]      = useState("");
  const [clusters,   setClusters]   = useState([]);
  const [networks,   setNetworks]   = useState([]);
  const [storage,    setStorage]    = useState([]);
  const [images,     setImages]     = useState([]);
  const [loadingRes, setLoadingRes] = useState(false);
  const [resErr,     setResErr]     = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [result,     setResult]     = useState(null);

  // Fetch resources when PC is selected
  useEffect(() => {
    if (!wizPC) return;
    let cancelled = false;
    async function fetchAll() {
      setLoadingRes(true); setResErr(null);
      setClusters([]); setNetworks([]); setStorage([]); setImages([]);
      try {
        const [cls, nets, stor, imgs] = await Promise.all([
          fetchNutanixClusters(wizPC.id),
          fetchNutanixNetworks(wizPC.id),
          fetchNutanixStorage(wizPC.id),
          fetchNutanixImages(wizPC.id),
        ]);
        if (cancelled) return;
        setClusters(cls || []);
        setNetworks(nets || []);
        setStorage((stor || []).filter(s => !s.error));
        setImages((imgs || []).filter(i => !i.error));
      } catch (e) { if (!cancelled) setResErr(e.message); }
      if (!cancelled) setLoadingRes(false);
    }
    fetchAll();
    return () => { cancelled = true; };
  }, [wizPC?.id]);

  // Reset cluster on PC change
  useEffect(() => {
    setCluster({ uuid: "", name: "", nodes: 0, hypervisor: "" });
    setNics([{ id: 1, subnet_uuid: "", subnet_name: "", vlan_id: 0, cidr: "", gateway: "", dhcp: false }]);
  }, [wizPC?.id]);

  // Disk helpers
  function addDisk(type) {
    const id = Date.now();
    setDisks(d => [...d, type === "CDROM"
      ? { id, type: "CDROM", bus_type: "IDE",  size_gib: 0,  size_unit: "GiB", sc_uuid: "", sc_name: "", image_uuid: "", image_name: "", clone_image: false }
      : { id, type: "DISK",  bus_type: "SCSI", size_gib: 50, size_unit: "GiB", sc_uuid: "", sc_name: "", image_uuid: "", image_name: "", clone_image: false }
    ]);
  }
  function removeDisk(id)       { setDisks(d => d.filter(x => x.id !== id)); }
  function patchDisk(id, patch) { setDisks(d => d.map(x => x.id === id ? { ...x, ...patch } : x)); }

  // NIC helpers
  function addNic()             { setNics(n => [...n, { id: Date.now(), subnet_uuid: "", subnet_name: "", vlan_id: 0, cidr: "", gateway: "", dhcp: false }]); }
  function removeNic(id)        { setNics(n => n.filter(x => x.id !== id)); }
  function patchNic(id, patch)  { setNics(n => n.map(x => x.id === id ? { ...x, ...patch } : x)); }

  function canNext() {
    if (step === 0) return !!wizPC && !!cluster.uuid;
    if (step === 1) return vmName.trim().length > 0;
    if (step === 2) return disks.length > 0;
    if (step === 3) return nics.length > 0 && !!nics[0].subnet_uuid;
    return true;
  }

  function resetWizard() {
    setStep(0); setVmName(""); setNumVCPU(2); setNumCores(1); setMemGib(4);
    setCluster({ uuid: "", name: "", nodes: 0, hypervisor: "" });
    setDisks([{ id: 1, type: "DISK", bus_type: "SCSI", size_gib: 50, size_unit: "GiB", sc_uuid: "", sc_name: "", image_uuid: "", image_name: "", clone_image: false }]);
    setNics([{ id: 1, subnet_uuid: "", subnet_name: "", vlan_id: 0, cidr: "", gateway: "", dhcp: false }]);
    setNotes(""); setResult(null);
  }

  async function submit() {
    setSubmitting(true); setResult(null);
    try {
      const ntx_disks = disks.map(d => ({
        type: d.type, bus_type: d.bus_type,
        size_bytes: d.type === "DISK" ? d.size_gib * (d.size_unit === "GiB" ? 1073741824 : 1048576) : 0,
        storage_container_uuid: d.sc_uuid || "",
        storage_container_name: d.sc_name || "",
        image_uuid:        d.clone_image ? (d.image_uuid || "") : "",
        image_name:        d.clone_image ? (d.image_name || "") : "",
        clone_from_image:  !!d.clone_image,
      }));
      const ntx_nics = nics.map(n => ({ subnet_uuid: n.subnet_uuid, subnet_name: n.subnet_name, vlan_id: n.vlan_id }));
      const total_disk_gb = disks.reduce((acc, d) => acc + (d.type === "DISK" ? (d.size_unit === "GiB" ? d.size_gib : d.size_gib / 1024) : 0), 0);
      const req = await submitNutanixVMRequest({
        vm_name: vmName, cpu: numVCPU, num_cores_per_vcpu: numCores, ram_gb: memGib,
        disk_gb: Math.ceil(total_disk_gb) || 0,
        ntx_pc_id: wizPC.id, ntx_pc_name: wizPC.name,
        ntx_cluster_uuid: cluster.uuid, ntx_cluster_name: cluster.name,
        ntx_disks: JSON.stringify(ntx_disks), ntx_nics: JSON.stringify(ntx_nics),
        notes,
      });
      setResult({ ok: true, req });
    } catch (e) { setResult({ ok: false, message: e.message }); }
    setSubmitting(false);
  }

  const inpStyle = { width: "100%", padding: "8px 10px", borderRadius: 7, fontSize: 13, background: p.surface, border: `1px solid ${p.border}`, color: p.text, outline: "none", boxSizing: "border-box" };
  const lbl = (txt, req) => <div style={{ fontSize: 12, fontWeight: 600, color: p.textSub, marginBottom: 5 }}>{txt}{req && <span style={{ color: "#ef4444", marginLeft: 2 }}>*</span>}</div>;

  // ── Success screen ──────────────────────────────────────────────────
  if (result?.ok) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "40px 20px", gap: 16 }}>
        <div style={{ fontSize: 60 }}>✅</div>
        <div style={{ fontWeight: 800, fontSize: 22, color: p.green }}>Request Submitted!</div>
        <div style={{ padding: "14px 24px", borderRadius: 12, background: `${p.green}12`, border: `1px solid ${p.green}30`, textAlign: "center", minWidth: 280 }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: "#4a90d9", letterSpacing: 1 }}>{result.req?.req_number}</div>
          <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>{result.req?.vm_name}</div>
          <div style={{ fontSize: 12, color: p.textMute, marginTop: 4 }}>Pending admin approval &nbsp;·&nbsp; 🟦 {wizPC?.name} › {cluster.name}</div>
        </div>
        <div style={{ fontSize: 13, color: p.textMute, textAlign: "center", maxWidth: 400, lineHeight: 1.7 }}>
          Your VM request is queued for admin review.<br/>Navigate to <strong>VM Requests</strong> in the sidebar to track its status.
        </div>
        <button className="btn btn-primary" onClick={resetWizard}>📝 Submit Another Request</button>
      </div>
    );
  }

  // ── Wizard layout ───────────────────────────────────────────────────
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Step indicator */}
      <div style={{ display: "flex", alignItems: "center", padding: "12px 16px", borderRadius: 10, background: p.surface, border: `1px solid ${p.border}`, gap: 0, overflowX: "auto" }}>
        {STEPS.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 0, flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 10px", borderRadius: 8, background: i === step ? `${NTX_BLUE}15` : "transparent" }}>
              <div style={{ width: 24, height: 24, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0, background: i < step ? p.green : i === step ? NTX_BLUE : p.surface, color: i <= step ? "#fff" : p.textMute, border: `2px solid ${i < step ? p.green : i === step ? NTX_BLUE : p.border}` }}>
                {i < step ? "✓" : i + 1}
              </div>
              <span style={{ fontSize: 12, fontWeight: i === step ? 700 : 400, color: i === step ? "#4a90d9" : i < step ? p.green : p.textMute, whiteSpace: "nowrap" }}>{s}</span>
            </div>
            {i < STEPS.length - 1 && <div style={{ width: 24, height: 2, flexShrink: 0, background: i < step ? p.green : p.border, borderRadius: 1 }} />}
          </div>
        ))}
      </div>

      {/* Step content card */}
      <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14, padding: "22px 26px", minHeight: 300 }}>

        {/* ── STEP 0: PC & Cluster ────────────────────────────── */}
        {step === 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>🟦 Prism Central & Element</div>
              <div style={{ fontSize: 13, color: p.textMute }}>Select which Prism Central and AHV cluster the VM will be deployed on.</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                {lbl("Prism Central", true)}
                <select value={wizPC?.id || ""} onChange={e => { const pc = pcs.find(x => x.id === Number(e.target.value)); setWizPC(pc || null); }} style={inpStyle}>
                  <option value="">— Select Prism Central —</option>
                  {pcs.map(pc => <option key={pc.id} value={pc.id}>{pc.name} [{pc.site}] — {pc.host}</option>)}
                </select>
                {wizPC && <div style={{ fontSize: 11, color: p.textMute, marginTop: 4 }}>Status: <span style={{ color: wizPC.status === "connected" ? p.green : p.red, fontWeight: 600 }}>{wizPC.status || "unknown"}</span></div>}
              </div>
              <div>
                {lbl("Prism Element (Cluster)", true)}
                {!wizPC
                  ? <div style={{ padding: "8px 10px", borderRadius: 7, background: p.surface, border: `1px solid ${p.border}`, fontSize: 12, color: p.textMute }}>Select a Prism Central first</div>
                  : loadingRes
                  ? <div style={{ padding: "8px 10px", borderRadius: 7, background: p.surface, border: `1px solid ${p.border}`, fontSize: 12, color: p.textMute }}>⏳ Loading clusters…</div>
                  : <select value={cluster.uuid} onChange={e => { const cl = clusters.find(c => c.uuid === e.target.value); setCluster({ uuid: e.target.value, name: cl?.name || "", nodes: cl?.num_nodes || 0, hypervisor: cl?.hypervisor || "" }); }} style={inpStyle}>
                      <option value="">— Select Cluster —</option>
                      {clusters.map(c => <option key={c.uuid} value={c.uuid}>{c.name} · {c.hypervisor} · {c.num_nodes} node{c.num_nodes !== 1 ? "s" : ""}</option>)}
                    </select>
                }
                {resErr && <div style={{ fontSize: 11, color: p.red, marginTop: 4 }}>⚠️ {resErr}</div>}
              </div>
            </div>
            {wizPC && cluster.uuid && !loadingRes && (
              <div style={{ padding: "10px 16px", borderRadius: 10, background: `${NTX_BLUE}10`, border: `1px solid ${NTX_BLUE}28`, fontSize: 12 }}>
                <div style={{ color: "#4a90d9", fontWeight: 600, marginBottom: 4 }}>📋 {wizPC.name} › {cluster.name}</div>
                <div style={{ color: p.textMute, display: "flex", gap: 16, flexWrap: "wrap" }}>
                  <span>{clusters.length} cluster{clusters.length !== 1 ? "s" : ""}</span>
                  <span>{networks.length} network{networks.length !== 1 ? "s" : ""}</span>
                  <span>{storage.length} storage container{storage.length !== 1 ? "s" : ""}</span>
                  <span>{images.length} image{images.length !== 1 ? "s" : ""} in image service</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── STEP 1: VM Config ───────────────────────────────── */}
        {step === 1 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>⚙️ VM Configuration</div>
              <div style={{ fontSize: 13, color: p.textMute }}>Define VM name and compute resources.</div>
            </div>
            <div>
              {lbl("VM Name", true)}
              <input value={vmName} onChange={e => setVmName(e.target.value)} placeholder="e.g. APP-SRV-01" style={inpStyle} maxLength={64} />
              <div style={{ fontSize: 11, color: p.textMute, marginTop: 3 }}>{vmName.length}/64 characters · Use alphanumerics and hyphens</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
              <div>
                {lbl("vCPUs (Sockets)", true)}
                <select value={numVCPU} onChange={e => setNumVCPU(Number(e.target.value))} style={inpStyle}>
                  {[1,2,4,6,8,12,16,24,32].map(n => <option key={n} value={n}>{n} vCPU{n > 1 ? "s" : ""}</option>)}
                </select>
              </div>
              <div>
                {lbl("Cores per vCPU")}
                <select value={numCores} onChange={e => setNumCores(Number(e.target.value))} style={inpStyle}>
                  {[1,2,4,8].map(n => <option key={n} value={n}>{n} core{n > 1 ? "s" : ""}</option>)}
                </select>
                <div style={{ fontSize: 11, color: p.textMute, marginTop: 3 }}>= {numVCPU * numCores} logical CPU{numVCPU * numCores > 1 ? "s" : ""}</div>
              </div>
              <div>
                {lbl("Memory", true)}
                <select value={memGib} onChange={e => setMemGib(Number(e.target.value))} style={inpStyle}>
                  {[1,2,4,6,8,12,16,24,32,48,64,96,128].map(n => <option key={n} value={n}>{n} GiB</option>)}
                </select>
              </div>
            </div>
            <div style={{ padding: "10px 14px", borderRadius: 8, background: `${p.cyan}10`, border: `1px solid ${p.cyan}20`, fontSize: 12, color: p.cyan }}>
              💻 <strong>{cluster.name}</strong> on <strong>{wizPC?.name}</strong> &nbsp;·&nbsp; <strong>{numVCPU}×{numCores}</strong> = <strong>{numVCPU*numCores}</strong> logical CPUs &nbsp;·&nbsp; <strong>{memGib} GiB RAM</strong>
            </div>
          </div>
        )}

        {/* ── STEP 2: Storage ─────────────────────────────────── */}
        {step === 2 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>💾 Storage Configuration</div>
                <div style={{ fontSize: 13, color: p.textMute }}>Configure virtual disks and CD-ROMs following Nutanix AHV conventions.</div>
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                <button onClick={() => addDisk("DISK")} style={{ padding: "5px 12px", borderRadius: 7, fontSize: 12, cursor: "pointer", fontWeight: 600, background: `${NTX_BLUE}15`, border: `1px solid ${NTX_BLUE}40`, color: "#4a90d9" }}>+ Disk</button>
                <button onClick={() => addDisk("CDROM")} style={{ padding: "5px 12px", borderRadius: 7, fontSize: 12, cursor: "pointer", fontWeight: 600, background: `${p.yellow}15`, border: `1px solid ${p.yellow}40`, color: p.yellow }}>+ CD-ROM</button>
              </div>
            </div>

            {disks.length === 0 && <div style={{ textAlign: "center", padding: "28px 0", color: p.textMute, fontSize: 13 }}>No storage devices. Add a disk or CD-ROM above.</div>}

            {disks.map((d, idx) => (
              <div key={d.id} style={{ background: p.surface, border: `1px solid ${d.type === "CDROM" ? p.yellow + "50" : p.border}`, borderLeft: `3px solid ${d.type === "CDROM" ? p.yellow : NTX_BLUE}`, borderRadius: 10, padding: "14px 16px" }}>
                {/* Header */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <span style={{ fontSize: 18 }}>{d.type === "CDROM" ? "💿" : "💾"}</span>
                  <span style={{ fontWeight: 700, fontSize: 13, color: d.type === "CDROM" ? p.yellow : "#4a90d9" }}>{d.type === "CDROM" ? "CD-ROM" : "Disk"} {idx + 1}</span>
                  <span style={{ fontSize: 11, padding: "1px 7px", borderRadius: 4, fontWeight: 600, background: d.type === "CDROM" ? `${p.yellow}15` : `${NTX_BLUE}12`, border: `1px solid ${d.type === "CDROM" ? p.yellow + "40" : NTX_BLUE + "30"}`, color: d.type === "CDROM" ? p.yellow : "#4a90d9" }}>{d.type}</span>
                  <div style={{ flex: 1 }} />
                  {disks.length > 1 && <button onClick={() => removeDisk(d.id)} style={{ padding: "2px 9px", borderRadius: 5, fontSize: 11, cursor: "pointer", background: `${p.red}12`, border: `1px solid ${p.red}30`, color: p.red, fontWeight: 700 }}>✕</button>}
                </div>

                {/* Fields grid */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 10 }}>
                  <div>
                    {lbl("Bus Type")}
                    <select value={d.bus_type} onChange={e => patchDisk(d.id, { bus_type: e.target.value })} style={inpStyle}>
                      {DISK_BUS[d.type].map(bt => <option key={bt} value={bt}>{bt}</option>)}
                    </select>
                    {d.type === "CDROM" && <div style={{ fontSize: 10, color: p.textMute, marginTop: 3 }}>IDE recommended for max compatibility</div>}
                  </div>
                  {d.type === "DISK" && (
                    <div>
                      {lbl("Capacity", true)}
                      <div style={{ display: "flex", gap: 5 }}>
                        <input type="number" value={d.size_gib} min={1} max={65536} onChange={e => patchDisk(d.id, { size_gib: Math.max(1, Number(e.target.value)) })} style={{ ...inpStyle, width: "65%", boxSizing: "border-box", flex: "none" }} />
                        <select value={d.size_unit} onChange={e => patchDisk(d.id, { size_unit: e.target.value })} style={{ ...inpStyle, width: "35%", boxSizing: "border-box", flex: "none" }}>
                          <option value="GiB">GiB</option>
                          <option value="MiB">MiB</option>
                        </select>
                      </div>
                    </div>
                  )}
                  {d.type === "DISK" && (
                    <div>
                      {lbl("Storage Container")}
                      <select value={d.sc_uuid} onChange={e => { const sc = storage.find(s => s.uuid === e.target.value || s.name === e.target.value); patchDisk(d.id, { sc_uuid: sc?.uuid || e.target.value, sc_name: sc?.name || "" }); }} style={inpStyle}>
                        <option value="">— Default Container —</option>
                        {storage.map(sc => <option key={sc.name} value={sc.uuid || sc.name}>{sc.name} ({sc.used_pct || 0}% used)</option>)}
                      </select>
                    </div>
                  )}
                </div>

                {/* Clone from Image Service toggle */}
                <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${p.border}30` }}>
                  <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", userSelect: "none" }}>
                    <div onClick={() => patchDisk(d.id, { clone_image: !d.clone_image, image_uuid: d.clone_image ? "" : d.image_uuid, image_name: d.clone_image ? "" : d.image_name })}
                      style={{ width: 38, height: 22, borderRadius: 11, cursor: "pointer", background: d.clone_image ? NTX_BLUE : p.border, position: "relative", transition: "background .2s", flexShrink: 0 }}>
                      <div style={{ position: "absolute", top: 3, width: 16, height: 16, borderRadius: "50%", background: "#fff", transition: "left .2s", left: d.clone_image ? 19 : 3 }} />
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 600, color: p.textSub }}>Clone from Image Service</span>
                    {d.type === "CDROM" && <span style={{ fontSize: 11, color: p.textMute }}>(mount ISO image)</span>}
                  </label>
                  {d.clone_image && (
                    <div style={{ marginTop: 10 }}>
                      {lbl(d.type === "CDROM" ? "Select ISO Image" : "Select Disk Image")}
                      <select value={d.image_uuid} onChange={e => { const img = images.find(i => i.uuid === e.target.value); patchDisk(d.id, { image_uuid: e.target.value, image_name: img?.name || "" }); }} style={inpStyle}>
                        <option value="">— Select Image from Image Service —</option>
                        {images.map(img => (
                          <option key={img.uuid} value={img.uuid}>
                            {img.name}{img.image_type === "ISO_IMAGE" ? " [ISO]" : " [Disk]"}{img.size_bytes ? ` · ${_fmtBytes(img.size_bytes)}` : ""}
                          </option>
                        ))}
                      </select>
                      {images.length === 0 && <div style={{ fontSize: 11, color: p.yellow, marginTop: 4 }}>⚠️ No images found. Upload images to Prism Central image service first.</div>}
                      {d.image_uuid && <div style={{ fontSize: 11, color: p.green, marginTop: 3 }}>✓ Selected: {d.image_name}</div>}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {disks.some(d => d.type === "DISK") && (
              <div style={{ textAlign: "right", fontSize: 12, color: p.textMute }}>
                Total: <strong style={{ color: p.text }}>{disks.filter(d => d.type === "DISK").reduce((s, d) => s + (d.size_unit === "GiB" ? d.size_gib : d.size_gib / 1024), 0).toFixed(1)} GiB</strong> disk capacity
              </div>
            )}
          </div>
        )}

        {/* ── STEP 3: Networks ────────────────────────────────── */}
        {step === 3 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>🌐 Network Configuration</div>
                <div style={{ fontSize: 13, color: p.textMute }}>Attach virtual NICs to subnets/VLANs managed by Prism Central.</div>
              </div>
              <button onClick={addNic} style={{ padding: "5px 12px", borderRadius: 7, fontSize: 12, cursor: "pointer", fontWeight: 600, flexShrink: 0, background: `${p.green}15`, border: `1px solid ${p.green}40`, color: p.green }}>+ Add NIC</button>
            </div>

            {nics.map((n, idx) => {
              const netInfo = networks.find(x => x.uuid === n.subnet_uuid);
              return (
                <div key={n.id} style={{ background: p.surface, border: `1px solid ${p.border}`, borderLeft: `3px solid ${p.green}`, borderRadius: 10, padding: "14px 16px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                    <span style={{ fontSize: 18 }}>🔌</span>
                    <span style={{ fontWeight: 700, fontSize: 13, color: p.green }}>NIC {idx + 1}</span>
                    <div style={{ flex: 1 }} />
                    {nics.length > 1 && <button onClick={() => removeNic(n.id)} style={{ padding: "2px 9px", borderRadius: 5, fontSize: 11, cursor: "pointer", background: `${p.red}12`, border: `1px solid ${p.red}30`, color: p.red, fontWeight: 700 }}>✕</button>}
                  </div>
                  <div>
                    {lbl("Network / Subnet", true)}
                    <select value={n.subnet_uuid} onChange={e => { const net = networks.find(x => x.uuid === e.target.value); patchNic(n.id, { subnet_uuid: e.target.value, subnet_name: net?.name || "", vlan_id: net?.vlan_id || 0, cidr: net?.cidr || "", gateway: net?.gateway || "", dhcp: net?.dhcp_enabled || false }); }} style={inpStyle}>
                      <option value="">— Select Network —</option>
                      {networks.map(net => <option key={net.uuid} value={net.uuid}>{net.name} · VLAN {net.vlan_id || 0}{net.cidr ? ` · ${net.cidr}` : ""}{net.dhcp_enabled ? " · DHCP" : ""}</option>)}
                    </select>
                    {netInfo && (
                      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 6, fontSize: 11, color: p.textMute }}>
                        {netInfo.cidr    && <span>📡 CIDR: <code style={{ color: p.cyan }}>{netInfo.cidr}</code></span>}
                        {netInfo.gateway && <span>🛡️ GW: <code style={{ color: p.cyan }}>{netInfo.gateway}</code></span>}
                        {netInfo.dhcp_enabled && <span style={{ color: p.green }}>✅ DHCP Enabled</span>}
                        <span>VLAN {netInfo.vlan_id || 0}</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            <div style={{ padding: "8px 14px", borderRadius: 8, background: `${p.green}10`, border: `1px solid ${p.green}25`, fontSize: 12, color: p.green }}>
              🌐 VM will have <strong>{nics.length} NIC{nics.length !== 1 ? "s" : ""}</strong> attached.
            </div>
          </div>
        )}

        {/* ── STEP 4: Preview ─────────────────────────────────── */}
        {step === 4 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>🔍 Review & Submit</div>
              <div style={{ fontSize: 13, color: p.textMute }}>Review your configuration before submitting for admin approval.</div>
            </div>

            <div style={{ border: `1px solid ${NTX_BLUE}35`, borderRadius: 12, overflow: "hidden" }}>
              {/* Card header */}
              <div style={{ background: `${NTX_BLUE}18`, padding: "14px 20px", borderBottom: `1px solid ${NTX_BLUE}25`, display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 42, height: 42, borderRadius: 10, background: `linear-gradient(135deg,${NTX_BLUE},#0066cc)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, flexShrink: 0 }}>💻</div>
                <div>
                  <div style={{ fontWeight: 800, fontSize: 18, color: "#4a90d9" }}>{vmName}</div>
                  <div style={{ fontSize: 12, color: p.textMute }}>Nutanix VM Request — Pending Admin Approval</div>
                </div>
                <div style={{ marginLeft: "auto", textAlign: "right" }}>
                  <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 5, background: `${NTX_BLUE}18`, border: `1px solid ${NTX_BLUE}30`, color: "#4a90d9" }}>🟦 Nutanix AHV</span>
                </div>
              </div>

              <div style={{ padding: "16px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                {/* Infrastructure */}
                <div style={{ gridColumn: "1/-1", paddingBottom: 12, borderBottom: `1px solid ${p.border}20` }}>
                  <div style={{ fontSize: 10, color: p.textMute, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 6 }}>Infrastructure</div>
                  <div style={{ display: "flex", gap: 14, flexWrap: "wrap", fontSize: 12, color: p.textSub }}>
                    <span>PC: <strong style={{ color: "#4a90d9" }}>{wizPC?.name}</strong></span>
                    <span>›</span>
                    <span>Cluster: <strong style={{ color: p.text }}>{cluster.name}</strong></span>
                    {cluster.hypervisor && <span style={{ color: p.textMute }}>Hypervisor: {cluster.hypervisor}</span>}
                  </div>
                </div>

                {/* Compute */}
                <div>
                  <div style={{ fontSize: 10, color: p.textMute, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 8 }}>Compute</div>
                  {[["vCPUs", `${numVCPU} socket${numVCPU>1?"s":""}`], ["Cores/Socket", numCores], ["Logical CPUs", numVCPU*numCores], ["Memory", `${memGib} GiB`]].map(([k,v]) => (
                    <div key={k} style={{ display: "flex", gap: 8, marginBottom: 5, fontSize: 12 }}>
                      <span style={{ color: p.textMute, minWidth: 95 }}>{k}:</span><strong>{v}</strong>
                    </div>
                  ))}
                </div>

                {/* Storage */}
                <div>
                  <div style={{ fontSize: 10, color: p.textMute, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 8 }}>Storage ({disks.length} device{disks.length!==1?"s":""})</div>
                  {disks.map((d, i) => (
                    <div key={d.id} style={{ fontSize: 12, marginBottom: 5, display: "flex", gap: 5, flexWrap: "wrap", color: p.textSub, alignItems: "center" }}>
                      <span>{d.type==="CDROM"?"💿":"💾"}</span>
                      <span style={{ fontWeight: 600, color: d.type==="CDROM"?p.yellow:"#4a90d9" }}>{d.type} {i+1}</span>
                      <span style={{ color: p.textMute }}>·</span><span>{d.bus_type}</span>
                      {d.type==="DISK"&&d.size_gib>0&&<><span style={{color:p.textMute}}>·</span><span>{d.size_gib}{d.size_unit}</span></>}
                      {d.sc_name&&<><span style={{color:p.textMute}}>·</span><span style={{color:p.cyan}}>📦 {d.sc_name}</span></>}
                      {d.clone_image&&d.image_name&&<><span style={{color:p.textMute}}>·</span><span style={{color:p.green}}>📀 {d.image_name}</span></>}
                    </div>
                  ))}
                </div>

                {/* Networks */}
                <div style={{ gridColumn: "1/-1", borderTop: `1px solid ${p.border}20`, paddingTop: 12 }}>
                  <div style={{ fontSize: 10, color: p.textMute, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 8 }}>Networks ({nics.length} NIC{nics.length!==1?"s":""})</div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {nics.map((n, i) => (
                      <span key={n.id} style={{ fontSize: 12, padding: "3px 10px", borderRadius: 6, background: `${p.green}12`, border: `1px solid ${p.green}30`, color: p.green }}>
                        🔌 NIC {i+1}: {n.subnet_name||"—"}{n.vlan_id>0?` (VLAN ${n.vlan_id})`:""}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Notes */}
              <div style={{ padding: "0 20px 18px" }}>
                <div style={{ fontSize: 10, color: p.textMute, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 6 }}>Notes / Comments (optional)</div>
                <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3} placeholder="Any special requirements or notes for the admin approver…" style={{ ...inpStyle, resize: "vertical" }} />
              </div>
            </div>

            {result?.ok === false && (
              <div style={{ padding: "10px 14px", borderRadius: 8, fontSize: 13, background: `${p.red}12`, border: `1px solid ${p.red}30`, color: p.red }}>❌ Submission failed: {result.message}</div>
            )}
            <div style={{ padding: "10px 14px", borderRadius: 8, fontSize: 12, background: `${p.yellow}10`, border: `1px solid ${p.yellow}20`, color: p.yellow }}>
              ℹ️ This request will be reviewed by an admin before the VM is created on Nutanix AHV.
            </div>
          </div>
        )}
      </div>

      {/* Navigation buttons */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {step > 0 && <button className="btn" onClick={() => setStep(s => s - 1)} style={{ background: p.surface, border: `1px solid ${p.border}`, color: p.textSub }}>← Back</button>}
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 12, color: p.textMute }}>Step {step + 1} of {STEPS.length}</div>
        {step < STEPS.length - 1
          ? <button className="btn btn-primary" onClick={() => setStep(s => s + 1)} disabled={!canNext()} style={{ opacity: canNext() ? 1 : 0.5 }}>Next →</button>
          : <button onClick={submit} disabled={submitting} style={{ padding: "9px 22px", borderRadius: 9, cursor: submitting ? "not-allowed" : "pointer", background: NTX_BLUE, border: "none", color: "#fff", fontWeight: 700, fontSize: 14, opacity: submitting ? 0.7 : 1 }}>
              {submitting ? "⏳ Submitting…" : "📤 Submit for Approval"}
            </button>
        }
      </div>
    </div>
  );
}

// ── TABS config ───────────────────────────────────────────────────────
const TABS = [
  { id: "overview",  label: "Overview",    icon: "🏠" },
  { id: "clusters",  label: "Clusters",    icon: "🟦" },
  { id: "vms",       label: "VMs",         icon: "💻" },
  { id: "hosts",     label: "Hosts",       icon: "🖥️" },
  { id: "storage",   label: "Storage",     icon: "💾" },
  { id: "networks",  label: "Networks",    icon: "🌐" },
  { id: "alerts",    label: "Alerts",      icon: "🔔" },
  { id: "request",   label: "Request VM",  icon: "📝" },
];

// ── Main NutanixPage component ────────────────────────────────────────
function NutanixPage({ currentUser, p }) {
  const role    = currentUser?.role || "viewer";
  const canAct  = role === "admin" || role === "operator";
  const isAdmin = role === "admin";

  // PC list state
  const [pcs,     setPcs]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [err,     setErr]     = useState(null);

  // Selected PC state
  const [selPC,   setSelPC]   = useState(null);
  const [tab,     setTab]     = useState("overview");

  // Tab data caches
  const [overview,   setOverview]   = useState(null);
  const [clusters,   setClusters]   = useState([]);
  const [vms,        setVms]        = useState([]);
  const [hosts,      setHosts]      = useState([]);
  const [storage,    setStorage]    = useState([]);
  const [alerts,     setAlerts]     = useState([]);
  const [networks,   setNetworks]   = useState([]);

  // Tab loading/error
  const [tabLoading, setTabLoading] = useState(false);
  const [tabErr,     setTabErr]     = useState(null);

  // Test connection
  const [testBusy,   setTestBusy]   = useState(false);
  const [testResult, setTestResult] = useState(null);

  // Modals
  const [showAdd,    setShowAdd]    = useState(false);
  const [editingPC,  setEditingPC]  = useState(null);

  // Load PCs
  const loadPCs = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const data = await fetchNutanixPCs();
      setPcs(data);
    } catch (e) { setErr(e.message); }
    setLoading(false);
  }, []);

  useEffect(() => { loadPCs(); }, [loadPCs]);

  // Clear caches when PC changes
  function selectPC(pc) {
    if (selPC?.id === pc.id) return;
    setSelPC(pc);
    setTab("overview");
    setOverview(null); setClusters([]); setVms([]); setHosts([]);
    setStorage([]); setAlerts([]); setNetworks([]);
    setTabErr(null); setTestResult(null);
  }

  // Load tab data
  async function loadTab(t) {
    if (!selPC) return;
    setTabLoading(true); setTabErr(null);
    try {
      switch (t) {
        case "overview": setOverview(await fetchNutanixOverview(selPC.id)); break;
        case "clusters": setClusters(await fetchNutanixClusters(selPC.id)); break;
        case "vms":      setVms(await fetchNutanixVMs(selPC.id)); break;
        case "hosts":    setHosts(await fetchNutanixHosts(selPC.id)); break;
        case "storage":  setStorage(await fetchNutanixStorage(selPC.id)); break;
        case "alerts":   setAlerts(await fetchNutanixAlerts(selPC.id)); break;
        case "networks": setNetworks(await fetchNutanixNetworks(selPC.id)); break;
      }
    } catch (e) { setTabErr(e.message); }
    setTabLoading(false);
  }

  // When tab changes, auto-load if not yet loaded
  useEffect(() => {
    if (!selPC) return;
    const needsLoad = {
      overview: !overview,
      clusters: clusters.length === 0,
      vms:      vms.length === 0,
      hosts:    hosts.length === 0,
      storage:  storage.length === 0,
      alerts:   alerts.length === 0,
      networks: networks.length === 0,
    };
    if (needsLoad[tab]) loadTab(tab);
  }, [tab, selPC]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function doTest() {
    if (!selPC) return;
    setTestBusy(true); setTestResult(null);
    try {
      const r = await testNutanixPC(selPC.id);
      setTestResult(r);
      loadPCs();
    } catch (e) { setTestResult({ reachable: false, message: e.message }); }
    setTestBusy(false);
  }

  async function doDeletePC(pc) {
    if (!window.confirm(`Delete Prism Central '${pc.name}'? This removes it from CaaS only.`)) return;
    try {
      await deleteNutanixPC(pc.id);
      if (selPC?.id === pc.id) setSelPC(null);
      loadPCs();
    } catch (e) { alert(e.message); }
  }

  if (loading) return <LoadState msg="Loading Nutanix Prism Centrals…" />;
  if (err)     return <ErrState msg={err} onRetry={loadPCs} />;

  // Group PCs by site
  const dcPCs = pcs.filter((pc) => pc.site !== "DR");
  const drPCs = pcs.filter((pc) => pc.site === "DR");

  const NUTANIX_BLUE = "#024DA1";

  function PCChip({ pc }) {
    const isSel   = selPC?.id === pc.id;
    const stColor = pc.status === "connected" ? p.green
                  : pc.status === "error"     ? p.red : "#64748b";
    return (
      <div onClick={() => selectPC(pc)}
        style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 14px",
                 borderRadius: 10, cursor: "pointer", transition: "all .15s",
                 background: isSel ? `${NUTANIX_BLUE}18` : p.surface,
                 border: `1.5px solid ${isSel ? NUTANIX_BLUE + "60" : p.border}` }}>
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: stColor,
                      boxShadow: `0 0 6px ${stColor}80` }} />
        <span style={{ fontWeight: 600, fontSize: 13, color: isSel ? "#4a90d9" : p.text }}>
          {pc.name}
        </span>
        <span style={{ fontSize: 10, color: stColor, fontWeight: 600 }}>{pc.status || "unknown"}</span>
        {isAdmin && (
          <div style={{ display: "flex", gap: 3, marginLeft: 4 }}>
            <button title="Edit" onClick={(e) => { e.stopPropagation(); setEditingPC(pc); }}
              style={{ background: `${p.accent}15`, border: `1px solid ${p.accent}30`,
                       borderRadius: 4, padding: "0 5px", cursor: "pointer", fontSize: 10,
                       color: p.accent, fontWeight: 700 }}>✏️</button>
            <button title="Delete" onClick={(e) => { e.stopPropagation(); doDeletePC(pc); }}
              style={{ background: `${p.red}15`, border: `1px solid ${p.red}30`,
                       borderRadius: 4, padding: "0 5px", cursor: "pointer", fontSize: 10,
                       color: p.red, fontWeight: 700 }}>✕</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="g-gap">
      {/* ── Header ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 38, height: 38, borderRadius: 10,
                        background: `linear-gradient(135deg,${NUTANIX_BLUE},#0066cc)`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 22, flexShrink: 0 }}>🟦</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 17 }}>Nutanix</div>
            <div style={{ fontSize: 12, color: p.textMute }}>Prism Central — DC infrastructure management</div>
          </div>
        </div>
        <div style={{ flex: 1 }} />
        {canAct && vms.length > 0 && (
          <button className="btn btn-sm" onClick={() => exportVMsCSV(vms)}
            style={{ background: `${p.green}15`, border: `1px solid ${p.green}40`,
                     color: p.green, fontWeight: 600, fontSize: 12 }}>
            📥 Export VMs CSV
          </button>
        )}
        {isAdmin && (
          <button className="btn btn-primary btn-sm" onClick={() => setShowAdd(true)}>
            + Add Prism Central
          </button>
        )}
      </div>

      {/* ── PC selector chips — DC ── */}
      {pcs.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {dcPCs.length > 0 && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: p.textMute,
                            textTransform: "uppercase", letterSpacing: ".8px",
                            marginBottom: 6 }}>🏢 DC — Data Centre</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {dcPCs.map((pc) => <PCChip key={pc.id} pc={pc} />)}
              </div>
            </div>
          )}
          {drPCs.length > 0 && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: p.textMute,
                            textTransform: "uppercase", letterSpacing: ".8px",
                            marginBottom: 6 }}>🛡️ DR — Disaster Recovery</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {drPCs.map((pc) => <PCChip key={pc.id} pc={pc} />)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Empty state ── */}
      {pcs.length === 0 && (
        <div className="card" style={{ textAlign: "center", padding: 48 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🟦</div>
          <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 6 }}>No Prism Central Configured</div>
          <div style={{ fontSize: 13, color: p.textMute, marginBottom: 16 }}>
            Add a Prism Central to start monitoring clusters, VMs and hosts.
          </div>
          {isAdmin && (
            <button className="btn btn-primary" onClick={() => setShowAdd(true)}>
              + Add Prism Central
            </button>
          )}
        </div>
      )}

      {/* ── Selected PC workspace ── */}
      {selPC && (
        <div className="g-gap">
          {/* PC info bar */}
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
                        padding: "10px 16px", borderRadius: 10,
                        background: p.surface, border: `1px solid ${p.border}` }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: NUTANIX_BLUE }}>{selPC.name}</span>
            <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 5,
                           background: selPC.site === "DR" ? "#f97316" + "18" : "#024DA118",
                           border: `1px solid ${selPC.site === "DR" ? "#f97316" : NUTANIX_BLUE}40`,
                           color: selPC.site === "DR" ? "#f97316" : "#4a90d9" }}>
              {selPC.site || "DC"}
            </span>
            <code style={{ fontSize: 11, color: p.cyan, background: `${p.cyan}10`,
                           padding: "2px 8px", borderRadius: 4 }}>
              {selPC.host}:9440
            </code>
            {selPC.description && (
              <span style={{ fontSize: 12, color: p.textMute, fontStyle: "italic" }}>{selPC.description}</span>
            )}
            <div style={{ flex: 1 }} />
            {canAct && (
              <button className="btn btn-sm" onClick={doTest} disabled={testBusy}
                style={{ background: `${p.cyan}15`, border: `1px solid ${p.cyan}30`,
                         color: p.cyan, fontSize: 11 }}>
                {testBusy ? "⏳ Testing…" : "📡 Test Connection"}
              </button>
            )}
            <button className="btn btn-sm" onClick={() => loadTab(tab)} disabled={tabLoading}
              style={{ background: `${p.green}15`, border: `1px solid ${p.green}30`,
                       color: p.green, fontSize: 11 }}>
              {tabLoading ? "⏳" : "↻"} Refresh
            </button>
          </div>

          {/* Test result banner */}
          {testResult && (
            <div style={{ padding: "8px 14px", borderRadius: 8, fontSize: 13,
                          background: testResult.reachable ? `${p.green}12` : `${p.red}12`,
                          border: `1px solid ${testResult.reachable ? p.green : p.red}30`,
                          color: testResult.reachable ? p.green : p.red }}>
              {testResult.reachable ? "✅" : "❌"} {testResult.message}
            </div>
          )}

          {/* Tabs */}
          <div style={{ display: "flex", gap: 2, flexWrap: "wrap",
                        borderBottom: `1px solid ${p.border}`, paddingBottom: 2 }}>
            {TABS.map((t) => {
              const act = tab === t.id;
              return (
                <button key={t.id} onClick={() => setTab(t.id)}
                  style={{ display: "flex", alignItems: "center", gap: 6, padding: "8px 14px",
                           borderRadius: "8px 8px 0 0",
                           border: `1px solid ${act ? NUTANIX_BLUE + "60" : p.border}`,
                           borderBottom: act ? "none" : "",
                           background: act ? `${NUTANIX_BLUE}15` : p.surface,
                           color: act ? "#4a90d9" : p.textSub,
                           fontWeight: act ? 700 : 500, fontSize: 13,
                           cursor: "pointer", marginBottom: act ? -1 : 0 }}>
                  {t.icon} {t.label}
                </button>
              );
            })}
          </div>

          {/* Tab errors */}
          {tabErr && (
            <div style={{ padding: "10px 14px", borderRadius: 8, fontSize: 13,
                          background: `${p.red}12`, border: `1px solid ${p.red}30`, color: p.red }}>
              ⚠️ {tabErr}
            </div>
          )}

          {/* Tab loading */}
          {tabLoading && tab !== "request" && <LoadState msg="Fetching live data from Prism Central…" />}

          {/* Tab content */}
          {!tabLoading && tab !== "request" && (
            <div>
              {tab === "overview" && <TabOverview overview={overview} p={p} />}
              {tab === "clusters" && <TabClusters clusters={clusters} p={p} />}
              {tab === "vms"      && <TabVMs vms={vms} pcId={selPC.id} canAct={canAct} p={p} />}
              {tab === "hosts"    && <TabHosts hosts={hosts} p={p} />}
              {tab === "storage"  && <TabStorage containers={storage} p={p} />}
              {tab === "networks" && <TabNetworks networks={networks} p={p} />}
              {tab === "alerts"   && <TabAlerts alerts={alerts} p={p} />}
            </div>
          )}

          {/* Request VM wizard — always rendered regardless of tabLoading */}
          {tab === "request" && (
            <TabRequestVM pcs={pcs} selPC={selPC} p={p} currentUser={currentUser} />
          )}
        </div>
      )}

      {/* ── Add PC Modal ── */}
      {showAdd && (
        <PCModal mode="add" p={p}
          onClose={() => setShowAdd(false)}
          onSaved={() => { setShowAdd(false); loadPCs(); }} />
      )}

      {/* ── Edit PC Modal ── */}
      {editingPC && (
        <PCModal mode="edit" initial={editingPC} p={p}
          onClose={() => setEditingPC(null)}
          onSaved={() => { setEditingPC(null); loadPCs(); }} />
      )}
    </div>
  );
}

export default NutanixPage;
