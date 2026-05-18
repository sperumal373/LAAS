/**
 * MigrationReportDashboard.jsx
 * Report tab component for Magic Migrate - shows per-plan and per-move-group reports
 * with download (JSON/CSV) support.
 */
import { useState, useEffect, useCallback } from "react";
import { getToken } from "./api";

const API = (path) => fetch(path, {
  credentials: "include",
  headers: { Authorization: "Bearer " + (getToken() || "") },
}).then(r => r.json());

// Generate a simple styled HTML string from report data
function buildReportHTML(report, title) {
  const esc = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  const rows = (report?.vms || []).map(vm =>
    `<tr><td>${esc(vm.name||vm)}</td><td>${esc(vm.cpu)}</td><td>${vm.memory_mb ? vm.memory_mb+' MB' : '-'}</td><td>${esc(vm.power_state)}</td><td>${esc(vm.ip_address)}</td></tr>`
  ).join("");
  const logRows = (report?.event_log || []).map(ev =>
    `<tr><td style="font-family:monospace;font-size:11px">${esc(ev.ts)}</td><td>${esc(ev.msg)}</td></tr>`
  ).join("");
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${esc(title)}</title><style>
body{font-family:Arial,sans-serif;margin:30px;color:#1e293b;background:#fff}
h1{font-size:22px;margin-bottom:4px}h2{font-size:15px;margin:20px 0 8px;color:#475569}
.meta{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;font-size:13px;margin-bottom:16px;background:#f8fafc;padding:12px;border-radius:8px}
.stats{display:flex;gap:12px;margin-bottom:16px}
.stat{background:#f1f5f9;border-radius:8px;padding:10px 18px;text-align:center}
.stat b{display:block;font-size:22px;font-weight:900}
.stat span{font-size:11px;color:#64748b}
table{width:100%;border-collapse:collapse;font-size:13px;margin-bottom:12px}
th{background:#f1f5f9;padding:7px 10px;text-align:left;font-size:12px;color:#64748b}
td{padding:6px 10px;border-bottom:1px solid #e2e8f0}
@media print{.no-print{display:none}}
</style></head><body>
<h1>📊 ${esc(title)}</h1>
<p style="color:#64748b;font-size:13px">Generated: ${new Date().toLocaleString()}</p>
<div class="meta">
  <div><b>Status:</b> ${esc(report?.status)}</div>
  <div><b>Target:</b> ${esc(report?.target_platform)}</div>
  <div><b>Created By:</b> ${esc(report?.created_by)}</div>
  ${report?.started_at ? `<div><b>Started:</b> ${esc(report.started_at?.slice(0,16))}</div>` : ""}
  ${report?.completed_at ? `<div><b>Completed:</b> ${esc(report.completed_at?.slice(0,16))}</div>` : ""}
  ${report?.duration_seconds != null ? `<div><b>Duration:</b> ${Math.ceil(report.duration_seconds/60)} min</div>` : ""}
</div>
<div class="stats">
  <div class="stat"><b>${report?.summary?.total_vms||0}</b><span>Total VMs</span></div>
  <div class="stat"><b style="color:#10b981">${report?.summary?.succeeded||0}</b><span>Succeeded</span></div>
  <div class="stat"><b style="color:#ef4444">${report?.summary?.failed||0}</b><span>Failed</span></div>
  <div class="stat"><b style="color:#f59e0b">${report?.summary?.warnings||0}</b><span>Warnings</span></div>
</div>
${rows ? `<h2>VMs Migrated</h2><table><thead><tr><th>Name</th><th>CPU</th><th>Memory</th><th>Power</th><th>IP</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
${logRows ? `<h2>Activity Log</h2><table><thead><tr><th>Timestamp</th><th>Message</th></tr></thead><tbody>${logRows}</tbody></table>` : ""}
</body></html>`;
}

function downloadHTML(report, filename) {
  const html = buildReportHTML(report, filename);
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename.replace(/ /g,"_") + "_report.html";
  a.click(); URL.revokeObjectURL(url);
}

function printPDF(report, title) {
  const html = buildReportHTML(report, title);
  const w = window.open("", "_blank");
  w.document.write(html);
  w.document.close();
  w.onload = () => { w.focus(); w.print(); };
}

const STATUS_COLOR = {
  completed: "#10b981", failed: "#ef4444", cancelled: "#f59e0b",
  executing: "#3b82f6", migrating: "#8b5cf6", planned: "#6b7280",
  preflight_passed: "#06b6d4", approved: "#22c55e",
};

const badge = (color, text) => (
  <span style={{
    padding: "3px 10px", borderRadius: 20, fontSize: 11.5, fontWeight: 700,
    background: `${color}20`, color, border: `1px solid ${color}44`,
  }}>{text}</span>
);

function StatCard({ label, value, color, p }) {
  return (
    <div style={{
      background: p.surface, border: `1px solid ${color}33`,
      borderRadius: 12, padding: "14px 20px", textAlign: "center",
      boxShadow: `0 2px 12px ${color}18`, flex: 1, minWidth: 120,
    }}>
      <div style={{ fontSize: 28, fontWeight: 900, color }}>{value}</div>
      <div style={{ fontSize: 12, color: p.textMute, marginTop: 4, fontWeight: 600 }}>{label}</div>
    </div>
  );
}

function PlanReport({ plan, p }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const loadReport = useCallback(async () => {
    if (report) { setExpanded(e => !e); return; }
    setLoading(true);
    try {
      const r = await API(`/api/migration/plans/${plan.id}/report`);
      setReport(r);
      setExpanded(true);
    } catch { } finally { setLoading(false); }
  }, [plan.id, report]);

  const download = async (fmt) => {
    const res = await fetch(`/api/migration/plans/${plan.id}/report/download?fmt=${fmt}`, {
      headers: { Authorization: "Bearer " + (getToken() || "") },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(plan.plan_name || "plan").replace(/ /g,"_")}_report.${fmt}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const sc = STATUS_COLOR[plan.status] || "#6b7280";

  return (
    <div style={{ background: p.surface, border: `1px solid ${p.border}`, borderRadius: 10, marginBottom: 10, overflow: "hidden" }}>
      <div onClick={loadReport} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", cursor: "pointer", transition: "background .15s" }}
        onMouseEnter={e => e.currentTarget.style.background = `${p.border}20`}
        onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
        <span style={{ fontSize: 16, minWidth: 20 }}>{expanded ? "▾" : "▸"}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 14, color: p.text }}>{plan.plan_name}</div>
          <div style={{ fontSize: 12, color: p.textMute, marginTop: 2 }}>
            {plan.target_platform?.toUpperCase()} · {Array.isArray(plan.vm_list) ? plan.vm_list.length : 0} VMs · {plan.created_at?.slice(0, 16)}
          </div>
        </div>
        {badge(sc, plan.status?.toUpperCase())}
        <div style={{ fontSize: 14, fontWeight: 900, color: sc, minWidth: 48, textAlign: "right" }}>{plan.progress || 0}%</div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }} onClick={e => e.stopPropagation()}>
          <button onClick={() => download("json")} title="Download JSON"
            style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid ${p.border}`, background: p.bg, color: p.textSub, fontSize: 11, cursor: "pointer", fontWeight: 700 }}>⬇ JSON</button>
          <button onClick={() => download("csv")} title="Download CSV"
            style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid ${p.border}`, background: p.bg, color: p.textSub, fontSize: 11, cursor: "pointer", fontWeight: 700 }}>⬇ CSV</button>
          <button onClick={async () => { if (!report) { const r = await API(`/api/migration/plans/${plan.id}/report`); setReport(r); downloadHTML(r, plan.plan_name || "plan"); } else downloadHTML(report, plan.plan_name || "plan"); }} title="Download HTML"
            style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid #06b6d4`, background: "#06b6d410", color: "#06b6d4", fontSize: 11, cursor: "pointer", fontWeight: 700 }}>⬇ HTML</button>
          <button onClick={async () => { if (!report) { const r = await API(`/api/migration/plans/${plan.id}/report`); setReport(r); printPDF(r, plan.plan_name || "plan"); } else printPDF(report, plan.plan_name || "plan"); }} title="Print / Save as PDF"
            style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid #ef4444`, background: "#ef444410", color: "#ef4444", fontSize: 11, cursor: "pointer", fontWeight: 700 }}>⬇ PDF</button>
        </div>
      </div>

      {loading && <div style={{ padding: "12px 20px", color: p.textMute, fontSize: 13 }}>Loading report…</div>}

      {expanded && report && (
        <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${p.border}` }}>
          {/* Summary stats */}
          <div style={{ display: "flex", gap: 10, margin: "14px 0" }}>
            <StatCard label="Total VMs"  value={report.summary?.total_vms || 0}   color="#3b82f6" p={p} />
            <StatCard label="Succeeded"  value={report.summary?.succeeded || 0}   color="#10b981" p={p} />
            <StatCard label="Failed"     value={report.summary?.failed || 0}      color="#ef4444" p={p} />
            <StatCard label="Warnings"   value={report.summary?.warnings || 0}    color="#f59e0b" p={p} />
            {report.duration_seconds != null && (
              <StatCard label="Duration" value={`${Math.ceil(report.duration_seconds/60)}m`} color="#8b5cf6" p={p} />
            )}
          </div>

          {/* Meta info */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, fontSize: 13, color: p.text, marginBottom: 14 }}>
            <div><b>Source:</b> VMware vCenter</div>
            <div><b>Target:</b> {report.target_platform?.toUpperCase()}</div>
            <div><b>Created By:</b> {report.created_by}</div>
            {report.approved_by && <div><b>Approved By:</b> {report.approved_by}</div>}
            {report.started_at && <div><b>Started:</b> {report.started_at?.slice(0,16)}</div>}
            {report.completed_at && <div><b>Completed:</b> {report.completed_at?.slice(0,16)}</div>}
          </div>

          {/* VM List */}
          {report.vms?.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12.5, fontWeight: 800, color: p.textMute, textTransform: "uppercase", letterSpacing: ".5px", marginBottom: 8 }}>VMs Migrated</div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: `${p.border}33` }}>
                      {["Name","CPU","Memory","Disk","Power","IP"].map(h => (
                        <th key={h} style={{ padding: "6px 10px", textAlign: "left", fontWeight: 700, color: p.textMute, fontSize: 11.5 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.vms.map((vm, vi) => (
                      <tr key={vi} style={{ borderBottom: `1px solid ${p.border}20` }}>
                        <td style={{ padding: "6px 10px", fontWeight: 700, color: p.text }}>{vm.name || vm}</td>
                        <td style={{ padding: "6px 10px", color: p.textSub }}>{vm.cpu || "-"}</td>
                        <td style={{ padding: "6px 10px", color: p.textSub }}>{vm.memory_mb ? `${vm.memory_mb} MB` : "-"}</td>
                        <td style={{ padding: "6px 10px", color: p.textSub }}>{vm.disk_gb ? `${vm.disk_gb} GB` : "-"}</td>
                        <td style={{ padding: "6px 10px" }}>{vm.power_state ? badge(vm.power_state === "poweredOn" ? "#10b981" : "#6b7280", vm.power_state) : "-"}</td>
                        <td style={{ padding: "6px 10px", color: p.textSub, fontFamily: "monospace", fontSize: 12 }}>{vm.ip_address || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Activity Log */}
          {report.event_log?.length > 0 && (
            <div>
              <div style={{ fontSize: 12.5, fontWeight: 800, color: p.textMute, textTransform: "uppercase", letterSpacing: ".5px", marginBottom: 8 }}>Activity Log ({report.event_log.length})</div>
              <div style={{ maxHeight: 220, overflowY: "auto", borderRadius: 8, border: `1px solid ${p.border}`, background: p.bg }}>
                {report.event_log.map((ev, ei) => (
                  <div key={ei} style={{ padding: "5px 12px", fontSize: 12.5, display: "flex", gap: 10, borderBottom: `1px solid ${p.border}10` }}>
                    <span style={{ color: p.textMute, fontFamily: "monospace", minWidth: 140, fontSize: 11.5 }}>{ev.ts}</span>
                    <span style={{ color: ev.msg?.includes("[OK]") ? "#10b981" : ev.msg?.includes("[FAIL]") ? "#ef4444" : ev.msg?.includes("[WARN]") ? "#f59e0b" : p.text }}>{ev.msg}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MoveGroupReport({ group, p }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const loadReport = useCallback(async () => {
    if (report) { setExpanded(e => !e); return; }
    setLoading(true);
    try {
      const r = await API(`/api/migration/move-groups/${group.id}/report`);
      setReport(r);
      setExpanded(true);
    } catch { } finally { setLoading(false); }
  }, [group.id, report]);

  const download = async (fmt) => {
    const res = await fetch(`/api/migration/move-groups/${group.id}/report/download?fmt=${fmt}`, {
      headers: { Authorization: "Bearer " + (getToken() || "") },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(group.name || "group").replace(/ /g,"_")}_report.${fmt}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ background: p.surface, border: `1px solid ${p.border}`, borderRadius: 10, marginBottom: 10, overflow: "hidden" }}>
      <div onClick={loadReport} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", cursor: "pointer" }}
        onMouseEnter={e => e.currentTarget.style.background = `${p.border}20`}
        onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
        <span style={{ fontSize: 16, minWidth: 20 }}>{expanded ? "▾" : "▸"}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 800, fontSize: 14, color: p.text }}>📦 {group.name}</div>
          <div style={{ fontSize: 12, color: p.textMute, marginTop: 2 }}>{group.vm_count || 0} VMs · Created {group.created_at?.slice(0, 16)}</div>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }} onClick={e => e.stopPropagation()}>
          <button onClick={() => download("json")} style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid ${p.border}`, background: p.bg, color: p.textSub, fontSize: 11, cursor: "pointer", fontWeight: 700 }}>⬇ JSON</button>
          <button onClick={() => download("csv")} style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid ${p.border}`, background: p.bg, color: p.textSub, fontSize: 11, cursor: "pointer", fontWeight: 700 }}>⬇ CSV</button>
          <button onClick={async () => { if (!report) { const r = await API(`/api/migration/move-groups/${group.id}/report`); setReport(r); downloadHTML(r, group.name || "group"); } else downloadHTML(report, group.name || "group"); }} title="Download HTML"
            style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid #06b6d4`, background: "#06b6d410", color: "#06b6d4", fontSize: 11, cursor: "pointer", fontWeight: 700 }}>⬇ HTML</button>
          <button onClick={async () => { if (!report) { const r = await API(`/api/migration/move-groups/${group.id}/report`); setReport(r); printPDF(r, group.name || "group"); } else printPDF(report, group.name || "group"); }} title="Print / Save as PDF"
            style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid #ef4444`, background: "#ef444410", color: "#ef4444", fontSize: 11, cursor: "pointer", fontWeight: 700 }}>⬇ PDF</button>
        </div>
      </div>

      {loading && <div style={{ padding: "12px 20px", color: p.textMute, fontSize: 13 }}>Loading group report…</div>}

      {expanded && report && (
        <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${p.border}` }}>
          <div style={{ display: "flex", gap: 10, margin: "14px 0" }}>
            <StatCard label="Total Plans" value={report.total_plans || 0}             color="#3b82f6" p={p} />
            <StatCard label="Total VMs"   value={report.total_vms_in_group || 0}      color="#8b5cf6" p={p} />
            <StatCard label="Succeeded"   value={report.summary?.succeeded || 0}      color="#10b981" p={p} />
            <StatCard label="Failed"      value={report.summary?.failed || 0}         color="#ef4444" p={p} />
          </div>

          {/* Per-plan breakdown */}
          {report.plans?.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12.5, fontWeight: 800, color: p.textMute, textTransform: "uppercase", letterSpacing: ".5px", marginBottom: 8 }}>Migration Plans in this Group</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: `${p.border}33` }}>
                    {["Plan Name","Target","VMs","✓ OK","✗ Fail","Progress","Status","Started","Completed"].map(h => (
                      <th key={h} style={{ padding: "6px 10px", textAlign: "left", fontWeight: 700, color: p.textMute, fontSize: 11.5, whiteSpace: "nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {report.plans.map((pl, pi) => {
                    const sc2 = STATUS_COLOR[pl.status] || "#6b7280";
                    return (
                      <tr key={pi} style={{ borderBottom: `1px solid ${p.border}20` }}>
                        <td style={{ padding: "6px 10px", fontWeight: 700, color: p.text }}>{pl.plan_name}</td>
                        <td style={{ padding: "6px 10px" }}>{badge("#3b82f6", pl.target_platform?.toUpperCase() || "-")}</td>
                        <td style={{ padding: "6px 10px", color: p.textSub }}>{pl.vms}</td>
                        <td style={{ padding: "6px 10px", color: "#10b981", fontWeight: 700 }}>{pl.succeeded}</td>
                        <td style={{ padding: "6px 10px", color: "#ef4444", fontWeight: 700 }}>{pl.failed}</td>
                        <td style={{ padding: "6px 10px", color: sc2, fontWeight: 800 }}>{pl.progress}%</td>
                        <td style={{ padding: "6px 10px" }}>{badge(sc2, pl.status?.toUpperCase())}</td>
                        <td style={{ padding: "6px 10px", color: p.textMute, fontSize: 12 }}>{pl.started_at?.slice(0,16) || "-"}</td>
                        <td style={{ padding: "6px 10px", color: p.textMute, fontSize: 12 }}>{pl.completed_at?.slice(0,16) || "-"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* VM list */}
          {report.vms?.length > 0 && (
            <div>
              <div style={{ fontSize: 12.5, fontWeight: 800, color: p.textMute, textTransform: "uppercase", letterSpacing: ".5px", marginBottom: 8 }}>VMs in Group</div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {report.vms.map((vm, vi) => (
                  <div key={vi} style={{ padding: "5px 12px", borderRadius: 20, background: `${p.border}30`, fontSize: 12.5, fontWeight: 700, color: p.text }}>
                    {vm.vm_name}
                    {vm.vcenter_name && <span style={{ fontSize: 11, color: p.textMute, marginLeft: 6 }}>({vm.vcenter_name})</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ReportDashboard({ p, currentUser }) {
  const [plans, setPlans] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("plans"); // "plans" | "groups"
  const [filterStatus, setFilterStatus] = useState("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pl, gr] = await Promise.all([
        API("/api/migration/plans"),
        API("/api/migration/move-groups"),
      ]);
      // plans API returns { plans: [...] }, move-groups returns [...] directly
      const plansArr = Array.isArray(pl) ? pl : (Array.isArray(pl?.plans) ? pl.plans : []);
      const groupsArr = Array.isArray(gr) ? gr : (Array.isArray(gr?.groups) ? gr.groups : []);
      setPlans(plansArr);
      setGroups(groupsArr);
    } catch { } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filteredPlans = filterStatus === "all" ? plans : plans.filter(p2 => p2.status === filterStatus);

  // Summary stats
  const totalVMs = plans.reduce((s, pl) => s + (Array.isArray(pl.vm_list) ? pl.vm_list.length : 0), 0);
  const completed = plans.filter(p2 => p2.status === "completed").length;
  const failed    = plans.filter(p2 => p2.status === "failed").length;
  const running   = plans.filter(p2 => ["executing","migrating","validating"].includes(p2.status)).length;

  const tdStyle = { fontSize: 12 };

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 22, fontWeight: 900, color: p.text }}>📊 Migration Reports</div>
          <div style={{ fontSize: 13, color: p.textMute, marginTop: 3 }}>View, analyze and download reports for all migration plans and move groups</div>
        </div>
        <button onClick={load} style={{ padding: "8px 18px", borderRadius: 8, border: `1px solid ${p.border}`, background: p.surface, color: p.text, fontSize: 13, cursor: "pointer", fontWeight: 700 }}>⟳ Refresh</button>
      </div>

      {/* Global summary */}
      <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
        <StatCard label="Total Plans"   value={plans.length}  color="#3b82f6" p={p} />
        <StatCard label="Total VMs"     value={totalVMs}      color="#8b5cf6" p={p} />
        <StatCard label="Completed"     value={completed}     color="#10b981" p={p} />
        <StatCard label="Failed"        value={failed}        color="#ef4444" p={p} />
        <StatCard label="Running"       value={running}       color="#f59e0b" p={p} />
        <StatCard label="Move Groups"   value={groups.length} color="#06b6d4" p={p} />
      </div>

      {/* View toggle */}
      <div style={{ display: "flex", gap: 0, background: p.surface, borderRadius: 8, border: `1px solid ${p.border}`, overflow: "hidden", marginBottom: 18, width: "fit-content" }}>
        {[["plans","📋 Plans"], ["groups","📦 Move Groups"]].map(([id, label]) => (
          <button key={id} onClick={() => setView(id)} style={{ padding: "7px 22px", fontSize: 12.5, fontWeight: 700, border: "none", cursor: "pointer", background: view === id ? p.accent : "transparent", color: view === id ? "#fff" : p.textSub, transition: "all .2s" }}>{label}</button>
        ))}
      </div>

      {loading && <div style={{ color: p.textMute, fontSize: 14, padding: "20px 0" }}>Loading reports…</div>}

      {/* Plans view */}
      {!loading && view === "plans" && (
        <div>
          {/* Filter bar */}
          <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
            <span style={{ fontSize: 12.5, color: p.textMute, fontWeight: 700 }}>Filter:</span>
            {["all","completed","failed","executing","migrating","planned","cancelled"].map(s => (
              <button key={s} onClick={() => setFilterStatus(s)}
                style={{ padding: "4px 12px", borderRadius: 20, fontSize: 12, fontWeight: 700, cursor: "pointer", border: `1px solid ${filterStatus === s ? (STATUS_COLOR[s] || p.accent) : p.border}`, background: filterStatus === s ? `${STATUS_COLOR[s] || p.accent}20` : "transparent", color: filterStatus === s ? (STATUS_COLOR[s] || p.accent) : p.textMute, transition: "all .15s" }}>
                {s === "all" ? "All" : s.toUpperCase()}
              </button>
            ))}
            <span style={{ fontSize: 12, color: p.textMute, marginLeft: "auto" }}>{filteredPlans.length} plan{filteredPlans.length !== 1 ? "s" : ""}</span>
          </div>
          {filteredPlans.length === 0
            ? <div style={{ color: p.textMute, fontSize: 14, padding: "30px 0", textAlign: "center" }}>No plans found.</div>
            : filteredPlans.map(plan => <PlanReport key={plan.id} plan={plan} p={p} />)
          }
        </div>
      )}

      {/* Move Groups view */}
      {!loading && view === "groups" && (
        <div>
          {groups.length === 0
            ? <div style={{ color: p.textMute, fontSize: 14, padding: "30px 0", textAlign: "center" }}>No move groups found.</div>
            : groups.map(g => <MoveGroupReport key={g.id} group={g} p={p} />)
          }
        </div>
      )}
    </div>
  );
}
