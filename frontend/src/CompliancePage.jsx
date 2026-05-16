/**
 * CompliancePage.jsx  --  CompliSphere v2
 * =========================================================
 * Tabs: Dashboard | Scan Config | Assets | Remediation
 * - 9 toggleable compliance rules with best-practice descriptions
 * - SSH (Linux root/Wipro@123) + WinRM (Windows Administrator/Wipro@123)
 * - Uptime, patch age, EOL OS, VMware Tools, HW version, snapshots, etc.
 */
import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { getToken } from "./api";

const CISHardeningModule = lazy(() => import("./CISHardening"));
function CISHardeningLazy(props) {
  return (
    <Suspense fallback={
      <div style={{ textAlign:"center", padding:60, color:"#6b7280" }}>
        <div style={{ fontSize:32, marginBottom:12 }}>🔒</div>
        <p>Loading CIS Hardening…</p>
      </div>
    }>
      <CISHardeningModule {...props} />
    </Suspense>
  );
}

const C_GREEN  = "#22c55e";
const C_YELLOW = "#f59e0b";
const C_RED    = "#ef4444";
const C_BLUE   = "#3b82f6";
const C_PURPLE = "#8b5cf6";

const STATUS_COLOR = { compliant: C_GREEN, warning: C_YELLOW, non_compliant: C_RED };
const STATUS_LABEL = { compliant: "Compliant", warning: "Warning", non_compliant: "Non-Compliant" };
const STATUS_ICON  = { compliant: "✅", warning: "⚠️", non_compliant: "🔴" };

const CAT_COLOR = {
  Security: C_RED, Patching: C_YELLOW, Availability: C_BLUE,
  VMware: C_PURPLE, Performance: "#f97316", Inventory: "#06b6d4",
};

function authHdr() { return { Authorization: "Bearer " + getToken(), "Content-Type": "application/json" }; }
async function apiFetch(path, opts = {}) {
  const r = await fetch(path, { headers: authHdr(), ...opts });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ── Donut Chart ──────────────────────────────────────────────────────────────
function DonutChart({ compliant = 0, warning = 0, non_compliant = 0, size = 190 }) {
  const total = compliant + warning + non_compliant || 1;
  const r = 72, cx = 95, cy = 95, sw = 22, circ = 2 * Math.PI * r;
  const pct = (v) => v / total;
  const ok = pct(compliant), wn = pct(warning);
  const seg = (val, offset, color) => (
    <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={sw}
      strokeDasharray={`${pct(val) * circ} ${circ}`}
      strokeDashoffset={-offset * circ}
      strokeLinecap="butt" transform={`rotate(-90 ${cx} ${cy})`} />
  );
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e293b" strokeWidth={sw} />
      {seg(non_compliant, ok + wn, C_RED)}
      {seg(warning, ok, C_YELLOW)}
      {seg(compliant, 0, C_GREEN)}
      <text x={cx} y={cy - 10} textAnchor="middle" fill="#f1f5f9" fontSize={30} fontWeight={900} fontFamily="monospace">
        {Math.round(ok * 100)}%
      </text>
      <text x={cx} y={cy + 12} textAnchor="middle" fill="#64748b" fontSize={12} fontWeight={700}>COMPLIANT</text>
    </svg>
  );
}

// ── Sparkline ────────────────────────────────────────────────────────────────
function Sparkline({ data, field = "avg_score", color = C_BLUE, h = 60, w = 340 }) {
  if (!data || data.length < 2) return <div style={{ color: "#64748b", fontSize: 13 }}>Trend builds up after daily scans</div>;
  const vals = data.map(d => parseFloat(d[field]) || 0);
  const min = Math.min(...vals), max = Math.max(...vals) || 1;
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1)) * w;
    const y = h - ((v - min) / (max - min || 1)) * (h - 10) - 5;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const last = pts.split(" ").pop().split(",");
  return (
    <svg width={w} height={h}>
      <defs>
        <linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill="url(#sg)" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r={4} fill={color} />
    </svg>
  );
}

// ── Score badge ──────────────────────────────────────────────────────────────
function ScoreBadge({ score, size = "md" }) {
  const color = score >= 80 ? C_GREEN : score >= 50 ? C_YELLOW : C_RED;
  const fs = size === "lg" ? 30 : 15;
  return <span style={{ fontWeight: 900, fontFamily: "monospace", fontSize: fs, color }}>{score ?? "—"}</span>;
}

function StatusPill({ status }) {
  const color = STATUS_COLOR[status] || "#64748b";
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 20,
      border: `1px solid ${color}40`, background: `${color}15`, color,
      textTransform: "uppercase", letterSpacing: ".5px",
    }}>
      {STATUS_ICON[status]} {STATUS_LABEL[status] || status}
    </span>
  );
}

// ── Rule toggle card ─────────────────────────────────────────────────────────
function RuleCard({ rule, enabled, onToggle, p }) {
  const catColor = CAT_COLOR[rule.category] || C_BLUE;
  return (
    <div style={{
      borderRadius: 12, border: `1.5px solid ${enabled ? catColor + "55" : p.border}`,
      background: enabled ? `${catColor}08` : p.panelAlt,
      padding: "14px 16px", transition: "all .2s",
    }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <span style={{ fontSize: 20 }}>{rule.icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: enabled ? p.text : p.textMute }}>{rule.label}</div>
          <span style={{
            fontSize: 10, fontWeight: 700, padding: "1px 7px", borderRadius: 8,
            background: `${catColor}20`, color: catColor,
          }}>{rule.category}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 11, color: p.textMute }}>W: {rule.weight}</span>
          {/* Toggle */}
          <div onClick={() => onToggle(rule.id)} style={{
            width: 44, height: 24, borderRadius: 12, position: "relative", cursor: "pointer",
            background: enabled ? catColor : `${p.border}80`,
            transition: "background .2s", flexShrink: 0,
            boxShadow: enabled ? `0 0 10px ${catColor}50` : "none",
          }}>
            <div style={{
              position: "absolute", top: 3, width: 18, height: 18, borderRadius: "50%",
              background: "#fff", transition: "left .2s",
              left: enabled ? 23 : 3,
              boxShadow: "0 1px 4px #0004",
            }} />
          </div>
        </div>
      </div>
      {/* Description */}
      <div style={{ fontSize: 12, color: p.textMute, lineHeight: 1.5, marginBottom: 8 }}>{rule.description}</div>
      {/* Green/Yellow/Red thresholds */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {[
          { label: rule.green,  color: C_GREEN  },
          { label: rule.yellow, color: C_YELLOW },
          { label: rule.red,    color: C_RED    },
        ].map((t, i) => (
          <span key={i} style={{
            fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 6,
            background: `${t.color}15`, color: t.color, border: `1px solid ${t.color}30`,
          }}>
            {i === 0 ? "🟢" : i === 1 ? "🟡" : "🔴"} {t.label}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Asset detail side panel ──────────────────────────────────────────────────
function AssetDetailPanel({ assetId, onClose, onRemediate, p }) {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [remCheck, setRemCheck] = useState("");
  const [remNote,  setRemNote]  = useState("");
  const [remBusy,  setRemBusy]  = useState(false);
  const [remMsg,   setRemMsg]   = useState("");

  useEffect(() => {
    if (!assetId) return;
    setLoading(true);
    apiFetch(`/api/compliance/assets/${assetId}`)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [assetId]);

  const submitRem = async () => {
    if (!remCheck) return;
    setRemBusy(true);
    try {
      await apiFetch(`/api/compliance/remediate/${assetId}`, {
        method: "POST",
        body: JSON.stringify({ check_name: remCheck, action: remNote || `Remediate: ${remCheck}`, priority: data?.score < 50 ? "critical" : "medium" }),
      });
      setRemMsg("✅ Task created"); setRemNote(""); setRemCheck("");
      if (onRemediate) onRemediate();
    } catch { setRemMsg("❌ Failed"); }
    setRemBusy(false);
    setTimeout(() => setRemMsg(""), 3000);
  };

  const a = data?.asset;
  const checks = data?.checks || [];

  return (
    <div style={{
      position: "fixed", top: 0, right: 0, bottom: 0, width: 520,
      background: p.panel, borderLeft: `1px solid ${p.border}`,
      zIndex: 1000, display: "flex", flexDirection: "column",
      boxShadow: "-8px 0 40px #00000050",
    }}>
      <div style={{ padding: "14px 18px", borderBottom: `1px solid ${p.border}`, display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 16, color: p.text }}>{a?.hostname || "Loading…"}</div>
          <div style={{ fontSize: 12, color: p.textMute }}>{a?.ip_address} · {a?.vcenter || "baremetal"}</div>
        </div>
        {data && <ScoreBadge score={data.score} size="lg" />}
        {data && <StatusPill status={data.status} />}
        <button onClick={onClose} style={{ background: "none", border: "none", color: p.textMute, cursor: "pointer", fontSize: 22 }}>✕</button>
      </div>

      {loading
        ? <div style={{ padding: 40, textAlign: "center", color: p.textMute }}>Loading…</div>
        : <div style={{ flex: 1, overflowY: "auto", padding: "14px 18px" }}>
            {/* Meta grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 18 }}>
              {[
                ["OS",       a?.os_name],
                ["Type",     a?.asset_type],
                ["vCenter",  a?.vcenter],
                ["Cluster",  a?.cluster],
                ["CPU",      a?.cpu_count ? `${a.cpu_count} vCPU` : "—"],
                ["RAM",      a?.memory_gb ? `${a.memory_gb} GB`  : "—"],
                ["Power",    a?.power_state],
                ["Tools",    a?.tools_status],
                ["HW Ver",   a?.hw_version],
                ["Owner",    a?.owner_team],
              ].map(([lbl, val]) => (
                <div key={lbl} style={{ background: p.panelAlt, borderRadius: 8, padding: "7px 10px" }}>
                  <div style={{ fontSize: 10, color: p.textMute, fontWeight: 700, marginBottom: 2 }}>{lbl}</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: p.text }}>{val || "—"}</div>
                </div>
              ))}
            </div>

            {/* Checks */}
            <div style={{ fontWeight: 700, fontSize: 13, color: p.text, marginBottom: 8 }}>🔍 Compliance Checks</div>
            {checks.map((c, i) => {
              const color = STATUS_COLOR[c.status] || "#64748b";
              return (
                <div key={i} style={{
                  display: "flex", alignItems: "flex-start", gap: 10,
                  padding: "9px 12px", borderRadius: 8, marginBottom: 5,
                  background: `${color}08`, border: `1px solid ${color}20`,
                }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: color, marginTop: 4, flexShrink: 0 }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                      <span style={{ fontWeight: 700, fontSize: 12, color: p.text }}>{c.label || c.name}</span>
                      <StatusPill status={c.status} />
                    </div>
                    <div style={{ fontSize: 11, color: p.textMute }}>{c.message}</div>
                  </div>
                  <span style={{ fontWeight: 800, fontSize: 13, color, fontFamily: "monospace", flexShrink: 0 }}>{c.earned}/{c.weight}</span>
                </div>
              );
            })}

            {/* Remediate */}
            {checks.some(c => c.status !== "compliant") && (
              <div style={{ marginTop: 16, padding: "14px", borderRadius: 10, border: `1px solid ${C_RED}30`, background: `${C_RED}06` }}>
                <div style={{ fontWeight: 700, fontSize: 13, color: p.text, marginBottom: 8 }}>🔧 Create Remediation Task</div>
                <select value={remCheck} onChange={e => setRemCheck(e.target.value)}
                  style={{ width: "100%", background: p.panelAlt, border: `1px solid ${p.border}`, borderRadius: 7, padding: "7px 10px", color: p.text, marginBottom: 7, fontSize: 12 }}>
                  <option value="">— Select failing check —</option>
                  {checks.filter(c => c.status !== "compliant").map((c, i) =>
                    <option key={i} value={c.name}>{c.label || c.name} ({c.status})</option>
                  )}
                </select>
                <textarea rows={2} placeholder="Notes (optional)" value={remNote} onChange={e => setRemNote(e.target.value)}
                  style={{ width: "100%", background: p.panelAlt, border: `1px solid ${p.border}`, borderRadius: 7, padding: "7px 10px", color: p.text, fontSize: 12, resize: "none", boxSizing: "border-box" }} />
                <button disabled={!remCheck || remBusy} onClick={submitRem}
                  style={{ marginTop: 7, width: "100%", padding: 9, borderRadius: 8, background: remCheck ? C_RED : `${C_RED}40`, color: "#fff", border: "none", fontWeight: 700, fontSize: 13, cursor: remCheck ? "pointer" : "not-allowed" }}>
                  {remBusy ? "Creating…" : "📋 Create Task"}
                </button>
                {remMsg && <div style={{ marginTop: 6, fontSize: 12, color: C_GREEN }}>{remMsg}</div>}
              </div>
            )}
          </div>
      }
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
//  TAB: Reports  — multi-filter, export to CSV
// ═══════════════════════════════════════════════════════════════════════
const REPORT_TEMPLATES = [
  { id: "all",           label: "Full Inventory",        icon: "📋", desc: "All assets, all checks" },
  { id: "non_compliant", label: "Non-Compliant",         icon: "🔴", desc: "Score < 50" },
  { id: "warning",       label: "Warnings",              icon: "⚠️",  desc: "Score 50–79" },
  { id: "eol",           label: "EOL OS",                icon: "💀", desc: "End-of-life operating systems" },
  { id: "patch",         label: "Patch Overdue",         icon: "🔄", desc: "Last patch > 90 days" },
  { id: "uptime",        label: "High Uptime",           icon: "⏱️", desc: "Uptime > 180 days (reboot overdue)" },
  { id: "disk",          label: "Disk Space Risk",       icon: "💾", desc: "Disk check failing" },
  { id: "tools",         label: "VMware Tools Issues",   icon: "🔧", desc: "Tools outdated or missing" },
  { id: "snapshots",     label: "Stale Snapshots",       icon: "📸", desc: "Snapshots older than 7 days" },
  { id: "no_av",         label: "No AV/EDR",             icon: "🛡️", desc: "Missing antivirus/EDR agent" },
  { id: "windows",       label: "Windows Assets",        icon: "🪟", desc: "All Windows VMs & servers" },
  { id: "linux",         label: "Linux Assets",          icon: "🐧", desc: "All Linux VMs & servers" },
];
const TEMPLATE_PARAMS = {
  all:           {},
  non_compliant: { status: "non_compliant" },
  warning:       { status: "warning" },
  eol:           { failing_check: "eol_os" },
  patch:         { patch_age_min: 90 },
  uptime:        { uptime_min: 180 },
  disk:          { failing_check: "disk_space" },
  tools:         { failing_check: "vmware_tools" },
  snapshots:     { failing_check: "snapshot_age" },
  no_av:         { failing_check: "antivirus" },
  windows:       { os_family: "windows" },
  linux:         { os_family: "linux" },
};

function ReportPage({ p }) {
  const [template,   setTemplate]   = useState("all");
  const [rows,       setRows]       = useState([]);
  const [summary,    setSummary]    = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [generated,  setGenerated]  = useState(false);
  const [fStatus,    setFStatus]    = useState("");
  const [fType,      setFType]      = useState("");
  const [fOsFamily,  setFOsFamily]  = useState("");
  const [fOsName,    setFOsName]    = useState("");
  const [fVcenter,   setFVcenter]   = useState("");
  const [fEnv,       setFEnv]       = useState("");
  const [fTeam,      setFTeam]      = useState("");
  const [fScoreMin,  setFScoreMin]  = useState("");
  const [fScoreMax,  setFScoreMax]  = useState("");
  const [fPatchMin,  setFPatchMin]  = useState("");
  const [fPatchMax,  setFPatchMax]  = useState("");
  const [fUptimeMin, setFUptimeMin] = useState("");
  const [fUptimeMax, setFUptimeMax] = useState("");
  const [fSearch,    setFSearch]    = useState("");
  const [fSortBy,    setFSortBy]    = useState("score");
  const [fSortDir,   setFSortDir]   = useState("asc");
  const [fFailing,   setFFailing]   = useState("");

  const applyTemplate = (tid) => {
    setTemplate(tid);
    const tp = TEMPLATE_PARAMS[tid] || {};
    setFStatus(tp.status || ""); setFOsFamily(tp.os_family || ""); setFFailing(tp.failing_check || "");
    setFPatchMin(tp.patch_age_min != null ? String(tp.patch_age_min) : "");
    setFUptimeMin(tp.uptime_min != null ? String(tp.uptime_min) : "");
    setFType(""); setFOsName(""); setFVcenter(""); setFEnv(""); setFTeam("");
    setFScoreMin(""); setFScoreMax(""); setFPatchMax(""); setFUptimeMax(""); setFSearch("");
  };

  const buildQuery = (fmt = "json") => {
    const q = new URLSearchParams({ fmt, sort_by: fSortBy, sort_dir: fSortDir });
    if (fStatus)    q.set("status",        fStatus);
    if (fType)      q.set("asset_type",    fType);
    if (fOsFamily)  q.set("os_family",     fOsFamily);
    if (fOsName)    q.set("os_name",       fOsName);
    if (fVcenter)   q.set("vcenter",       fVcenter);
    if (fEnv)       q.set("environment",   fEnv);
    if (fTeam)      q.set("owner_team",    fTeam);
    if (fSearch)    q.set("search",        fSearch);
    if (fScoreMin)  q.set("score_min",     fScoreMin);
    if (fScoreMax)  q.set("score_max",     fScoreMax);
    if (fPatchMin)  q.set("patch_age_min", fPatchMin);
    if (fPatchMax)  q.set("patch_age_max", fPatchMax);
    if (fUptimeMin) q.set("uptime_min",    fUptimeMin);
    if (fUptimeMax) q.set("uptime_max",    fUptimeMax);
    if (fFailing)   q.set("failing_check", fFailing);
    return q.toString();
  };

  const generate = async () => {
    setLoading(true); setGenerated(false);
    try {
      const d = await apiFetch(`/api/compliance/report?${buildQuery("json")}`);
      setRows(d.assets || []); setSummary(d.summary || {}); setGenerated(true);
    } catch { }
    setLoading(false);
  };

  const exportCSV = () => {
    fetch(`/api/compliance/report?${buildQuery("csv")}`, { headers: { Authorization: "Bearer " + getToken() } })
      .then(r => r.blob())
      .then(blob => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `compliance_${template}_${new Date().toISOString().slice(0,10)}.csv`;
        a.click();
      });
  };

  const IS  = { background: p.panelAlt, border: `1px solid ${p.border}`, borderRadius: 8, padding: "7px 11px", color: p.text, fontSize: 13, width: "100%", boxSizing: "border-box" };
  const LBL = { fontSize: 11, fontWeight: 600, color: p.textMute, marginBottom: 4 };
  const TH  = { padding: "8px 10px", fontSize: 11, fontWeight: 700, color: p.textMute, textTransform: "uppercase", letterSpacing: ".5px", borderBottom: `1px solid ${p.border}`, background: p.panelAlt, whiteSpace: "nowrap" };

  return (
    <div>
      <div style={{ fontWeight: 800, fontSize: 18, color: p.text, marginBottom: 4 }}>📊 Compliance Reports</div>
      <div style={{ fontSize: 13, color: p.textMute, marginBottom: 20 }}>Build custom reports with any combination of filters — export to CSV for Excel / ServiceNow / Jira</div>

      {/* Template quick-picks */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: p.textMute, marginBottom: 10, textTransform: "uppercase", letterSpacing: ".6px" }}>Quick Templates</div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {REPORT_TEMPLATES.map(t => (
            <button key={t.id} onClick={() => applyTemplate(t.id)} title={t.desc}
              style={{ padding: "7px 14px", borderRadius: 20, border: `1.5px solid ${template === t.id ? C_BLUE : p.border}`,
                background: template === t.id ? `${C_BLUE}18` : p.panelAlt, color: template === t.id ? C_BLUE : p.textMute,
                fontWeight: template === t.id ? 700 : 500, fontSize: 13, cursor: "pointer", transition: "all .15s" }}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filter panel */}
      <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14, padding: "16px 20px", marginBottom: 20 }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: p.text, marginBottom: 14 }}>🔍 Custom Filters</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 }}>
          <div><div style={LBL}>Status</div>
            <select value={fStatus} onChange={e => setFStatus(e.target.value)} style={IS}>
              <option value="">All</option>
              <option value="compliant">✅ Compliant</option>
              <option value="warning">⚠️ Warning</option>
              <option value="non_compliant">🔴 Non-Compliant</option>
              <option value="warning,non_compliant">⚠️+🔴 Issues Only</option>
            </select></div>
          <div><div style={LBL}>Asset Type</div>
            <select value={fType} onChange={e => setFType(e.target.value)} style={IS}>
              <option value="">All</option><option value="vm">VM</option><option value="baremetal">Baremetal</option>
            </select></div>
          <div><div style={LBL}>OS Family</div>
            <select value={fOsFamily} onChange={e => setFOsFamily(e.target.value)} style={IS}>
              <option value="">All</option><option value="windows">Windows</option><option value="linux">Linux</option><option value="other">Other</option>
            </select></div>
          <div><div style={LBL}>Failing Check</div>
            <select value={fFailing} onChange={e => setFFailing(e.target.value)} style={IS}>
              <option value="">Any</option>
              <option value="eol_os">💀 EOL OS</option>
              <option value="os_patch_age">🔄 Patch Age</option>
              <option value="uptime">⏱️ Uptime</option>
              <option value="vmware_tools">🔧 VMware Tools</option>
              <option value="hw_version">🖥️ HW Version</option>
              <option value="snapshot_age">📸 Snapshot Age</option>
              <option value="cpu_ratio">⚙️ CPU Ratio</option>
              <option value="power_state">🔌 Power State</option>
              <option value="antivirus">🛡️ Antivirus</option>
              <option value="disk_space">💾 Disk Space</option>
            </select></div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 12 }}>
          <div><div style={LBL}>OS Name (partial)</div><input value={fOsName} onChange={e => setFOsName(e.target.value)} placeholder="e.g. Windows Server 2016" style={IS} /></div>
          <div><div style={LBL}>vCenter (partial)</div><input value={fVcenter} onChange={e => setFVcenter(e.target.value)} placeholder="e.g. 172.17" style={IS} /></div>
          <div><div style={LBL}>Environment</div><input value={fEnv} onChange={e => setFEnv(e.target.value)} placeholder="e.g. production" style={IS} /></div>
          <div><div style={LBL}>Owner / Team</div><input value={fTeam} onChange={e => setFTeam(e.target.value)} placeholder="e.g. Network" style={IS} /></div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, marginBottom: 12 }}>
          <div><div style={LBL}>Score ≥</div><input type="number" value={fScoreMin} onChange={e => setFScoreMin(e.target.value)} placeholder="0" style={IS} /></div>
          <div><div style={LBL}>Score ≤</div><input type="number" value={fScoreMax} onChange={e => setFScoreMax(e.target.value)} placeholder="100" style={IS} /></div>
          <div><div style={LBL}>Patch Age ≥ (days)</div><input type="number" value={fPatchMin} onChange={e => setFPatchMin(e.target.value)} placeholder="e.g. 30" style={IS} /></div>
          <div><div style={LBL}>Patch Age ≤ (days)</div><input type="number" value={fPatchMax} onChange={e => setFPatchMax(e.target.value)} placeholder="e.g. 90" style={IS} /></div>
          <div><div style={LBL}>Uptime ≥ (days)</div><input type="number" value={fUptimeMin} onChange={e => setFUptimeMin(e.target.value)} placeholder="e.g. 180" style={IS} /></div>
          <div><div style={LBL}>Uptime ≤ (days)</div><input type="number" value={fUptimeMax} onChange={e => setFUptimeMax(e.target.value)} placeholder="e.g. 365" style={IS} /></div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 150px 150px", gap: 12 }}>
          <div><div style={LBL}>Free Search (hostname / IP / OS)</div><input value={fSearch} onChange={e => setFSearch(e.target.value)} placeholder="🔍 free text…" style={IS} /></div>
          <div><div style={LBL}>Sort By</div>
            <select value={fSortBy} onChange={e => setFSortBy(e.target.value)} style={IS}>
              <option value="score">Score</option><option value="hostname">Hostname</option>
              <option value="patch_age_days">Patch Age</option><option value="vcenter">vCenter</option><option value="os_name">OS</option>
            </select></div>
          <div><div style={LBL}>Direction</div>
            <select value={fSortDir} onChange={e => setFSortDir(e.target.value)} style={IS}>
              <option value="asc">↑ Ascending</option><option value="desc">↓ Descending</option>
            </select></div>
        </div>
      </div>

      {/* Action bar */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, alignItems: "center" }}>
        <button onClick={generate} disabled={loading}
          style={{ padding: "10px 28px", borderRadius: 10, border: "none", background: C_BLUE, color: "#fff", fontWeight: 700, fontSize: 14, cursor: "pointer", boxShadow: `0 4px 16px ${C_BLUE}40` }}>
          {loading ? "⏳ Generating…" : "🔍 Generate Report"}
        </button>
        {generated && <button onClick={exportCSV}
          style={{ padding: "10px 22px", borderRadius: 10, border: `1px solid ${C_GREEN}50`, background: `${C_GREEN}12`, color: C_GREEN, fontWeight: 700, fontSize: 14, cursor: "pointer" }}>
          📥 Export CSV
        </button>}
        {generated && summary && (
          <div style={{ display: "flex", gap: 16, marginLeft: 12 }}>
            {[{ l:"Total",v:summary.total,c:C_BLUE},{l:"Avg",v:`${summary.avg_score}`,c:C_BLUE},{l:"✅",v:summary.compliant,c:C_GREEN},{l:"⚠️",v:summary.warning,c:C_YELLOW},{l:"🔴",v:summary.non_compliant,c:C_RED}]
              .map(kp => (
                <div key={kp.l} style={{ textAlign: "center" }}>
                  <div style={{ fontWeight: 900, fontSize: 18, color: kp.c, fontFamily: "monospace" }}>{kp.v}</div>
                  <div style={{ fontSize: 10, color: p.textMute, fontWeight: 600 }}>{kp.l}</div>
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Results table */}
      {generated && (
        <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14, overflow: "auto", maxHeight: 520 }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead style={{ position: "sticky", top: 0, zIndex: 2 }}>
              <tr>{["Hostname","IP","OS","Type","vCenter","CPU","RAM","Disk","Score","Status","Patch","Failing Checks","Scanned"].map(h => <th key={h} style={TH}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {rows.length === 0
                ? <tr><td colSpan={13} style={{ padding: 32, textAlign: "center", color: p.textMute }}>No assets match the selected filters.</td></tr>
                : rows.map((a, i) => {
                  const sc = STATUS_COLOR[a.compliance_status] || "#64748b";
                  return (
                    <tr key={a.id || i} style={{ borderBottom: `1px solid ${p.border}` }}
                      onMouseEnter={e => e.currentTarget.style.background = `${C_BLUE}06`}
                      onMouseLeave={e => e.currentTarget.style.background = ""}>
                      <td style={{ padding: "7px 10px", fontWeight: 600, color: p.text, whiteSpace: "nowrap" }}>{a.hostname}</td>
                      <td style={{ padding: "7px 10px", color: p.textMute, fontFamily: "monospace", whiteSpace: "nowrap" }}>{a.ip_address || "—"}</td>
                      <td style={{ padding: "7px 10px", color: p.textMute, maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={a.os_name}>{a.os_name || "—"}</td>
                      <td style={{ padding: "7px 10px" }}><span style={{ fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: `${C_BLUE}15`, color: C_BLUE }}>{(a.asset_type||"").toUpperCase()}</span></td>
                      <td style={{ padding: "7px 10px", color: p.textMute, maxWidth: 110, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={a.vcenter}>{a.vcenter||"—"}</td>
                      <td style={{ padding: "7px 10px", color: p.textMute, textAlign: "right" }}>{a.cpu_count??'—'}</td>
                      <td style={{ padding: "7px 10px", color: p.textMute, textAlign: "right" }}>{a.memory_gb != null ? `${a.memory_gb}G` : "—"}</td>
                      <td style={{ padding: "7px 10px", color: p.textMute, textAlign: "right" }}>{a.disk_gb != null ? `${Number(a.disk_gb).toFixed(0)}G` : "—"}</td>
                      <td style={{ padding: "7px 10px", fontWeight: 900, color: sc, fontFamily: "monospace", textAlign: "right" }}>{a.score}</td>
                      <td style={{ padding: "7px 10px" }}><StatusPill status={a.compliance_status} /></td>
                      <td style={{ padding: "7px 10px", fontFamily: "monospace", textAlign: "right",
                        color: a.patch_age_days==null ? p.textMute : a.patch_age_days>90 ? C_RED : a.patch_age_days>30 ? C_YELLOW : C_GREEN }}>
                        {a.patch_age_days!=null ? `${a.patch_age_days}d` : "—"}</td>
                      <td style={{ padding: "7px 10px", maxWidth: 220 }}>
                        {(a.failing_checks||[]).length === 0
                          ? <span style={{ color: C_GREEN, fontSize: 11 }}>✅ None</span>
                          : (a.failing_checks||[]).map(fc => (
                            <span key={fc} style={{ fontSize: 10, fontWeight: 600, padding: "1px 5px", borderRadius: 4, background: `${C_RED}15`, color: C_RED, marginRight: 3, whiteSpace: "nowrap" }}>{fc}</span>
                          ))}
                      </td>
                      <td style={{ padding: "7px 10px", color: p.textMute, whiteSpace: "nowrap", fontSize: 11 }}>
                        {a.last_scanned ? new Date(a.last_scanned).toLocaleDateString() : "—"}
                      </td>
                    </tr>
                  );
                })
              }
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
//  Credential Vault Manager  (no passwords ever shown in plaintext)
// ═══════════════════════════════════════════════════════════════════════
function CredentialVault({ p }) {
  const [creds,    setCreds]    = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form,     setForm]     = useState({ profile_name: "", os_family: "linux", port: "22", username: "", password: "", confirm: "" });
  const [busy,     setBusy]     = useState(false);
  const [msg,      setMsg]      = useState("");

  const load = () => {
    setLoading(true);
    apiFetch("/api/compliance/credentials")
      .then(d => { setCreds(d.credentials || []); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const setF = (k, v) => {
    const nf = { ...form, [k]: v };
    if (k === "os_family") nf.port = v === "linux" ? "22" : "5985";
    setForm(nf);
  };

  const save = async () => {
    if (!form.profile_name || !form.username || !form.password) { setMsg("⚠️ All fields required"); return; }
    if (form.password !== form.confirm) { setMsg("⚠️ Passwords do not match"); return; }
    setBusy(true); setMsg("");
    try {
      await apiFetch("/api/compliance/credentials", {
        method: "POST",
        body: JSON.stringify({ profile_name: form.profile_name, os_family: form.os_family, port: parseInt(form.port), username: form.username, password: form.password }),
      });
      setMsg("✅ Saved");
      setForm({ profile_name: "", os_family: "linux", port: "22", username: "", password: "", confirm: "" });
      setShowForm(false);
      load();
    } catch { setMsg("❌ Save failed"); }
    setBusy(false);
    setTimeout(() => setMsg(""), 3000);
  };

  const del = async (id, name) => {
    if (!window.confirm(`Delete profile "${name}"?`)) return;
    await apiFetch(`/api/compliance/credentials/${id}`, { method: "DELETE" });
    load();
  };

  const IS = { background: p.panelAlt, border: `1px solid ${p.border}`, borderRadius: 8, padding: "7px 12px", color: p.text, fontSize: 13, width: "100%", boxSizing: "border-box" };

  return (
    <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14, padding: "16px 20px", marginBottom: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, color: p.text }}>🔐 Credential Vault</div>
          <div style={{ fontSize: 12, color: p.textMute, marginTop: 2 }}>
            Credentials are stored securely on the server. Passwords are <strong style={{ color: C_GREEN }}>never displayed</strong> after saving.
          </div>
        </div>
        <button onClick={() => setShowForm(v => !v)} style={{ padding: "7px 16px", borderRadius: 9, border: "none", background: C_BLUE, color: "#fff", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>
          {showForm ? "✕ Cancel" : "+ Add Profile"}
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div style={{ background: p.panelAlt, borderRadius: 10, padding: "14px 16px", marginBottom: 14, border: `1px solid ${C_BLUE}30` }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 80px", gap: 10, marginBottom: 10 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: p.textMute, marginBottom: 4 }}>Profile Name</div>
              <input placeholder="e.g. Linux Root" value={form.profile_name} onChange={e => setF("profile_name", e.target.value)} style={IS} />
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: p.textMute, marginBottom: 4 }}>OS Family</div>
              <select value={form.os_family} onChange={e => setF("os_family", e.target.value)} style={IS}>
                <option value="linux">Linux (SSH)</option>
                <option value="windows">Windows (WinRM)</option>
              </select>
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: p.textMute, marginBottom: 4 }}>Port</div>
              <input type="number" value={form.port} onChange={e => setF("port", e.target.value)} style={IS} />
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 10 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: p.textMute, marginBottom: 4 }}>Username</div>
              <input placeholder="Username" value={form.username} onChange={e => setF("username", e.target.value)} style={IS} />
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: p.textMute, marginBottom: 4 }}>Password</div>
              <input type="password" placeholder="Password" value={form.password} onChange={e => setF("password", e.target.value)} style={IS} />
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: p.textMute, marginBottom: 4 }}>Confirm Password</div>
              <input type="password" placeholder="Re-enter password" value={form.confirm} onChange={e => setF("confirm", e.target.value)} style={IS} />
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button onClick={save} disabled={busy} style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: C_GREEN, color: "#fff", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>
              {busy ? "Saving…" : "💾 Save Profile"}
            </button>
            {msg && <span style={{ fontSize: 12, color: msg.startsWith("✅") ? C_GREEN : C_RED }}>{msg}</span>}
          </div>
        </div>
      )}

      {/* Existing profiles */}
      {loading
        ? <div style={{ color: p.textMute, fontSize: 13 }}>Loading…</div>
        : creds.length === 0
          ? <div style={{ color: p.textMute, fontSize: 13, padding: "10px 0" }}>
              No credential profiles yet. Add one above to enable SSH/WinRM scanning.
            </div>
          : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
              {creds.map(c => {
                const osColor = c.os_family === "linux" ? C_GREEN : C_BLUE;
                return (
                  <div key={c.id} style={{ background: p.panelAlt, border: `1px solid ${osColor}25`, borderRadius: 10, padding: "10px 14px", display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 20 }}>{c.os_family === "linux" ? "🐧" : "🪟"}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, fontSize: 13, color: p.text }}>{c.profile_name}</div>
                      <div style={{ fontSize: 11, color: p.textMute }}>{c.username} · port {c.port}</div>
                      <div style={{ fontSize: 10, color: p.textMute }}>Password: <span style={{ color: C_YELLOW }}>••••••••</span> (stored securely)</div>
                    </div>
                    <button onClick={() => del(c.id, c.profile_name)} style={{ background: `${C_RED}15`, border: `1px solid ${C_RED}30`, color: C_RED, borderRadius: 6, padding: "3px 8px", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>🗑</button>
                  </div>
                );
              })}
            </div>
          )
      }
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
//  Apply Credentials modal (per asset)
// ═══════════════════════════════════════════════════════════════════════
function ApplyCredentialModal({ assetId, hostname, onClose, onDone, p }) {
  const [creds,   setCreds]   = useState([]);
  const [selId,   setSelId]   = useState("");
  const [busy,    setBusy]    = useState(false);
  const [msg,     setMsg]     = useState("");

  useEffect(() => {
    apiFetch("/api/compliance/credentials")
      .then(d => setCreds(d.credentials || []));
  }, []);

  const apply = async () => {
    if (!selId) return;
    setBusy(true);
    try {
      await apiFetch(`/api/compliance/assets/${assetId}/credentials`, {
        method: "POST",
        body: JSON.stringify({ credential_id: parseInt(selId) }),
      });
      setMsg("✅ Credential assigned. It will be used in the next scan.");
      setTimeout(() => { onDone && onDone(); onClose(); }, 2000);
    } catch { setMsg("❌ Failed"); setBusy(false); }
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "#00000080", zIndex: 2000, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 16, padding: 28, width: 420, boxShadow: "0 20px 60px #00000060" }}>
        <div style={{ fontWeight: 800, fontSize: 16, color: p.text, marginBottom: 6 }}>🔑 Apply Credentials</div>
        <div style={{ fontSize: 13, color: p.textMute, marginBottom: 16 }}>
          Assign a stored credential profile to <strong style={{ color: p.text }}>{hostname}</strong>.<br />
          This will be used instead of the default profile on the next scan.
        </div>
        {creds.length === 0
          ? <div style={{ fontSize: 13, color: C_YELLOW, marginBottom: 16 }}>⚠️ No credentials in vault. Go to Scan Config → Credential Vault to add one.</div>
          : (
            <select value={selId} onChange={e => setSelId(e.target.value)} style={{ width: "100%", background: p.panelAlt, border: `1px solid ${p.border}`, borderRadius: 8, padding: "9px 12px", color: p.text, fontSize: 13, marginBottom: 16, boxSizing: "border-box" }}>
              <option value="">— Select profile —</option>
              {creds.map(c => <option key={c.id} value={c.id}>{c.profile_name} ({c.username} · {c.os_family} · port {c.port})</option>)}
            </select>
          )
        }
        {msg && <div style={{ fontSize: 13, color: msg.startsWith("✅") ? C_GREEN : C_RED, marginBottom: 12 }}>{msg}</div>}
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={apply} disabled={!selId || busy} style={{ flex: 1, padding: 10, borderRadius: 9, border: "none", background: selId ? C_BLUE : `${C_BLUE}40`, color: "#fff", fontWeight: 700, cursor: selId ? "pointer" : "not-allowed" }}>
            {busy ? "Assigning…" : "🔑 Assign"}
          </button>
          <button onClick={onClose} style={{ flex: 1, padding: 10, borderRadius: 9, border: `1px solid ${p.border}`, background: p.panelAlt, color: p.text, fontWeight: 600, cursor: "pointer" }}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
function ScanConfig({ p, onScanStarted }) {
  const [rules,        setRules]        = useState([]);
  const [enabled,      setEnabled]      = useState({});
  const [useSSH,       setUseSSH]       = useState(true);
  const [scanning,     setScanning]     = useState(false);
  const [msg,          setMsg]          = useState("");
  const [loading,      setLoading]      = useState(true);

  useEffect(() => {
    apiFetch("/api/compliance/rules")
      .then(d => {
        const rs = d.rules || [];
        setRules(rs);
        const init = {};
        rs.forEach(r => { init[r.id] = r.default_on; });
        setEnabled(init);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const toggle = (id) => setEnabled(prev => ({ ...prev, [id]: !prev[id] }));
  const toggleAll = (val) => {
    const all = {};
    rules.forEach(r => { all[r.id] = val; });
    setEnabled(all);
  };

  const enabledList  = rules.filter(r => enabled[r.id]).map(r => r.id);
  const totalWeight  = rules.filter(r => enabled[r.id]).reduce((s, r) => s + r.weight, 0);

  const startScan = async () => {
    if (enabledList.length === 0) { setMsg("⚠️ Enable at least one rule"); return; }
    setScanning(true); setMsg("");
    try {
      const r = await apiFetch("/api/compliance/scan", {
        method: "POST",
        body: JSON.stringify({ enabled_checks: enabledList, use_ssh: useSSH }),
      });
      setMsg(`✅ ${r.message}`);
      if (onScanStarted) onScanStarted();
    } catch { setMsg("❌ Failed to trigger scan"); }
    setScanning(false);
  };

  // Group rules by category
  const categories = [...new Set(rules.map(r => r.category))];

  const InputStyle = { background: p.panelAlt, border: `1px solid ${p.border}`, borderRadius: 8, padding: "7px 12px", color: p.text, fontSize: 13 };

  if (loading) return <div style={{ padding: 40, color: p.textMute, textAlign: "center" }}>Loading rules…</div>;

  return (
    <div>
      {/* Header + actions */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 18, color: p.text }}>⚙️ Scan Configuration</div>
          <div style={{ fontSize: 13, color: p.textMute, marginTop: 2 }}>
            Toggle which compliance rules to run · {enabledList.length} of {rules.length} rules enabled · Weight coverage: {totalWeight}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button onClick={() => toggleAll(true)}  style={{ ...InputStyle, cursor: "pointer" }}>Enable All</button>
          <button onClick={() => toggleAll(false)} style={{ ...InputStyle, cursor: "pointer" }}>Disable All</button>
        </div>
      </div>

      {/* Credential Vault */}
      <CredentialVault p={p} />

      {/* SSH/WinRM toggle */}
      <div style={{
        background: p.panel, border: `1px solid ${useSSH ? C_BLUE + "40" : p.border}`,
        borderRadius: 14, padding: "16px 20px", marginBottom: 20,
        display: "flex", alignItems: "center", gap: 20,
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: p.text, marginBottom: 4 }}>
            🔌 Enable Remote Connectivity
          </div>
          <div style={{ fontSize: 12, color: p.textMute, lineHeight: 1.6 }}>
            When enabled, the scanner will attempt SSH (Linux) and WinRM (Windows) connections
            using credentials from the vault above to collect <strong style={{ color: C_BLUE }}>real uptime</strong>,{" "}
            <strong style={{ color: C_BLUE }}>last patch date</strong> and{" "}
            <strong style={{ color: C_BLUE }}>AV/EDR presence</strong> data.<br />
            If a VM fails authentication, a <strong style={{ color: C_YELLOW }}>🔑 Apply Credentials</strong> button
            will appear in the Assets table to assign a specific profile to that server.
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 11, color: p.textMute, marginBottom: 6, fontWeight: 600 }}>
            {useSSH ? "SSH/WinRM ON" : "SSH/WinRM OFF"}
          </div>
          <div onClick={() => setUseSSH(v => !v)} style={{
            width: 52, height: 28, borderRadius: 14, position: "relative", cursor: "pointer",
            background: useSSH ? C_BLUE : `${p.border}80`,
            transition: "background .2s",
            boxShadow: useSSH ? `0 0 12px ${C_BLUE}50` : "none",
          }}>
            <div style={{
              position: "absolute", top: 4, width: 20, height: 20, borderRadius: "50%",
              background: "#fff", transition: "left .2s",
              left: useSSH ? 28 : 4, boxShadow: "0 1px 4px #0004",
            }} />
          </div>
        </div>
      </div>

      {/* Rules by category */}
      {categories.map(cat => (
        <div key={cat} style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <div style={{ width: 4, height: 18, borderRadius: 2, background: CAT_COLOR[cat] || C_BLUE }} />
            <span style={{ fontWeight: 800, fontSize: 13, color: p.text, textTransform: "uppercase", letterSpacing: ".8px" }}>{cat}</span>
            <span style={{ fontSize: 11, color: p.textMute }}>
              ({rules.filter(r => r.category === cat && enabled[r.id]).length}/{rules.filter(r => r.category === cat).length} enabled)
            </span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {rules.filter(r => r.category === cat).map(rule => (
              <RuleCard key={rule.id} rule={rule} enabled={!!enabled[rule.id]} onToggle={toggle} p={p} />
            ))}
          </div>
        </div>
      ))}

      {/* Scan button */}
      <div style={{
        position: "sticky", bottom: 0, background: p.panel,
        borderTop: `1px solid ${p.border}`, padding: "16px 0",
        display: "flex", alignItems: "center", gap: 16,
      }}>
        <button disabled={scanning || enabledList.length === 0} onClick={startScan} style={{
          padding: "12px 32px", borderRadius: 12, border: "none",
          background: scanning ? `${C_GREEN}60` : C_GREEN,
          color: "#fff", fontWeight: 800, fontSize: 16, cursor: scanning ? "wait" : "pointer",
          boxShadow: scanning ? "none" : `0 4px 20px ${C_GREEN}40`,
          transition: "all .2s",
        }}>
          {scanning ? "⏳ Scanning…" : `▶ Run CompliSphere Scan (${enabledList.length} rules)`}
        </button>
        {msg && <span style={{ fontSize: 13, color: msg.startsWith("✅") ? C_GREEN : C_RED }}>{msg}</span>}
        <span style={{ fontSize: 12, color: p.textMute, marginLeft: "auto" }}>
          Results appear in the Dashboard tab in ~2 minutes
        </span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
//  TAB: Dashboard
// ═══════════════════════════════════════════════════════════════════════
function ComplianceDashboard({ p, onDrillDown, onGoScanConfig }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    apiFetch("/api/compliance/summary")
      .then(d => { setSummary(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: p.textMute }}>🛡️ Loading CompliSphere data…</div>;

  const s     = summary || {};
  const total = s.total_assets || 0;
  const trend = s.trend || [];
  const noData = total === 0;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <div style={{ fontWeight: 900, fontSize: 20, color: p.text }}>CompliSphere Overview</div>
          <div style={{ fontSize: 13, color: p.textMute, marginTop: 2 }}>
            {s.last_scan ? `Last scan: ${new Date(s.last_scan).toLocaleString()}` : "No scans yet"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={onGoScanConfig} style={{
            padding: "9px 20px", borderRadius: 10, border: "none",
            background: C_GREEN, color: "#fff", fontWeight: 700, cursor: "pointer", fontSize: 14,
          }}>⚙️ Configure & Scan</button>
          <button onClick={load} style={{ padding: "9px 14px", borderRadius: 10, border: `1px solid ${p.border}`, background: p.panelAlt, color: p.text, fontWeight: 600, cursor: "pointer" }}>🔄</button>
        </div>
      </div>

      {noData
        ? (
          <div style={{ textAlign: "center", padding: "60px 20px", background: p.panel, border: `1px dashed ${p.border}`, borderRadius: 16 }}>
            <div style={{ fontSize: 56, marginBottom: 16 }}>🛡️</div>
            <div style={{ fontWeight: 800, fontSize: 20, color: p.text, marginBottom: 8 }}>No Compliance Data Yet</div>
            <div style={{ fontSize: 15, color: p.textMute, marginBottom: 20 }}>
              Click <strong>"Configure & Scan"</strong> to run your first CompliSphere scan.<br />
              The scanner will pull all VMs from your 6 vCenters and score them against your selected rules.
            </div>
            <button onClick={onGoScanConfig} style={{
              padding: "12px 28px", borderRadius: 12, border: "none",
              background: C_GREEN, color: "#fff", fontWeight: 800, fontSize: 16, cursor: "pointer",
            }}>⚙️ Configure & Run First Scan</button>
          </div>
        )
        : (
          <>
            {/* Donut + KPI */}
            <div style={{ display: "grid", gridTemplateColumns: "210px 1fr", gap: 20, marginBottom: 20 }}>
              <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 16, padding: 20, display: "flex", flexDirection: "column", alignItems: "center" }}>
                <DonutChart compliant={s.compliant || 0} warning={s.warning || 0} non_compliant={s.non_compliant || 0} />
                <div style={{ marginTop: 12, width: "100%" }}>
                  {[{ l: "Compliant", v: s.compliant || 0, c: C_GREEN }, { l: "Warning", v: s.warning || 0, c: C_YELLOW }, { l: "Non-Compliant", v: s.non_compliant || 0, c: C_RED }].map(item => (
                    <div key={item.l} style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                        <div style={{ width: 9, height: 9, borderRadius: "50%", background: item.c }} />
                        <span style={{ fontSize: 12, color: p.textMute }}>{item.l}</span>
                      </div>
                      <span style={{ fontWeight: 800, fontSize: 13, color: item.c, fontFamily: "monospace" }}>{item.v}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
                  {[
                    { label: "Total Assets",    val: total,               color: C_BLUE,   icon: "🖥️" },
                    { label: "Avg Score",        val: `${s.avg_score}%`,   color: C_BLUE,   icon: "📊" },
                    { label: "Compliant",        val: `${s.compliant_pct}%`,  color: C_GREEN,  icon: "✅" },
                    { label: "Non-Compliant",    val: `${s.non_compliant_pct}%`, color: C_RED, icon: "🔴" },
                  ].map(kpi => (
                    <div key={kpi.label} style={{ background: p.panel, border: `1px solid ${kpi.color}25`, borderRadius: 14, padding: "14px 16px", position: "relative", overflow: "hidden" }}>
                      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: `linear-gradient(90deg,${kpi.color}60,${kpi.color})` }} />
                      <div style={{ fontSize: 20, marginBottom: 4 }}>{kpi.icon}</div>
                      <div style={{ fontSize: 26, fontWeight: 900, color: kpi.color, fontFamily: "monospace", lineHeight: 1 }}>{kpi.val}</div>
                      <div style={{ fontSize: 11, color: p.textMute, marginTop: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".5px" }}>{kpi.label}</div>
                    </div>
                  ))}
                </div>
                <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14, padding: "14px 18px", flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 13, color: p.text, marginBottom: 8 }}>📈 90-Day Compliance Trend</div>
                  <Sparkline data={trend} field="avg_score" color={C_BLUE} h={65} w={550} />
                </div>
              </div>
            </div>

            {/* Top failures + Quick actions */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
              <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14, padding: "16px 18px" }}>
                <div style={{ fontWeight: 700, fontSize: 13, color: p.text, marginBottom: 12 }}>🔴 Most Common Failures (7 days)</div>
                {(s.top_failures || []).length === 0
                  ? <div style={{ color: p.textMute, fontSize: 13 }}>No failure data yet</div>
                  : (s.top_failures || []).map((f, i) => {
                    const name = typeof f.check_name === "string" ? f.check_name.replace(/"/g, "") : String(f.check_name);
                    const pct  = total ? Math.round(f.fail_count / total * 100) : 0;
                    return (
                      <div key={i} style={{ marginBottom: 9 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: p.text }}>{name}</span>
                          <span style={{ fontSize: 12, fontWeight: 800, color: C_RED, fontFamily: "monospace" }}>{f.fail_count} ({pct}%)</span>
                        </div>
                        <div style={{ background: p.panelAlt, borderRadius: 4, height: 5 }}>
                          <div style={{ height: 5, borderRadius: 4, background: C_RED, width: `${Math.min(pct, 100)}%` }} />
                        </div>
                      </div>
                    );
                  })
                }
              </div>
              <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14, padding: "16px 18px" }}>
                <div style={{ fontWeight: 700, fontSize: 13, color: p.text, marginBottom: 12 }}>⚡ Quick Filter</div>
                {[
                  { status: "non_compliant", label: "Non-Compliant Assets", count: s.non_compliant || 0, color: C_RED },
                  { status: "warning",       label: "Warning Assets",       count: s.warning || 0,       color: C_YELLOW },
                  { status: "compliant",     label: "Compliant Assets",     count: s.compliant || 0,     color: C_GREEN },
                ].map(item => (
                  <button key={item.status} onClick={() => onDrillDown(item.status)} style={{
                    display: "flex", alignItems: "center", gap: 12, width: "100%",
                    background: `${item.color}08`, border: `1px solid ${item.color}30`,
                    borderRadius: 10, padding: "11px 14px", cursor: "pointer", marginBottom: 7,
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = `${item.color}15`}
                  onMouseLeave={e => e.currentTarget.style.background = `${item.color}08`}>
                    <span style={{ flex: 1, fontWeight: 600, fontSize: 13, color: p.text, textAlign: "left" }}>{STATUS_ICON[item.status]} {item.label}</span>
                    <span style={{ fontWeight: 900, fontSize: 18, color: item.color, fontFamily: "monospace" }}>{item.count}</span>
                  </button>
                ))}
              </div>
            </div>
          </>
        )
      }
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
//  TAB: Assets Table
// ═══════════════════════════════════════════════════════════════════════

// Inline location editor (admin-only)
function LocationCell({ assetId, value, isAdmin, onSaved, p }) {
  const [editing, setEditing] = useState(false);
  const [loc,     setLoc]     = useState(value || "Bangalore");
  const [busy,    setBusy]    = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await apiFetch(`/api/compliance/assets/${assetId}/location`, {
        method: "PATCH", body: JSON.stringify({ location: loc }),
      });
      setEditing(false);
      if (onSaved) onSaved(loc);
    } catch { }
    setBusy(false);
  };

  if (editing) {
    return (
      <div style={{ display: "flex", gap: 4, alignItems: "center" }} onClick={e => e.stopPropagation()}>
        <input value={loc} onChange={e => setLoc(e.target.value)} autoFocus
          style={{ width: 100, background: p.panelAlt, border: `1px solid ${C_BLUE}`, borderRadius: 5, padding: "3px 6px", color: p.text, fontSize: 11 }} />
        <button onClick={save} disabled={busy} style={{ background: C_GREEN, border: "none", color: "#fff", borderRadius: 4, padding: "3px 7px", cursor: "pointer", fontSize: 10, fontWeight: 700 }}>✓</button>
        <button onClick={() => setEditing(false)} style={{ background: "none", border: "none", color: p.textMute, cursor: "pointer", fontSize: 12 }}>✕</button>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
      <span style={{ fontSize: 11, color: p.textMute }}>{loc || "Bangalore"}</span>
      {isAdmin && (
        <button onClick={e => { e.stopPropagation(); setEditing(true); }}
          title="Edit location (admin only)"
          style={{ background: "none", border: "none", color: p.textMute, cursor: "pointer", fontSize: 11, padding: "0 2px", opacity: 0.5 }}>✏️</button>
      )}
    </div>
  );
}

function ComplianceAssets({ p, initialStatus, currentUser }) {
  const isAdmin = (currentUser?.role || currentUser?.roles?.[0]) === "admin";
  const [assets,    setAssets]    = useState([]);
  const [total,     setTotal]     = useState(0);
  const [pages,     setPages]     = useState(1);
  const [page,      setPage]      = useState(1);
  const [loading,   setLoading]   = useState(false);
  const [selId,     setSelId]     = useState(null);
  const [credAsset, setCredAsset] = useState(null);
  const [colMenuOpen, setColMenuOpen] = useState(false);

  // Server-side filters (sent to API)
  const [filters, setFilters] = useState({ status: initialStatus || "", asset_type: "", os_family: "", vcenter: "", search: "" });

  // Client-side per-column text filters (applied after API response)
  const [colFilters, setColFilters] = useState({
    hostname: "", ip: "", os: "", os_ver: "", type: "", vcenter: "",
    location: "", tags: "", uptime: "", patch_age: "", missing: "", score: "", status: "",
  });
  const setCF = (k, v) => setColFilters(prev => ({ ...prev, [k]: v }));

  // Column visibility
  const ALL_COLS = [
    { id: "hostname",  label: "Hostname",        always: true },
    { id: "ip",        label: "IP" },
    { id: "os",        label: "OS" },
    { id: "os_ver",    label: "OS Ver" },
    { id: "type",      label: "Type" },
    { id: "vcenter",   label: "vCenter" },
    { id: "location",  label: "Location" },
    { id: "tags",      label: "Tags" },
    { id: "uptime",    label: "Uptime" },
    { id: "patch_age", label: "Patch Age" },
    { id: "missing",   label: "Missing" },
    { id: "score",     label: "Score" },
    { id: "status",    label: "Status" },
    { id: "actions",   label: "Actions",         always: true },
  ];
  const [visibleCols, setVisibleCols] = useState(
    () => Object.fromEntries(ALL_COLS.map(c => [c.id, true]))
  );
  const toggleCol = id => setVisibleCols(prev => ({ ...prev, [id]: !prev[id] }));
  const show = id => visibleCols[id] !== false;

  const load = useCallback((f = filters, pg = 1) => {
    setLoading(true);
    const q = new URLSearchParams({ page: pg, page_size: 50 });
    if (f.status)     q.set("status",     f.status);
    if (f.asset_type) q.set("asset_type", f.asset_type);
    if (f.os_family)  q.set("os_family",  f.os_family);
    if (f.vcenter)    q.set("vcenter",    f.vcenter);
    if (f.search)     q.set("search",     f.search);
    apiFetch(`/api/compliance/assets?${q}`)
      .then(d => { setAssets(d.assets || []); setTotal(d.total || 0); setPages(d.pages || 1); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, []);
  useEffect(() => {
    if (initialStatus) { const nf = { ...filters, status: initialStatus }; setFilters(nf); load(nf, 1); }
  }, [initialStatus]);

  const setF = (k, v) => { const nf = { ...filters, [k]: v }; setFilters(nf); setPage(1); load(nf, 1); };

  // Apply client-side column filters on top of API results
  const filteredAssets = assets.filter(a => {
    const cf = colFilters;
    const tags = Array.isArray(a.vm_tags) ? a.vm_tags.join(" ") : "";
    if (cf.hostname  && !String(a.hostname||"").toLowerCase().includes(cf.hostname.toLowerCase()))   return false;
    if (cf.ip        && !String(a.ip_address||"").toLowerCase().includes(cf.ip.toLowerCase()))       return false;
    if (cf.os        && !String(a.os_name||"").toLowerCase().includes(cf.os.toLowerCase()))          return false;
    if (cf.os_ver    && !String(a.os_version||"").toLowerCase().includes(cf.os_ver.toLowerCase()))   return false;
    if (cf.type      && !String(a.asset_type||"").toLowerCase().includes(cf.type.toLowerCase()))     return false;
    if (cf.vcenter   && !String(a.vcenter||"").toLowerCase().includes(cf.vcenter.toLowerCase()))     return false;
    if (cf.location  && !String(a.location||"").toLowerCase().includes(cf.location.toLowerCase()))   return false;
    if (cf.tags      && !tags.toLowerCase().includes(cf.tags.toLowerCase()))                          return false;
    if (cf.uptime    && !String(a.uptime_days??"-").includes(cf.uptime))                              return false;
    if (cf.patch_age && !String(a.patch_age_days??"-").includes(cf.patch_age))                       return false;
    if (cf.missing   && !String(a.missing_patches??"-").includes(cf.missing))                        return false;
    if (cf.score     && !String(a.score??"-").includes(cf.score))                                    return false;
    if (cf.status    && !String(a.compliance_status||"").toLowerCase().includes(cf.status.toLowerCase())) return false;
    return true;
  });

  const hasColFilter = Object.values(colFilters).some(v => v !== "");

  const updateLocationInList = (id, loc) => setAssets(prev => prev.map(a => a.id === id ? { ...a, location: loc } : a));

  // Shared styles
  const TH_LABEL = { fontSize: 9, fontWeight: 800, color: p.textMute, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 4, whiteSpace: "nowrap" };
  const TH_BASE  = { padding: "6px 8px 4px", background: p.panelAlt, borderBottom: `2px solid ${p.border}`, verticalAlign: "top", minWidth: 80 };
  const FI = {
    width: "100%", background: p.panel, border: `1px solid ${p.border}`,
    borderRadius: 5, padding: "3px 6px", color: p.text, fontSize: 10,
    outline: "none", marginTop: 2,
  };
  const FI_SELECT = { ...FI, paddingRight: 2 };

  return (
    <div>
      {selId     && <AssetDetailPanel assetId={selId} onClose={() => setSelId(null)} onRemediate={() => load()} p={p} currentUser={currentUser} />}
      {credAsset && <ApplyCredentialModal assetId={credAsset.id} hostname={credAsset.hostname} onClose={() => setCredAsset(null)} onDone={() => load()} p={p} />}

      {/* Top toolbar — minimal, just count + columns toggle + clear */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ fontSize: 12, color: p.textMute }}>
          {loading ? "Loading…" : `${filteredAssets.length} / ${total} assets`}
          {hasColFilter && <span style={{ color: C_YELLOW, marginLeft: 6 }}>• column filters active</span>}
        </span>
        {hasColFilter && (
          <button onClick={() => setColFilters({ hostname:"",ip:"",os:"",os_ver:"",type:"",vcenter:"",location:"",tags:"",uptime:"",patch_age:"",missing:"",score:"",status:"" })}
            style={{ padding: "3px 10px", borderRadius: 6, border: `1px solid ${C_YELLOW}40`, background: `${C_YELLOW}10`, color: C_YELLOW, fontSize: 11, fontWeight: 600, cursor: "pointer" }}>
            ✕ Clear Filters
          </button>
        )}
        {/* Column visibility toggle */}
        <div style={{ position: "relative", marginLeft: "auto" }}>
          <button onClick={() => setColMenuOpen(v => !v)}
            style={{ padding: "5px 12px", background: p.panelAlt, border: `1px solid ${p.border}`, borderRadius: 8, color: p.textMute, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            ⚙️ Columns <span style={{ fontSize: 9, opacity: 0.6 }}>▼</span>
          </button>
          {colMenuOpen && (
            <div style={{ position: "absolute", right: 0, top: "110%", zIndex: 200,
              background: p.panel, border: `1px solid ${p.border}`, borderRadius: 10,
              padding: "10px 14px", minWidth: 170, boxShadow: "0 8px 32px #0008" }}
              onMouseLeave={() => setColMenuOpen(false)}>
              <div style={{ fontSize: 9, fontWeight: 800, color: p.textMute, marginBottom: 8, textTransform: "uppercase", letterSpacing: ".5px" }}>Toggle Columns</div>
              {ALL_COLS.filter(c => !c.always).map(col => (
                <label key={col.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0", cursor: "pointer", fontSize: 12, color: p.text }}>
                  <input type="checkbox" checked={visibleCols[col.id] !== false} onChange={() => toggleCol(col.id)} style={{ accentColor: C_GREEN }} />
                  {col.label}
                </label>
              ))}
              <button onClick={() => setVisibleCols(Object.fromEntries(ALL_COLS.map(c => [c.id, true])))}
                style={{ marginTop: 8, width: "100%", padding: "5px 0", background: `${C_GREEN}15`, border: `1px solid ${C_GREEN}30`, borderRadius: 6, color: C_GREEN, fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
                Show All
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Table with per-column header filters */}
      <div style={{ background: p.panel, border: `1px solid ${p.border}`, borderRadius: 14, overflow: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr>
              {/* Hostname */}
              <th style={TH_BASE}>
                <div style={TH_LABEL}>Hostname</div>
                <input style={FI} placeholder="filter…" value={colFilters.hostname} onChange={e => setCF("hostname", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>
              {/* IP */}
              {show("ip") && <th style={TH_BASE}>
                <div style={TH_LABEL}>IP</div>
                <input style={FI} placeholder="filter…" value={colFilters.ip} onChange={e => setCF("ip", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* OS */}
              {show("os") && <th style={{ ...TH_BASE, minWidth: 130 }}>
                <div style={TH_LABEL}>OS</div>
                <input style={FI} placeholder="filter…" value={colFilters.os} onChange={e => setCF("os", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* OS Ver */}
              {show("os_ver") && <th style={TH_BASE}>
                <div style={TH_LABEL}>OS Ver</div>
                <input style={FI} placeholder="filter…" value={colFilters.os_ver} onChange={e => setCF("os_ver", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* Type */}
              {show("type") && <th style={{ ...TH_BASE, minWidth: 70 }}>
                <div style={TH_LABEL}>Type</div>
                <select style={FI_SELECT} value={colFilters.type} onChange={e => setCF("type", e.target.value)}>
                  <option value="">All</option><option value="vm">VM</option><option value="baremetal">BM</option>
                </select>
              </th>}
              {/* vCenter */}
              {show("vcenter") && <th style={TH_BASE}>
                <div style={TH_LABEL}>vCenter</div>
                <input style={FI} placeholder="filter…" value={colFilters.vcenter} onChange={e => setCF("vcenter", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* Location */}
              {show("location") && <th style={TH_BASE}>
                <div style={TH_LABEL}>Location</div>
                <input style={FI} placeholder="filter…" value={colFilters.location} onChange={e => setCF("location", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* Tags */}
              {show("tags") && <th style={{ ...TH_BASE, minWidth: 110 }}>
                <div style={TH_LABEL}>Tags</div>
                <input style={FI} placeholder="filter…" value={colFilters.tags} onChange={e => setCF("tags", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* Uptime */}
              {show("uptime") && <th style={{ ...TH_BASE, minWidth: 70 }}>
                <div style={{ ...TH_LABEL, textAlign: "right" }}>Uptime</div>
                <input style={{ ...FI, textAlign: "right" }} placeholder="e.g. 30" value={colFilters.uptime} onChange={e => setCF("uptime", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* Patch Age */}
              {show("patch_age") && <th style={{ ...TH_BASE, minWidth: 80 }}>
                <div style={{ ...TH_LABEL, textAlign: "right" }}>Patch Age</div>
                <input style={{ ...FI, textAlign: "right" }} placeholder="e.g. 90" value={colFilters.patch_age} onChange={e => setCF("patch_age", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* Missing */}
              {show("missing") && <th style={{ ...TH_BASE, minWidth: 70 }}>
                <div style={{ ...TH_LABEL, textAlign: "right" }}>Missing</div>
                <input style={{ ...FI, textAlign: "right" }} placeholder="e.g. 5" value={colFilters.missing} onChange={e => setCF("missing", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* Score */}
              {show("score") && <th style={{ ...TH_BASE, minWidth: 60 }}>
                <div style={{ ...TH_LABEL, textAlign: "right" }}>Score</div>
                <input style={{ ...FI, textAlign: "right" }} placeholder="≥" value={colFilters.score} onChange={e => setCF("score", e.target.value)} onClick={e => e.stopPropagation()} />
              </th>}
              {/* Status */}
              {show("status") && <th style={{ ...TH_BASE, minWidth: 100 }}>
                <div style={TH_LABEL}>Status</div>
                <select style={FI_SELECT} value={colFilters.status} onChange={e => setCF("status", e.target.value)}>
                  <option value="">All</option>
                  <option value="compliant">Compliant</option>
                  <option value="warning">Warning</option>
                  <option value="non_compliant">Non-Compliant</option>
                </select>
              </th>}
              {/* Actions */}
              <th style={{ ...TH_BASE, minWidth: 60 }}>
                <div style={TH_LABEL}>Actions</div>
                <div style={{ height: 22 }} />
              </th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? <tr><td colSpan={14} style={{ padding: 32, textAlign: "center", color: p.textMute }}>Loading…</td></tr>
              : filteredAssets.length === 0
                ? <tr><td colSpan={14} style={{ padding: 40, textAlign: "center", color: p.textMute }}>
                    {assets.length === 0 ? "No assets found. Run a CompliSphere scan first." : "No assets match the current filters."}
                  </td></tr>
                : filteredAssets.map(a => {
                  const sc   = STATUS_COLOR[a.compliance_status] || "#64748b";
                  const tags = Array.isArray(a.vm_tags) ? a.vm_tags : [];
                  return (
                    <tr key={a.id} onClick={() => setSelId(a.id)}
                      style={{ cursor: "pointer", borderBottom: `1px solid ${p.border}` }}
                      onMouseEnter={e => e.currentTarget.style.background = `${C_BLUE}06`}
                      onMouseLeave={e => e.currentTarget.style.background = ""}>

                      {/* Hostname — always shown */}
                      <td style={{ padding: "8px 10px", fontWeight: 700, color: p.text, whiteSpace: "nowrap" }}>{a.hostname}</td>

                      {/* IP */}
                      {show("ip") && (
                        <td style={{ padding: "8px 10px", fontFamily: "monospace", whiteSpace: "nowrap",
                          color: a.ip_address ? p.text : C_YELLOW }}>
                          {a.ip_address || <span title="No IP — VMware Tools not running">⚠️ —</span>}
                        </td>
                      )}

                      {/* OS Name */}
                      {show("os") && (
                        <td style={{ padding: "8px 10px", color: p.textMute, maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={a.os_name}>
                          {a.os_name || "—"}
                        </td>
                      )}

                      {/* OS Version */}
                      {show("os_ver") && (
                        <td style={{ padding: "8px 10px", color: p.textMute, maxWidth: 110, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={a.os_version}>
                          {a.os_version ? <span style={{ fontSize: 10 }}>{a.os_version}</span> : "—"}
                        </td>
                      )}

                      {/* Type */}
                      {show("type") && (
                        <td style={{ padding: "8px 10px" }}>
                          <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: `${C_BLUE}15`, color: C_BLUE }}>{(a.asset_type||"").toUpperCase()}</span>
                        </td>
                      )}

                      {/* vCenter */}
                      {show("vcenter") && (
                        <td style={{ padding: "8px 10px", color: p.textMute, whiteSpace: "nowrap", maxWidth: 110, overflow: "hidden", textOverflow: "ellipsis" }} title={a.vcenter}>
                          {a.vcenter || "—"}
                        </td>
                      )}

                      {/* Location */}
                      {show("location") && (
                        <td style={{ padding: "8px 10px" }} onClick={e => e.stopPropagation()}>
                          <LocationCell assetId={a.id} value={a.location} isAdmin={isAdmin} p={p}
                            onSaved={loc => updateLocationInList(a.id, loc)} />
                        </td>
                      )}

                      {/* Tags */}
                      {show("tags") && (
                        <td style={{ padding: "8px 10px", maxWidth: 160 }}>
                          {tags.length === 0
                            ? <span style={{ color: p.textMute, fontSize: 10 }}>—</span>
                            : <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                                {tags.slice(0,3).map((t,i) => (
                                  <span key={i} style={{ fontSize: 9, fontWeight: 600, padding: "1px 5px", borderRadius: 8,
                                    background: `${C_PURPLE}20`, color: C_PURPLE, border: `1px solid ${C_PURPLE}30`, whiteSpace: "nowrap" }}>
                                    🏷 {t}
                                  </span>
                                ))}
                                {tags.length > 3 && <span style={{ fontSize: 9, color: p.textMute }}>+{tags.length-3}</span>}
                              </div>
                          }
                        </td>
                      )}

                      {/* Uptime */}
                      {show("uptime") && (
                        <td style={{ padding: "8px 10px", fontFamily: "monospace", textAlign: "right",
                          color: a.uptime_days == null ? p.textMute : a.uptime_days > 365 ? C_RED : a.uptime_days > 180 ? C_YELLOW : C_GREEN }}>
                          {a.uptime_days != null
                            ? (a.uptime_days === 0 ? "<1d" : `${a.uptime_days}d`)
                            : <span style={{ opacity: 0.4 }}>—</span>}
                        </td>
                      )}

                      {/* Patch Age */}
                      {show("patch_age") && (
                        <td style={{ padding: "8px 10px", fontFamily: "monospace", textAlign: "right",
                          color: a.patch_age_days == null ? p.textMute : a.patch_age_days > 90 ? C_RED : a.patch_age_days > 30 ? C_YELLOW : C_GREEN }}>
                          {a.patch_age_days != null
                            ? (a.patch_age_days === 0 ? "<1d" : `${a.patch_age_days}d`)
                            : <span style={{ fontSize: 9, color: p.textMute, opacity: 0.5 }} title="Enable SSH/WinRM scan for patch data">SSH needed</span>}
                        </td>
                      )}

                      {/* Missing Patches */}
                      {show("missing") && (
                        <td style={{ padding: "8px 10px", fontFamily: "monospace", textAlign: "right" }}>
                          {a.patch_age_days != null
                            ? <span style={{ color: a.missing_patches > 10 ? C_RED : a.missing_patches > 0 ? C_YELLOW : C_GREEN, fontWeight: a.missing_patches > 0 ? 700 : 400 }}>
                                {a.missing_patches ?? 0}
                              </span>
                            : <span style={{ fontSize: 9, color: p.textMute, opacity: 0.5 }} title="Enable SSH/WinRM scan for patch data">SSH needed</span>}
                        </td>
                      )}

                      {/* Score */}
                      {show("score") && <td style={{ padding: "8px 10px", textAlign: "right" }}><ScoreBadge score={a.score} /></td>}

                      {/* Status */}
                      {show("status") && <td style={{ padding: "8px 10px" }}><StatusPill status={a.compliance_status} /></td>}

                      {/* Actions — always shown */}
                      <td style={{ padding: "8px 10px" }} onClick={e => e.stopPropagation()}>
                        <div style={{ display: "flex", gap: 4, flexWrap: "nowrap" }}>
                          <button onClick={() => setSelId(a.id)}
                            style={{ padding: "3px 9px", borderRadius: 5, border: `1px solid ${sc}40`, background: `${sc}10`, color: sc, fontSize: 10, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" }}>
                            Details
                          </button>
                          {a.ssh_auth_failed && (
                            <button onClick={() => setCredAsset({ id: a.id, hostname: a.hostname })}
                              style={{ padding: "3px 9px", borderRadius: 5, border: `1px solid ${C_YELLOW}50`, background: `${C_YELLOW}10`, color: C_YELLOW, fontSize: 10, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" }}
                              title="SSH/WinRM auth failed — assign credentials">
                              🔑 Creds
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
            }
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 12 }}>
          <button disabled={page <= 1} onClick={() => { const pg = page-1; setPage(pg); load(filters, pg); }}
            style={{ padding: "6px 14px", borderRadius: 8, border: `1px solid ${p.border}`, background: p.panelAlt, color: p.text, cursor: "pointer" }}>← Prev</button>
          <span style={{ padding: "6px 14px", fontSize: 12, color: p.textMute }}>Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => { const pg = page+1; setPage(pg); load(filters, pg); }}
            style={{ padding: "6px 14px", borderRadius: 8, border: `1px solid ${p.border}`, background: p.panelAlt, color: p.text, cursor: "pointer" }}>Next →</button>
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════
//  MAIN PAGE
// ═══════════════════════════════════════════════════════════════════════
export default function CompliancePage({ currentUser, p }) {
  const [tab,         setTab]         = useState("dashboard");
  const [drillStatus, setDrillStatus] = useState(null);

  const TABS = [
    { id: "dashboard",    label: "Dashboard",     icon: "🛡️" },
    { id: "cis",         label: "CIS Hardening", icon: "🔒" },
    { id: "assets",      label: "Assets",        icon: "🖥️" },
    { id: "reports",     label: "Reports",       icon: "📊" },
  ];

  const handleDrillDown = (status) => { setDrillStatus(status); setTab("assets"); };

  return (
    <div style={{ padding: 24, maxWidth: 1400 }}>
      {/* Page header */}
      <div style={{
        background: `linear-gradient(135deg,${p.panel},${p.panelAlt})`,
        border: `1px solid ${p.border}`, borderRadius: 14, padding: "16px 22px",
        display: "flex", alignItems: "center", gap: 14, marginBottom: 20,
        boxShadow: `0 4px 24px ${C_GREEN}08`,
      }}>
        <div style={{ width: 50, height: 50, borderRadius: 13, background: `linear-gradient(135deg,${C_GREEN}30,${C_GREEN}60)`, border: `1px solid ${C_GREEN}40`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24, flexShrink: 0 }}>🛡️</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 900, fontSize: 22, color: p.text, letterSpacing: "-.3px" }}>CompliSphere</div>
          <div style={{ fontSize: 13, color: p.textMute, marginTop: 2 }}>
            9 Toggleable Rules · SSH/WinRM · EOL OS · Uptime · Patch Age · VMware Tools · Snapshots · AV/EDR
          </div>
        </div>
        {[{ l: "CIS Benchmarks", c: C_BLUE }, { l: "VMware HCL", c: C_PURPLE }, { l: "COE Standards", c: C_GREEN }].map(b => (
          <span key={b.l} style={{ fontSize: 11, fontWeight: 700, padding: "4px 12px", borderRadius: 20, background: `${b.c}15`, color: b.c, border: `1px solid ${b.c}30` }}>{b.l}</span>
        ))}
      </div>

      {/* Tab bar */}
      <div style={{ display: "flex", gap: 4, marginBottom: 20, background: p.panel, border: `1px solid ${p.border}`, borderRadius: 12, padding: 4, width: "fit-content" }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => { setTab(t.id); if (t.id !== "assets") setDrillStatus(null); }}
            style={{
              padding: "9px 22px", borderRadius: 9, border: "none", cursor: "pointer",
              fontWeight: tab === t.id ? 700 : 500, fontSize: 14,
              background: tab === t.id ? `${C_GREEN}20` : "transparent",
              color: tab === t.id ? C_GREEN : p.textMute,
              transition: "all .15s",
            }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === "dashboard"    && <ComplianceDashboard p={p} onDrillDown={handleDrillDown} onGoScanConfig={() => setTab("cis")} />}
      {tab === "cis"         && <CISHardeningLazy currentUser={currentUser} />}
      {tab === "assets"      && <ComplianceAssets p={p} initialStatus={drillStatus} currentUser={currentUser} />}
      {tab === "reports"     && <ReportPage p={p} />}
    </div>
  );
}
