/**
 * CISHardening.jsx  — CompliSphere CIS Benchmark tab
 * Tabs: Dashboard | VM List | VM Detail | Exclusions | Remediation Log
 */
import React, { useState, useEffect, useCallback, useRef } from "react";

// ── Helpers ───────────────────────────────────────────────────────────────────

const API = (path, opts = {}) =>
  fetch(path, {
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + (sessionStorage.getItem("caas_token") || ""),
      ...opts.headers,
    },
    ...opts,
  }).then((r) => {
    if (!r.ok && r.status === 401) throw new Error("Unauthorized");
    return r.json();
  });

const scoreColor = (s) => {
  if (s == null) return "#6b7280";
  if (s >= 80) return "#10b981";
  if (s >= 60) return "#f59e0b";
  if (s >= 40) return "#f97316";
  return "#ef4444";
};
const scoreLabel = (s) => {
  if (s == null) return "—";
  if (s >= 80) return "Compliant";
  if (s >= 60) return "Warning";
  if (s >= 40) return "At Risk";
  return "Critical";
};

const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString());
const fmtPct = (n) => (n == null ? "—" : Number(n).toFixed(1) + "%");
const fmtDt = (d) =>
  d
    ? new Date(d).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })
    : "—";

// ── Donut Chart ───────────────────────────────────────────────────────────────

function DonutCIS({ passed = 0, failed = 0, skipped = 0, excluded = 0, size = 140, label = "" }) {
  const total = passed + failed + skipped + excluded || 1;
  const r = size / 2 - 14;
  const cx = size / 2;
  const circumference = 2 * Math.PI * r;

  const slices = [
    { v: passed,   color: "#10b981", title: "Pass" },
    { v: failed,   color: "#ef4444", title: "Fail" },
    { v: skipped,  color: "#6b7280", title: "Skip" },
    { v: excluded, color: "#8b5cf6", title: "Excluded" },
  ];

  let offset = 0;
  const arcs = slices.map((s) => {
    const pct = s.v / total;
    const dash = pct * circumference;
    const gap  = circumference - dash;
    const arc  = { ...s, dash, gap, offset };
    offset += dash;
    return arc;
  });

  const pct = Math.round((passed / total) * 100);

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {arcs.map((a, i) => (
        <circle
          key={i}
          r={r} cx={cx} cy={cx}
          fill="none" stroke={a.color} strokeWidth={18}
          strokeDasharray={`${a.dash} ${a.gap}`}
          strokeDashoffset={-a.offset + circumference * 0.25}
          style={{ transition: "stroke-dasharray 0.6s ease" }}
        >
          <title>{a.title}: {a.v}</title>
        </circle>
      ))}
      <text x={cx} y={cx - 6} textAnchor="middle" fontSize={size * 0.18} fontWeight="700" fill="#fff">
        {pct}%
      </text>
      {label && (
        <text x={cx} y={cx + size * 0.13} textAnchor="middle" fontSize={size * 0.09} fill="#9ca3af">
          {label}
        </text>
      )}
    </svg>
  );
}

// ── Gauge (score arc) ─────────────────────────────────────────────────────────

function ScoreGauge({ score, size = 80 }) {
  const pct = Math.max(0, Math.min(100, score || 0)) / 100;
  const r = size / 2 - 8;
  const cx = size / 2;
  const circumference = Math.PI * r; // half circle
  const dash = pct * circumference;
  const color = scoreColor(score);

  return (
    <svg width={size} height={size / 2 + 12} viewBox={`0 0 ${size} ${size / 2 + 12}`}>
      <path
        d={`M 8,${size / 2} A ${r},${r} 0 0 1 ${size - 8},${size / 2}`}
        fill="none" stroke="#374151" strokeWidth={10}
      />
      <path
        d={`M 8,${size / 2} A ${r},${r} 0 0 1 ${size - 8},${size / 2}`}
        fill="none" stroke={color} strokeWidth={10}
        strokeDasharray={`${dash} ${circumference}`}
        style={{ transition: "stroke-dasharray 0.7s ease" }}
      />
      <text x={cx} y={size / 2 + 10} textAnchor="middle" fontSize={13} fontWeight="700" fill={color}>
        {score != null ? Math.round(score) : "—"}
      </text>
    </svg>
  );
}

// ── Bar chart for top failures ────────────────────────────────────────────────

function TopFailuresBar({ data = [] }) {
  if (!data.length) return <p style={{ color: "#6b7280", textAlign: "center" }}>No data</p>;
  const max = Math.max(...data.map((d) => d.fail_count));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {data.slice(0, 12).map((d) => (
        <div key={d.cis_id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 58, fontSize: 11, color: "#ef4444", fontWeight: 700, flexShrink: 0 }}>
            {d.cis_id}
          </span>
          <div style={{ flex: 1, background: "#1f2937", borderRadius: 4, height: 18, position: "relative" }}>
            <div
              style={{
                width: `${(d.fail_count / max) * 100}%`, minWidth: 4,
                height: "100%", background: "linear-gradient(90deg,#ef4444,#f97316)",
                borderRadius: 4, transition: "width 0.6s ease",
              }}
            />
            <span style={{ position: "absolute", left: 6, top: 1, fontSize: 11, color: "#f9fafb" }}>
              {d.title?.substring(0, 48)}
            </span>
          </div>
          <span style={{ width: 44, textAlign: "right", fontSize: 11, color: "#f87171", fontWeight: 600 }}>
            {d.fail_count} VMs
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Score histogram ───────────────────────────────────────────────────────────

function Histogram({ data = [] }) {
  if (!data.length) return null;
  const max = Math.max(...data.map((d) => d.count));
  const bucketColor = (b) => (b >= 80 ? "#10b981" : b >= 60 ? "#f59e0b" : b >= 40 ? "#f97316" : "#ef4444");
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 70, padding: "4px 0" }}>
      {Array.from({ length: 10 }, (_, i) => i * 10).map((bucket) => {
        const item = data.find((d) => d.bucket === bucket) || { count: 0 };
        const h = max ? Math.max(4, (item.count / max) * 60) : 4;
        return (
          <div key={bucket} title={`${bucket}-${bucket + 9}%: ${item.count} VMs`}
            style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
            <div style={{ width: "100%", height: h, background: bucketColor(bucket), borderRadius: "2px 2px 0 0",
              transition: "height 0.5s ease" }} />
            <span style={{ fontSize: 9, color: "#6b7280" }}>{bucket}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Pill Badge ────────────────────────────────────────────────────────────────

function StatusPill({ status }) {
  const map = {
    pass:     { bg: "#064e3b", color: "#10b981", label: "PASS" },
    fail:     { bg: "#450a0a", color: "#ef4444", label: "FAIL" },
    skip:     { bg: "#1f2937", color: "#6b7280", label: "SKIP" },
    excluded: { bg: "#2e1065", color: "#a78bfa", label: "EXCL" },
  };
  const s = map[status] || map["skip"];
  return (
    <span style={{ background: s.bg, color: s.color, borderRadius: 4,
      padding: "1px 8px", fontSize: 10, fontWeight: 700, letterSpacing: 0.5 }}>
      {s.label}
    </span>
  );
}

// ── Section colour ────────────────────────────────────────────────────────────

const sectionColors = ["#6366f1","#f59e0b","#10b981","#3b82f6","#ef4444","#8b5cf6","#06b6d4"];
const sectionColor = (sec) => sectionColors[(parseInt(sec) || 0) % sectionColors.length];

// ─────────────────────────────────────────────────────────────────────────────
//  SUB-VIEWS
// ─────────────────────────────────────────────────────────────────────────────

// ── 1. Dashboard ──────────────────────────────────────────────────────────────

function CISDashboard({ onViewVM }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanMsg, setScanMsg] = useState("");
  const [ingestLoading, setIngestLoading] = useState(false);
  const [ingestVmName, setIngestVmName] = useState("puretest1");
  const [ingestMsg, setIngestMsg] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    API("/api/cis/dashboard")
      .then((r) => setData({
        fleet:        (r?.fleet && typeof r.fleet === "object") ? r.fleet : {},
        by_benchmark: Array.isArray(r?.by_benchmark) ? r.by_benchmark : [],
        top_failures: Array.isArray(r?.top_failures) ? r.top_failures : [],
        histogram:    Array.isArray(r?.histogram)    ? r.histogram    : [],
        recent_jobs:  Array.isArray(r?.recent_jobs)  ? r.recent_jobs  : [],
      }))
      .catch(() => setData({ fleet: {}, by_benchmark: [], top_failures: [], histogram: [], recent_jobs: [] }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const triggerScan = () => {
    setScanLoading(true); setScanMsg("");
    API("/api/cis/scan", { method: "POST", body: JSON.stringify({}) })
      .then((r) => setScanMsg(`✅ ${r.message || "Scan started"} (job #${r.job_id})`))
      .catch((e) => setScanMsg("❌ " + e.message))
      .finally(() => setScanLoading(false));
  };

  const ingestLocal = () => {
    setIngestLoading(true); setIngestMsg("");
    API("/api/cis/ingest-local", {
      method: "POST",
      body: JSON.stringify({
        file_path: "E:\\Compliance\\audit_puretest1-CIS-RHEL8_1744982923.json",
        vm_name: ingestVmName, ip: "",
      }),
    })
      .then((r) =>
        setIngestMsg(
          r.success
            ? `✅ Ingested ${r.total} checks — ${r.passed} pass / ${r.failed} fail (job #${r.job_id})`
            : `❌ ${r.error}`
        )
      )
      .catch((e) => setIngestMsg("❌ " + e.message))
      .finally(() => { setIngestLoading(false); load(); });
  };

  if (loading) return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", height:300, color:"#6b7280" }}>
      <div style={{ textAlign:"center" }}>
        <div className="spin" style={{ width:40, height:40, border:"4px solid #374151",
          borderTop:"4px solid #6366f1", borderRadius:"50%", margin:"0 auto 12px",
          animation:"spin 1s linear infinite" }} />
        Loading CIS data…
      </div>
    </div>
  );

  const f = data?.fleet || {};
  const noData = !f.total_vms;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Quick Actions ── */}
      <div style={{ display:"flex", gap:12, flexWrap:"wrap", alignItems:"center" }}>
        <button onClick={triggerScan} disabled={scanLoading}
          style={{ background:"linear-gradient(135deg,#6366f1,#8b5cf6)", color:"#fff",
            border:"none", borderRadius:8, padding:"10px 20px", cursor:"pointer",
            fontWeight:600, fontSize:14, opacity: scanLoading ? 0.7 : 1 }}>
          {scanLoading ? "⏳ Starting…" : "🚀 Scan All VMs"}
        </button>

        <div style={{ display:"flex", gap:8, alignItems:"center" }}>
          <input value={ingestVmName} onChange={(e) => setIngestVmName(e.target.value)}
            placeholder="VM name for Goss JSON"
            style={{ background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
              borderRadius:6, padding:"8px 12px", fontSize:13, width:200 }} />
          <button onClick={ingestLocal} disabled={ingestLoading}
            style={{ background:"linear-gradient(135deg,#0ea5e9,#06b6d4)", color:"#fff",
              border:"none", borderRadius:8, padding:"10px 18px", cursor:"pointer",
              fontWeight:600, fontSize:13, opacity: ingestLoading ? 0.7 : 1 }}>
            {ingestLoading ? "⏳ Ingesting…" : "📥 Ingest Goss JSON"}
          </button>
        </div>

        {(scanMsg || ingestMsg) && (
          <span style={{ color: (scanMsg||ingestMsg).startsWith("✅") ? "#10b981" : "#ef4444",
            fontSize:13, fontWeight:500 }}>
            {scanMsg || ingestMsg}
          </span>
        )}
        <button onClick={load} style={{ marginLeft:"auto", background:"#1f2937",
          color:"#9ca3af", border:"1px solid #374151", borderRadius:6, padding:"8px 14px",
          cursor:"pointer", fontSize:13 }}>⟳ Refresh</button>
      </div>

      {noData ? (
        <div style={{ textAlign:"center", padding:60, color:"#6b7280" }}>
          <div style={{ fontSize:48, marginBottom:16 }}>🔒</div>
          <p style={{ fontSize:18, fontWeight:600, color:"#9ca3af", marginBottom:8 }}>
            No CIS scan data yet
          </p>
          <p style={{ fontSize:14 }}>
            Click <b style={{color:"#6366f1"}}>Scan All VMs</b> or{" "}
            <b style={{color:"#0ea5e9"}}>Ingest Goss JSON</b> to get started.
          </p>
        </div>
      ) : (<>

        {/* ── KPI Row ── */}
        <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit,minmax(150px,1fr))", gap:14 }}>
          {[
            { label:"Total VMs Scanned", value: fmt(f.total_vms), icon:"🖥️", color:"#6366f1" },
            { label:"Avg CIS Score",     value: fmtPct(f.avg_score), icon:"📊",
              color: scoreColor(f.avg_score) },
            { label:"Compliant (≥80%)", value: fmt(f.compliant_vms), icon:"✅", color:"#10b981" },
            { label:"Warning (50-79%)", value: fmt(f.warning_vms),   icon:"⚠️", color:"#f59e0b" },
            { label:"Critical (<50%)",  value: fmt(f.critical_vms),  icon:"🔴", color:"#ef4444" },
            { label:"Total Checks",     value: fmt(f.grand_total),   icon:"📋", color:"#06b6d4" },
            { label:"Passed",           value: fmt(f.total_passed),  icon:"✔",  color:"#10b981" },
            { label:"Failed",           value: fmt(f.total_failed),  icon:"✖",  color:"#ef4444" },
          ].map((k) => (
            <div key={k.label} style={{ background:"#111827", borderRadius:12, padding:"16px 18px",
              border:"1px solid #1f2937" }}>
              <div style={{ fontSize:22, marginBottom:6 }}>{k.icon}</div>
              <div style={{ fontSize:22, fontWeight:800, color: k.color }}>{k.value}</div>
              <div style={{ fontSize:11, color:"#6b7280", marginTop:4 }}>{k.label}</div>
            </div>
          ))}
        </div>

        {/* ── Per-Benchmark Donuts + Histogram ── */}
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>
          {/* Benchmark donuts */}
          <div style={{ background:"#111827", borderRadius:14, padding:20, border:"1px solid #1f2937" }}>
            <h3 style={{ color:"#f9fafb", fontSize:15, fontWeight:700, marginBottom:16 }}>
              🎯 CIS Score by Benchmark
            </h3>
            {(!data?.by_benchmark?.length) ? (
              <p style={{ color:"#6b7280", textAlign:"center", padding:20 }}>No benchmark data</p>
            ) : (
              <div style={{ display:"flex", flexWrap:"wrap", gap:20, justifyContent:"center" }}>
                {data.by_benchmark.map((b) => (
                  <div key={b.benchmark} style={{ textAlign:"center" }}>
                    <DonutCIS
                      passed={b.passed} failed={b.failed}
                      skipped={0} excluded={0}
                      size={110}
                      label={`${b.vm_count} VM${b.vm_count !== 1 ? "s" : ""}`}
                    />
                    <div style={{ fontSize:11, color:"#9ca3af", marginTop:6, maxWidth:110 }}>
                      {b.benchmark?.replace(/_/g," ") || "Unknown"}
                    </div>
                    <div style={{ fontSize:13, fontWeight:700, color: scoreColor(b.avg_score) }}>
                      {fmtPct(b.avg_score)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Score histogram */}
          <div style={{ background:"#111827", borderRadius:14, padding:20, border:"1px solid #1f2937" }}>
            <h3 style={{ color:"#f9fafb", fontSize:15, fontWeight:700, marginBottom:4 }}>
              📈 Score Distribution
            </h3>
            <p style={{ color:"#6b7280", fontSize:12, marginBottom:10 }}>
              VMs by CIS compliance score (0–100%)
            </p>
            <Histogram data={data?.histogram || []} />
            <div style={{ display:"flex", justifyContent:"space-between", marginTop:10 }}>
              {[["🟢","≥80% Compliant",f.compliant_vms,"#10b981"],
                ["🟡","50-79% Warning",f.warning_vms,"#f59e0b"],
                ["🔴","<50% Critical",f.critical_vms,"#ef4444"]].map(([icon,lbl,val,col]) => (
                <div key={lbl} style={{ textAlign:"center" }}>
                  <div style={{ fontSize:20 }}>{icon}</div>
                  <div style={{ fontSize:14, fontWeight:700, color:col }}>{fmt(val)}</div>
                  <div style={{ fontSize:10, color:"#6b7280" }}>{lbl}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Per-OS Compliance Breakdown ── */}
        <div style={{ background:"#111827", borderRadius:14, padding:20, border:"1px solid #1f2937" }}>
          <h3 style={{ color:"#f9fafb", fontSize:15, fontWeight:700, marginBottom:16 }}>
            🖥️ OS-Flavour Compliance Breakdown
          </h3>
          {(!data?.by_benchmark?.length) ? (
            <p style={{ color:"#6b7280", textAlign:"center", padding:20 }}>No data yet</p>
          ) : (
            <div style={{ overflowX:"auto" }}>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
                <thead>
                  <tr style={{ background:"#0f172a" }}>
                    {["OS / Benchmark","VMs","Avg Score","Compliant ≥80%","Warning 50-79%","Critical <50%","Pass","Fail","Score Bar"].map(h=>(
                      <th key={h} style={{ padding:"8px 12px", color:"#6b7280",
                        textAlign:"left", fontWeight:600, borderBottom:"1px solid #1f2937",
                        whiteSpace:"nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.by_benchmark.map((b,i) => {
                    const osIcon = b.os_family==="windows" ? "🪟" : "🐧";
                    const col = scoreColor(b.avg_score);
                    return (
                      <tr key={i} style={{ borderBottom:"1px solid #1a2332" }}>
                        <td style={{ padding:"10px 12px", fontWeight:700, color:"#f9fafb" }}>
                          {osIcon} {b.os_label || b.benchmark?.replace(/_/g," ")}
                        </td>
                        <td style={{ padding:"10px 12px", color:"#9ca3af", textAlign:"center" }}>{b.vm_count}</td>
                        <td style={{ padding:"10px 12px", fontWeight:700, color:col }}>{fmtPct(b.avg_score)}</td>
                        <td style={{ padding:"10px 12px", textAlign:"center" }}>
                          <span style={{ background:"#064e3b", color:"#10b981",
                            borderRadius:12, padding:"2px 12px", fontWeight:700 }}>
                            {b.compliant ?? 0}
                          </span>
                        </td>
                        <td style={{ padding:"10px 12px", textAlign:"center" }}>
                          <span style={{ background:"#451a03", color:"#f59e0b",
                            borderRadius:12, padding:"2px 12px", fontWeight:700 }}>
                            {b.warning ?? 0}
                          </span>
                        </td>
                        <td style={{ padding:"10px 12px", textAlign:"center" }}>
                          <span style={{ background:"#450a0a", color:"#ef4444",
                            borderRadius:12, padding:"2px 12px", fontWeight:700 }}>
                            {b.critical ?? 0}
                          </span>
                        </td>
                        <td style={{ padding:"10px 12px", color:"#10b981", fontWeight:600 }}>{fmt(b.passed)}</td>
                        <td style={{ padding:"10px 12px", color:"#ef4444", fontWeight:600 }}>{fmt(b.failed)}</td>
                        <td style={{ padding:"10px 12px", minWidth:120 }}>
                          <div style={{ background:"#1f2937", borderRadius:6, height:10, overflow:"hidden" }}>
                            <div style={{ width:`${b.avg_score||0}%`, height:"100%",
                              background:`linear-gradient(90deg,${col},${col}88)`,
                              borderRadius:6, transition:"width .6s" }} />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Top Failures ── */}
        <div style={{ background:"#111827", borderRadius:14, padding:20, border:"1px solid #1f2937" }}>
          <h3 style={{ color:"#f9fafb", fontSize:15, fontWeight:700, marginBottom:14 }}>
            🚨 Top Failing CIS Controls (Fleet-wide)
          </h3>
          <TopFailuresBar data={data?.top_failures || []} />
        </div>

        {/* ── Recent Jobs ── */}
        <div style={{ background:"#111827", borderRadius:14, padding:20, border:"1px solid #1f2937" }}>
          <h3 style={{ color:"#f9fafb", fontSize:15, fontWeight:700, marginBottom:14 }}>
            📋 Recent Scan Jobs
          </h3>
          <div style={{ overflowX:"auto" }}>
            <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
              <thead>
                <tr>
                  {["Job","Status","Triggered By","Started","VMs","Checks","Pass","Fail"].map((h) => (
                    <th key={h} style={{ padding:"6px 10px", color:"#6b7280", textAlign:"left",
                      fontWeight:600, borderBottom:"1px solid #1f2937" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data?.recent_jobs || []).map((j) => (
                  <tr key={j.id} style={{ borderBottom:"1px solid #111827" }}>
                    <td style={{ padding:"6px 10px", color:"#6366f1", fontWeight:700 }}>#{j.id}</td>
                    <td style={{ padding:"6px 10px" }}>
                      <span style={{ color: j.status==="completed" ? "#10b981" :
                        j.status==="running" ? "#f59e0b" : "#6b7280",
                        fontWeight:600, fontSize:11 }}>
                        {j.status?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding:"6px 10px", color:"#9ca3af" }}>{j.triggered_by}</td>
                    <td style={{ padding:"6px 10px", color:"#9ca3af", fontSize:12 }}>{fmtDt(j.started_at)}</td>
                    <td style={{ padding:"6px 10px", color:"#f9fafb" }}>{fmt(j.scanned_vms)}/{fmt(j.target_vms)}</td>
                    <td style={{ padding:"6px 10px", color:"#f9fafb" }}>{fmt(j.total_checks)}</td>
                    <td style={{ padding:"6px 10px", color:"#10b981", fontWeight:600 }}>{fmt(j.passed_checks)}</td>
                    <td style={{ padding:"6px 10px", color:"#ef4444", fontWeight:600 }}>{fmt(j.failed_checks)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </>)}
    </div>
  );
}

// ── 2. VM List ────────────────────────────────────────────────────────────────

function CISVMList({ onSelectVM }) {
  const [data, setData]       = useState({ vms: [], total: 0, pages: 1 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch]   = useState("");
  const [osFam, setOsFam]     = useState("");
  const [benchmark, setBenchmark] = useState("");
  const [minScore, setMinScore]   = useState(0);
  const [maxScore, setMaxScore]   = useState(100);
  const [page, setPage]       = useState(1);

  const load = useCallback(() => {
    setLoading(true);
    const q = new URLSearchParams({
      search, os_family: osFam, benchmark, min_score: minScore, max_score: maxScore,
      page, page_size: 50,
    });
    API("/api/cis/vms?" + q)
      .then((r) => setData({
        vms:   Array.isArray(r?.vms)   ? r.vms   : [],
        total: typeof r?.total === "number" ? r.total : 0,
        pages: typeof r?.pages === "number" ? r.pages : 1,
      }))
      .catch(() => setData({ vms: [], total: 0, pages: 1 }))
      .finally(() => setLoading(false));
  }, [search, osFam, benchmark, minScore, maxScore, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      {/* Filters */}
      <div style={{ display:"flex", gap:10, flexWrap:"wrap", alignItems:"center" }}>
        <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="🔍 Search VM name…"
          style={{ background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
            borderRadius:6, padding:"8px 12px", fontSize:13, width:220 }} />
        <select value={osFam} onChange={(e) => { setOsFam(e.target.value); setPage(1); }}
          style={{ background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
            borderRadius:6, padding:"8px 10px", fontSize:13 }}>
          <option value="">All OS</option>
          <option value="linux">Linux</option>
          <option value="windows">Windows</option>
        </select>
        <input value={benchmark} onChange={(e) => { setBenchmark(e.target.value); setPage(1); }}
          placeholder="Benchmark filter…"
          style={{ background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
            borderRadius:6, padding:"8px 12px", fontSize:13, width:180 }} />
        <span style={{ color:"#6b7280", fontSize:13 }}>Score:</span>
        <input type="number" value={minScore} min={0} max={100}
          onChange={(e) => setMinScore(+e.target.value)}
          style={{ background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
            borderRadius:6, padding:"8px", fontSize:13, width:60 }} />
        <span style={{ color:"#6b7280" }}>–</span>
        <input type="number" value={maxScore} min={0} max={100}
          onChange={(e) => setMaxScore(+e.target.value)}
          style={{ background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
            borderRadius:6, padding:"8px", fontSize:13, width:60 }} />
        <button onClick={load} style={{ background:"#1f2937", color:"#9ca3af",
          border:"1px solid #374151", borderRadius:6, padding:"8px 14px", cursor:"pointer" }}>
          ⟳
        </button>
        <span style={{ marginLeft:"auto", color:"#6b7280", fontSize:13 }}>
          {fmt(data.total)} VMs
        </span>
      </div>

      {/* Table */}
      <div style={{ background:"#111827", borderRadius:14, border:"1px solid #1f2937", overflowX:"auto" }}>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
          <thead>
            <tr style={{ background:"#0f172a" }}>
              {["VM Name","IP","OS","Benchmark","Score","Pass","Fail","Skip","Excl","Scanned",""].map((h) => (
                <th key={h} style={{ padding:"10px 12px", color:"#6b7280", textAlign:"left",
                  fontWeight:600, borderBottom:"1px solid #1f2937", whiteSpace:"nowrap" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={11} style={{ textAlign:"center", padding:40, color:"#6b7280" }}>
                Loading…
              </td></tr>
            ) : !(data.vms || []).length ? (
              <tr><td colSpan={11} style={{ textAlign:"center", padding:40, color:"#6b7280" }}>
                No VMs found. Run a scan first.
              </td></tr>
            ) : (data.vms || []).map((vm) => (
              <tr key={vm.id}
                style={{ borderBottom:"1px solid #1a2332", cursor:"pointer",
                  transition:"background 0.15s" }}
                onMouseEnter={(e) => e.currentTarget.style.background = "#1a2332"}
                onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
                <td style={{ padding:"10px 12px", fontWeight:600, color:"#f9fafb" }}>
                  <span style={{ marginRight:6 }}>
                    {vm.os_family === "windows" ? "🪟" : "🐧"}
                  </span>
                  {vm.vm_name}
                </td>
                <td style={{ padding:"10px 12px", color:"#9ca3af", fontFamily:"monospace", fontSize:12 }}>
                  {vm.ip_address || "—"}
                </td>
                <td style={{ padding:"10px 12px", color:"#9ca3af", fontSize:12 }}>
                  {vm.os_name || vm.os_family || "—"}
                </td>
                <td style={{ padding:"10px 12px", color:"#a78bfa", fontSize:12 }}>
                  {vm.benchmark?.replace(/_/g," ") || "—"}
                </td>
                <td style={{ padding:"10px 12px" }}>
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <div style={{ width:52, height:8, background:"#1f2937", borderRadius:4, overflow:"hidden" }}>
                      <div style={{ width:`${vm.score||0}%`, height:"100%",
                        background: scoreColor(vm.score), borderRadius:4 }} />
                    </div>
                    <span style={{ fontWeight:700, color: scoreColor(vm.score), fontSize:13 }}>
                      {fmtPct(vm.score)}
                    </span>
                  </div>
                </td>
                <td style={{ padding:"10px 12px", color:"#10b981", fontWeight:600 }}>{fmt(vm.passed)}</td>
                <td style={{ padding:"10px 12px", color:"#ef4444", fontWeight:600 }}>{fmt(vm.failed)}</td>
                <td style={{ padding:"10px 12px", color:"#6b7280" }}>{fmt(vm.skipped)}</td>
                <td style={{ padding:"10px 12px", color:"#8b5cf6" }}>{fmt(vm.excluded)}</td>
                <td style={{ padding:"10px 12px", color:"#6b7280", fontSize:12 }}>{fmtDt(vm.scanned_at)}</td>
                <td style={{ padding:"10px 12px" }}>
                  <button onClick={() => onSelectVM(vm)}
                    style={{ background:"linear-gradient(135deg,#6366f1,#8b5cf6)", color:"#fff",
                      border:"none", borderRadius:6, padding:"5px 12px", cursor:"pointer",
                      fontSize:12, fontWeight:600 }}>
                    View →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {(data.pages || 0) > 1 && (
        <div style={{ display:"flex", gap:8, justifyContent:"center", flexWrap:"wrap" }}>
          {Array.from({ length: data.pages || 1 }, (_, i) => i + 1).map((p) => (
            <button key={p} onClick={() => setPage(p)}
              style={{ background: p === page ? "#6366f1" : "#1f2937",
                color: p === page ? "#fff" : "#9ca3af",
                border:"1px solid #374151", borderRadius:6, padding:"5px 12px",
                cursor:"pointer", fontWeight: p === page ? 700 : 400 }}>
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 3. VM Detail ─────────────────────────────────────────────────────────────

function CISVMDetail({ vm, onBack }) {
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [sectionFilter, setSectionFilter] = useState("");
  const [expandedSec, setExpandedSec]   = useState({});
  const [remediating, setRemediating]   = useState({});
  const [remResults, setRemResults]     = useState({});
  const [excluding, setExcluding]       = useState({});

  const load = useCallback(() => {
    setLoading(true);
    const q = new URLSearchParams({ status_filter: statusFilter, section: sectionFilter });
    API(`/api/cis/vms/${vm.id}/results?${q}`)
      .then((r) => setData({
        vm:         r?.vm         || {},
        checks:     Array.isArray(r?.checks)     ? r.checks     : [],
        by_section: r?.by_section && typeof r.by_section === "object" ? r.by_section : {},
        total:      typeof r?.total === "number"  ? r.total      : 0,
      }))
      .catch(() => setData({ vm: {}, checks: [], by_section: {}, total: 0 }))
      .finally(() => setLoading(false));
  }, [vm.id, statusFilter, sectionFilter]);

  useEffect(() => { load(); }, [load]);

  const doRemediate = (check) => {
    setRemediating((p) => ({ ...p, [check.cis_id]: true }));
    API("/api/cis/remediate", {
      method: "POST",
      body: JSON.stringify({ vm_scan_id: vm.id, cis_id: check.cis_id }),
    })
      .then((r) => setRemResults((p) => ({ ...p, [check.cis_id]: r })))
      .finally(() => setRemediating((p) => ({ ...p, [check.cis_id]: false })));
  };

  const doExclude = (check) => {
    const reason = window.prompt(`Reason for excluding ${check.cis_id}?`, "Not applicable");
    if (reason == null) return;
    setExcluding((p) => ({ ...p, [check.cis_id]: true }));
    API("/api/cis/exclusions", {
      method: "POST",
      body: JSON.stringify({ cis_id: check.cis_id, vm_name: vm.vm_name, reason }),
    })
      .then(() => load())
      .finally(() => setExcluding((p) => ({ ...p, [check.cis_id]: false })));
  };

  const sections = data ? Object.keys(data.by_section || {}).sort((a, b) => +a - +b) : [];
  const sectionNames = {
    "1": "Initial Setup", "2": "Services", "3": "Network",
    "4": "Logging & Auditing", "5": "Access Control", "6": "System Maintenance",
    "9": "Audit Policy", "18": "Advanced Security",
  };

  if (!data && loading) return (
    <div style={{ textAlign:"center", padding:60, color:"#6b7280" }}>Loading checks…</div>
  );
  if (!data) return (
    <div style={{ textAlign:"center", padding:60, color:"#6b7280" }}>No data available.</div>
  );

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      {/* Back + VM header */}
      <div style={{ display:"flex", alignItems:"center", gap:16 }}>
        <button onClick={onBack}
          style={{ background:"#1f2937", color:"#9ca3af", border:"1px solid #374151",
            borderRadius:8, padding:"8px 14px", cursor:"pointer", fontSize:13, fontWeight:600 }}>
          ← Back
        </button>
        <div>
          <h2 style={{ color:"#f9fafb", fontSize:20, fontWeight:800, margin:0 }}>
            {vm.os_family === "windows" ? "🪟" : "🐧"} {vm.vm_name}
          </h2>
          <div style={{ color:"#6b7280", fontSize:13 }}>
            {vm.ip_address} · {vm.os_name} · {vm.benchmark?.replace(/_/g," ")} · Scanned {fmtDt(vm.scanned_at)}
          </div>
        </div>

        {/* Score donut */}
        <div style={{ marginLeft:"auto", textAlign:"center" }}>
          <DonutCIS passed={vm.passed} failed={vm.failed}
            skipped={vm.skipped} excluded={vm.excluded} size={100} />
          <div style={{ fontSize:12, color: scoreColor(vm.score), fontWeight:700 }}>
            {scoreLabel(vm.score)}
          </div>
        </div>
      </div>

      {/* KPI row */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:10 }}>
        {[
          ["Total Checks", vm.total_checks, "#6366f1"],
          ["Passed",       vm.passed,       "#10b981"],
          ["Failed",       vm.failed,       "#ef4444"],
          ["Skipped",      vm.skipped,      "#6b7280"],
          ["Excluded",     vm.excluded,     "#8b5cf6"],
        ].map(([l,v,c]) => (
          <div key={l} style={{ background:"#111827", borderRadius:10, padding:"12px 14px",
            border:"1px solid #1f2937", textAlign:"center" }}>
            <div style={{ fontSize:20, fontWeight:800, color:c }}>{fmt(v)}</div>
            <div style={{ fontSize:11, color:"#6b7280" }}>{l}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display:"flex", gap:10, alignItems:"center", flexWrap:"wrap" }}>
        <span style={{ color:"#6b7280", fontSize:13 }}>Filter:</span>
        {["", "pass", "fail", "skip", "excluded"].map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)}
            style={{ background: statusFilter===s ? "#374151" : "#1f2937",
              color: statusFilter===s ? "#f9fafb" : "#6b7280",
              border: `1px solid ${statusFilter===s ? "#6366f1" : "#374151"}`,
              borderRadius:6, padding:"5px 12px", cursor:"pointer", fontSize:12, fontWeight:600 }}>
            {s || "All"} {s && `(${data?.checks?.filter(c=>c.status===s).length||0})`}
          </button>
        ))}

        <select value={sectionFilter} onChange={(e) => setSectionFilter(e.target.value)}
          style={{ marginLeft:8, background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
            borderRadius:6, padding:"5px 10px", fontSize:12 }}>
          <option value="">All Sections</option>
          {sections.map((s) => (
            <option key={s} value={s}>
              §{s} {sectionNames[s] || ""}
            </option>
          ))}
        </select>

        <button onClick={load} style={{ background:"#1f2937", color:"#9ca3af",
          border:"1px solid #374151", borderRadius:6, padding:"5px 12px", cursor:"pointer", fontSize:12 }}>
          ⟳
        </button>
        <span style={{ marginLeft:"auto", color:"#6b7280", fontSize:13 }}>
          {data?.total || 0} checks
        </span>
      </div>

      {/* Checks accordion by section */}
      {loading ? (
        <div style={{ textAlign:"center", padding:40, color:"#6b7280" }}>Loading checks…</div>
      ) : sections.length === 0 ? (
        <div style={{ textAlign:"center", padding:40, color:"#6b7280" }}>No checks match filter.</div>
      ) : sections.map((sec) => {
        const checks = data.by_section[sec] || [];
        const open   = expandedSec[sec] !== false;
        const failCount = checks.filter((c) => c.status === "fail").length;
        const passCount = checks.filter((c) => c.status === "pass").length;

        return (
          <div key={sec} style={{ background:"#111827", borderRadius:12, border:"1px solid #1f2937",
            overflow:"hidden" }}>
            <button
              onClick={() => setExpandedSec((p) => ({ ...p, [sec]: !open }))}
              style={{ width:"100%", background:"transparent", border:"none", cursor:"pointer",
                display:"flex", alignItems:"center", gap:12, padding:"14px 16px" }}>
              <span style={{ width:28, height:28, borderRadius:6, display:"flex",
                alignItems:"center", justifyContent:"center", fontSize:13, fontWeight:700,
                background: sectionColor(sec) + "33", color: sectionColor(sec) }}>
                §{sec}
              </span>
              <span style={{ color:"#f9fafb", fontWeight:700, fontSize:14 }}>
                {sectionNames[sec] || `Section ${sec}`}
              </span>
              <span style={{ color:"#6b7280", fontSize:12 }}>({checks.length} checks)</span>
              {failCount > 0 && (
                <span style={{ background:"#450a0a", color:"#ef4444", borderRadius:12,
                  padding:"1px 8px", fontSize:11, fontWeight:700 }}>
                  {failCount} FAIL
                </span>
              )}
              {passCount > 0 && (
                <span style={{ background:"#064e3b", color:"#10b981", borderRadius:12,
                  padding:"1px 8px", fontSize:11, fontWeight:700 }}>
                  {passCount} PASS
                </span>
              )}
              <span style={{ marginLeft:"auto", color:"#6b7280" }}>{open ? "▲" : "▼"}</span>
            </button>

            {open && (
              <div style={{ borderTop:"1px solid #1f2937" }}>
                {checks.map((c, i) => {
                  const rem = remResults[c.cis_id];
                  const isFail = c.status === "fail";
                  return (
                    <div key={c.id} style={{ display:"flex", gap:10, padding:"10px 16px",
                      alignItems:"flex-start",
                      background: i % 2 === 0 ? "transparent" : "#0d1117",
                      borderBottom: i < checks.length - 1 ? "1px solid #1a2332" : "none" }}>
                      <StatusPill status={c.status} />

                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ display:"flex", alignItems:"center", gap:8, flexWrap:"wrap" }}>
                          <span style={{ color:"#a78bfa", fontWeight:700, fontSize:12, fontFamily:"monospace" }}>
                            {c.cis_id}
                          </span>
                          <span style={{ color:"#f9fafb", fontSize:13 }}>{c.title}</span>
                          {c.is_ig1 && <span style={{ background:"#1e3a5f", color:"#60a5fa",
                            borderRadius:4, padding:"1px 5px", fontSize:10 }}>IG1</span>}
                          {c.is_ig2 && <span style={{ background:"#1e3a5f", color:"#60a5fa",
                            borderRadius:4, padding:"1px 5px", fontSize:10 }}>IG2</span>}
                          {c.is_ig3 && <span style={{ background:"#1e3a5f", color:"#60a5fa",
                            borderRadius:4, padding:"1px 5px", fontSize:10 }}>IG3</span>}
                        </div>
                        {isFail && (
                          <div style={{ marginTop:4, fontSize:12, color:"#6b7280" }}>
                            <span style={{ color:"#f87171" }}>Found:</span> {c.found_value || "(empty)"} |{" "}
                            <span style={{ color:"#10b981" }}>Expected:</span> {c.expected_value}
                          </div>
                        )}
                        {rem && (
                          <div style={{ marginTop:6, background:"#0d1117", borderRadius:6,
                            padding:"6px 10px", fontSize:12,
                            color: rem.success ? "#10b981" : "#ef4444" }}>
                            {rem.success ? "✅ Remediation OK" : "❌ Remediation failed"}: {rem.output?.substring(0,200)}
                          </div>
                        )}
                      </div>

                      <div style={{ display:"flex", gap:6, flexShrink:0 }}>
                        {isFail && c.remediation_cmd && (
                          <button
                            onClick={() => { if (window.confirm(`Auto-remediate "${c.title}" on ${vm.vm_name}?`)) doRemediate(c); }}
                            disabled={remediating[c.cis_id]}
                            style={{ background: remediating[c.cis_id] ? "#1f2937" : "linear-gradient(135deg,#065f46,#047857)",
                              color:"#10b981", border:"1px solid #065f46", borderRadius:6,
                              padding:"4px 10px", cursor:"pointer", fontSize:11, fontWeight:600,
                              opacity: remediating[c.cis_id] ? 0.7 : 1 }}>
                            {remediating[c.cis_id] ? "⏳" : "🔧 Fix"}
                          </button>
                        )}
                        {c.status !== "excluded" && (
                          <button
                            onClick={() => doExclude(c)}
                            disabled={excluding[c.cis_id]}
                            style={{ background:"#2e1065", color:"#a78bfa", border:"1px solid #4c1d95",
                              borderRadius:6, padding:"4px 10px", cursor:"pointer", fontSize:11,
                              opacity: excluding[c.cis_id] ? 0.7 : 1 }}>
                            {excluding[c.cis_id] ? "⏳" : "⊘ Excl"}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── 4. Exclusions Manager ─────────────────────────────────────────────────────

function CISExclusions() {
  const [excl, setExcl]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm]       = useState({ cis_id:"", vm_name:"", reason:"" });
  const [saving, setSaving]   = useState(false);
  const [msg, setMsg]         = useState("");

  const load = () => {
    setLoading(true);
    API("/api/cis/exclusions").then((r) => setExcl(r.exclusions || [])).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const add = () => {
    if (!form.cis_id) return;
    setSaving(true); setMsg("");
    API("/api/cis/exclusions", { method:"POST", body: JSON.stringify(form) })
      .then((r) => { setMsg(r.ok ? "✅ Exclusion added" : "❌ " + r.error); if (r.ok) { setForm({ cis_id:"", vm_name:"", reason:"" }); load(); } })
      .finally(() => setSaving(false));
  };

  const remove = (id) => {
    if (!window.confirm("Remove this exclusion?")) return;
    API(`/api/cis/exclusions/${id}`, { method:"DELETE" }).then(load);
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      <h3 style={{ color:"#f9fafb", fontSize:16, fontWeight:700, margin:0 }}>⊘ Exclusions Manager</h3>

      {/* Add form */}
      <div style={{ background:"#111827", borderRadius:12, padding:18, border:"1px solid #1f2937",
        display:"flex", gap:10, flexWrap:"wrap", alignItems:"flex-end" }}>
        <div>
          <div style={{ color:"#6b7280", fontSize:11, marginBottom:4 }}>CIS ID *</div>
          <input value={form.cis_id} onChange={(e) => setForm({...form, cis_id:e.target.value})}
            placeholder="e.g. 1.1.1.7"
            style={{ background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
              borderRadius:6, padding:"8px 12px", fontSize:13, width:130 }} />
        </div>
        <div>
          <div style={{ color:"#6b7280", fontSize:11, marginBottom:4 }}>VM Name (blank = global)</div>
          <input value={form.vm_name} onChange={(e) => setForm({...form, vm_name:e.target.value})}
            placeholder="hostname or blank"
            style={{ background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
              borderRadius:6, padding:"8px 12px", fontSize:13, width:180 }} />
        </div>
        <div>
          <div style={{ color:"#6b7280", fontSize:11, marginBottom:4 }}>Reason</div>
          <input value={form.reason} onChange={(e) => setForm({...form, reason:e.target.value})}
            placeholder="Reason for exclusion"
            style={{ background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
              borderRadius:6, padding:"8px 12px", fontSize:13, width:240 }} />
        </div>
        <button onClick={add} disabled={saving || !form.cis_id}
          style={{ background:"linear-gradient(135deg,#6366f1,#8b5cf6)", color:"#fff",
            border:"none", borderRadius:8, padding:"9px 18px", cursor:"pointer",
            fontWeight:600, opacity: (saving||!form.cis_id) ? 0.6 : 1 }}>
          {saving ? "Saving…" : "+ Add Exclusion"}
        </button>
        {msg && <span style={{ color: msg.startsWith("✅") ? "#10b981" : "#ef4444", fontSize:13 }}>{msg}</span>}
      </div>

      {/* Table */}
      <div style={{ background:"#111827", borderRadius:12, border:"1px solid #1f2937", overflowX:"auto" }}>
        {loading ? (
          <div style={{ padding:40, textAlign:"center", color:"#6b7280" }}>Loading…</div>
        ) : !excl.length ? (
          <div style={{ padding:40, textAlign:"center", color:"#6b7280" }}>No exclusions configured.</div>
        ) : (
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
            <thead>
              <tr style={{ background:"#0f172a" }}>
                {["CIS ID","VM Name","Reason","Excluded By","Date",""].map((h) => (
                  <th key={h} style={{ padding:"10px 12px", color:"#6b7280", textAlign:"left",
                    fontWeight:600, borderBottom:"1px solid #1f2937" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {excl.map((e) => (
                <tr key={e.id} style={{ borderBottom:"1px solid #1a2332" }}>
                  <td style={{ padding:"10px 12px", color:"#a78bfa", fontWeight:700, fontFamily:"monospace" }}>{e.cis_id}</td>
                  <td style={{ padding:"10px 12px", color:"#9ca3af" }}>{e.vm_name || <em style={{color:"#4b5563"}}>Global</em>}</td>
                  <td style={{ padding:"10px 12px", color:"#d1d5db" }}>{e.reason || "—"}</td>
                  <td style={{ padding:"10px 12px", color:"#6b7280" }}>{e.excluded_by}</td>
                  <td style={{ padding:"10px 12px", color:"#6b7280", fontSize:12 }}>{fmtDt(e.excluded_at)}</td>
                  <td style={{ padding:"10px 12px" }}>
                    <button onClick={() => remove(e.id)}
                      style={{ background:"#450a0a", color:"#ef4444", border:"1px solid #7f1d1d",
                        borderRadius:6, padding:"4px 10px", cursor:"pointer", fontSize:11 }}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── 5. Remediation Log ────────────────────────────────────────────────────────

function CISRemLog() {
  const [data, setData]       = useState({ log:[], total:0, pages:1 });
  const [loading, setLoading] = useState(true);
  const [search, setSearch]   = useState("");
  const [page, setPage]       = useState(1);

  const load = useCallback(() => {
    setLoading(true);
    const q = new URLSearchParams({ vm_name: search, page, page_size: 50 });
    API("/api/cis/remediation-log?" + q)
      .then((r) => setData({
        log:   Array.isArray(r?.log)   ? r.log   : [],
        total: typeof r?.total === "number" ? r.total : 0,
        pages: typeof r?.pages === "number" ? r.pages : 1,
      }))
      .catch(() => setData({ log: [], total: 0, pages: 1 }))
      .finally(() => setLoading(false));
  }, [search, page]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      <div style={{ display:"flex", gap:10, alignItems:"center" }}>
        <h3 style={{ color:"#f9fafb", fontSize:16, fontWeight:700, margin:0 }}>📋 Remediation Audit Log</h3>
        <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          placeholder="🔍 Filter by VM name…"
          style={{ marginLeft:"auto", background:"#1f2937", border:"1px solid #374151", color:"#f9fafb",
            borderRadius:6, padding:"7px 12px", fontSize:13, width:220 }} />
        <button onClick={load} style={{ background:"#1f2937", color:"#9ca3af",
          border:"1px solid #374151", borderRadius:6, padding:"7px 12px", cursor:"pointer" }}>⟳</button>
      </div>

      <div style={{ background:"#111827", borderRadius:12, border:"1px solid #1f2937", overflowX:"auto" }}>
        {loading ? (
          <div style={{ padding:40, textAlign:"center", color:"#6b7280" }}>Loading…</div>
        ) : !(data.log || []).length ? (
          <div style={{ padding:40, textAlign:"center", color:"#6b7280" }}>No remediation actions yet.</div>
        ) : (
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
            <thead>
              <tr style={{ background:"#0f172a" }}>
                {["VM","IP","CIS ID","Status","Output","Performed By","Date"].map((h) => (
                  <th key={h} style={{ padding:"10px 12px", color:"#6b7280", textAlign:"left",
                    fontWeight:600, borderBottom:"1px solid #1f2937" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.log.map((r) => (
                <tr key={r.id} style={{ borderBottom:"1px solid #1a2332" }}>
                  <td style={{ padding:"10px 12px", color:"#f9fafb", fontWeight:600 }}>{r.vm_name}</td>
                  <td style={{ padding:"10px 12px", color:"#9ca3af", fontFamily:"monospace", fontSize:12 }}>{r.ip_address}</td>
                  <td style={{ padding:"10px 12px", color:"#a78bfa", fontWeight:700 }}>{r.cis_id}</td>
                  <td style={{ padding:"10px 12px" }}>
                    <span style={{ color: r.success ? "#10b981" : "#ef4444", fontWeight:700 }}>
                      {r.success ? "✅ Success" : "❌ Failed"}
                    </span>
                  </td>
                  <td style={{ padding:"10px 12px", color:"#6b7280", fontSize:11, maxWidth:300,
                    overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                    {r.output || "—"}
                  </td>
                  <td style={{ padding:"10px 12px", color:"#6b7280" }}>{r.performed_by}</td>
                  <td style={{ padding:"10px 12px", color:"#6b7280", fontSize:12 }}>{fmtDt(r.performed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── 6. Reports ───────────────────────────────────────────────────────────────

async function _download(url, filename) {
  const resp = await fetch(url, {
    headers: { Authorization: "Bearer " + (sessionStorage.getItem("caas_token") || "") },
  });
  if (!resp.ok) { alert("Report generation failed: " + (await resp.text()).slice(0, 200)); return; }
  const blob = await resp.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}

function CISReports() {
  const [vms, setVms]         = useState([]);
  const [selVM, setSelVM]     = useState("");
  const [format, setFormat]   = useState("html");
  const [scope, setScope]     = useState("fleet");  // fleet | vm
  const [benchmark, setBenchmark] = useState("");
  const [osFam, setOsFam]     = useState("");
  const [loading, setLoading] = useState(false);
  const [msg, setMsg]         = useState("");

  useEffect(() => {
    API("/api/cis/vms?page_size=200").then(r => setVms(r.vms || []));
  }, []);

  const gen = async () => {
    setLoading(true); setMsg("");
    try {
      if (scope === "vm") {
        if (!selVM) { setMsg("❌ Select a VM first"); setLoading(false); return; }
        const vm = vms.find(v => String(v.id) === selVM);
        const fname = `cis_report_${vm?.vm_name || selVM}_${new Date().toISOString().slice(0,10)}.${format === "html" ? "html" : format}`;
        await _download(`/api/cis/report/vm/${selVM}?format=${format}`, fname);
        setMsg(`✅ ${fname} downloaded`);
      } else {
        const q = new URLSearchParams({ format, benchmark, os_family: osFam });
        const fname = `cis_fleet_${new Date().toISOString().slice(0,10)}.${format === "html" ? "html" : format}`;
        await _download(`/api/cis/report/fleet?${q}`, fname);
        setMsg(`✅ ${fname} downloaded`);
      }
    } catch(e) { setMsg("❌ " + e.message); }
    finally { setLoading(false); }
  };

  const fmtInfo = {
    csv:  { icon:"📊", label:"CSV",  desc:"Excel-compatible spreadsheet with all raw check data" },
    html: { icon:"🌐", label:"HTML", desc:"Styled report — open in browser, then Print → Save as PDF" },
    pdf:  { icon:"📄", label:"PDF",  desc:"Native PDF via fpdf2 (requires fpdf2 installed on server)" },
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
      <h3 style={{ color:"#f9fafb", fontSize:18, fontWeight:800, margin:0 }}>📄 Report Generation</h3>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:16 }}>

        {/* ── Scope ── */}
        <div style={{ background:"#111827", borderRadius:14, padding:20, border:"1px solid #1f2937" }}>
          <h4 style={{ color:"#9ca3af", fontSize:12, fontWeight:700, marginBottom:14,
            textTransform:"uppercase", letterSpacing:1 }}>Report Scope</h4>
          <div style={{ display:"flex", gap:10 }}>
            {[["fleet","🌐 Fleet Report (All VMs)"],["vm","🖥️ Single VM Report"]].map(([v,l]) => (
              <button key={v} onClick={() => setScope(v)}
                style={{ flex:1, padding:"12px", borderRadius:10,
                  background: scope===v ? "linear-gradient(135deg,#1e3a5f,#1e40af)" : "#1f2937",
                  color: scope===v ? "#60a5fa" : "#6b7280",
                  border: `2px solid ${scope===v ? "#3b82f6" : "#374151"}`,
                  cursor:"pointer", fontWeight:600, fontSize:13 }}>
                {l}
              </button>
            ))}
          </div>

          {scope === "vm" ? (
            <div style={{ marginTop:14 }}>
              <div style={{ color:"#6b7280", fontSize:11, marginBottom:6 }}>SELECT VM</div>
              <select value={selVM} onChange={e=>setSelVM(e.target.value)}
                style={{ width:"100%", background:"#1f2937", border:"1px solid #374151",
                  color:"#f9fafb", borderRadius:8, padding:"10px", fontSize:13 }}>
                <option value="">— Choose VM —</option>
                {vms.map(v => (
                  <option key={v.id} value={v.id}>
                    {v.os_family==="windows"?"🪟":"🐧"} {v.vm_name}  ({fmtPct(v.score)})
                  </option>
                ))}
              </select>
              {selVM && (() => { const v = vms.find(x=>String(x.id)===selVM); return v ? (
                <div style={{ marginTop:10, background:"#1f2937", borderRadius:8, padding:"10px 14px",
                  fontSize:12, color:"#9ca3af", display:"flex", gap:16 }}>
                  <span>🖥️ <b style={{color:"#f9fafb"}}>{v.vm_name}</b></span>
                  <span>OS: {v.os_name || v.os_family}</span>
                  <span>Score: <b style={{color:scoreColor(v.score)}}>{fmtPct(v.score)}</b></span>
                  <span>Pass: <b style={{color:"#10b981"}}>{v.passed}</b> Fail: <b style={{color:"#ef4444"}}>{v.failed}</b></span>
                </div>
              ) : null; })()}
            </div>
          ) : (
            <div style={{ marginTop:14, display:"flex", gap:10, flexWrap:"wrap" }}>
              <div style={{ flex:1 }}>
                <div style={{ color:"#6b7280", fontSize:11, marginBottom:4 }}>OS FILTER</div>
                <select value={osFam} onChange={e=>setOsFam(e.target.value)}
                  style={{ width:"100%", background:"#1f2937", border:"1px solid #374151",
                    color:"#f9fafb", borderRadius:8, padding:"8px", fontSize:13 }}>
                  <option value="">All OS</option>
                  <option value="linux">Linux / RHEL</option>
                  <option value="windows">Windows</option>
                </select>
              </div>
              <div style={{ flex:2 }}>
                <div style={{ color:"#6b7280", fontSize:11, marginBottom:4 }}>BENCHMARK FILTER</div>
                <input value={benchmark} onChange={e=>setBenchmark(e.target.value)}
                  placeholder="e.g. RHEL8 or 2022 (blank = all)"
                  style={{ width:"100%", background:"#1f2937", border:"1px solid #374151",
                    color:"#f9fafb", borderRadius:8, padding:"8px 12px", fontSize:13 }} />
              </div>
            </div>
          )}
        </div>

        {/* ── Format ── */}
        <div style={{ background:"#111827", borderRadius:14, padding:20, border:"1px solid #1f2937" }}>
          <h4 style={{ color:"#9ca3af", fontSize:12, fontWeight:700, marginBottom:14,
            textTransform:"uppercase", letterSpacing:1 }}>Output Format</h4>
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            {Object.entries(fmtInfo).map(([k,v]) => (
              <button key={k} onClick={() => setFormat(k)}
                style={{ padding:"14px 16px", borderRadius:10, textAlign:"left",
                  background: format===k ? "linear-gradient(135deg,#1a1a3e,#1e1b4b)" : "#1f2937",
                  border: `2px solid ${format===k ? "#6366f1" : "#374151"}`,
                  cursor:"pointer", display:"flex", alignItems:"center", gap:12 }}>
                <span style={{ fontSize:24 }}>{v.icon}</span>
                <div>
                  <div style={{ color: format===k ? "#a5b4fc" : "#9ca3af", fontWeight:700, fontSize:14 }}>
                    {v.label}
                  </div>
                  <div style={{ color:"#4b5563", fontSize:12, marginTop:2 }}>{v.desc}</div>
                </div>
                {format===k && <span style={{ marginLeft:"auto", color:"#6366f1", fontSize:18 }}>✓</span>}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Generate Button ── */}
      <div style={{ display:"flex", alignItems:"center", gap:16 }}>
        <button onClick={gen} disabled={loading}
          style={{ background: loading ? "#374151" : "linear-gradient(135deg,#6366f1,#8b5cf6)",
            color:"#fff", border:"none", borderRadius:10, padding:"14px 32px",
            cursor: loading ? "not-allowed" : "pointer", fontWeight:700, fontSize:15,
            display:"flex", alignItems:"center", gap:10, opacity: loading ? 0.7 : 1 }}>
          {loading ? (
            <><span style={{ animation:"spin 1s linear infinite", display:"inline-block" }}>⟳</span> Generating…</>
          ) : (
            <>{fmtInfo[format]?.icon} Generate & Download {fmtInfo[format]?.label}</>
          )}
        </button>
        {msg && (
          <span style={{ color: msg.startsWith("✅") ? "#10b981" : "#ef4444",
            fontSize:13, fontWeight:500 }}>{msg}</span>
        )}
      </div>

      {/* ── Quick report cards ── */}
      <div style={{ background:"#111827", borderRadius:14, padding:20, border:"1px solid #1f2937" }}>
        <h4 style={{ color:"#f9fafb", fontSize:14, fontWeight:700, marginBottom:14 }}>⚡ Quick Fleet Downloads</h4>
        <div style={{ display:"flex", gap:10, flexWrap:"wrap" }}>
          {[
            ["📊 Fleet CSV",   "csv",  "",        ""],
            ["🌐 Fleet HTML",  "html", "",        ""],
            ["📄 Fleet PDF",   "pdf",  "",        ""],
            ["🐧 Linux CSV",   "csv",  "linux",   ""],
            ["🐧 RHEL 8 HTML", "html", "linux",   "RHEL8"],
            ["🪟 Windows CSV", "csv",  "windows", ""],
            ["🪟 Win 2022 PDF","pdf",  "windows", "2022"],
          ].map(([label, fmt2, osf, bm]) => (
            <button key={label}
              onClick={async () => {
                const q = new URLSearchParams({ format: fmt2, benchmark: bm, os_family: osf });
                const ext = fmt2 === "html" ? "html" : fmt2;
                const ts = new Date().toISOString().slice(0,10);
                await _download(`/api/cis/report/fleet?${q}`, `cis_fleet_${bm||osf||"all"}_${ts}.${ext}`);
              }}
              style={{ background:"#1f2937", color:"#9ca3af", border:"1px solid #374151",
                borderRadius:8, padding:"8px 16px", cursor:"pointer", fontSize:12, fontWeight:600,
                transition:"all .2s" }}
              onMouseEnter={e=>{ e.target.style.background="#374151"; e.target.style.color="#f9fafb"; }}
              onMouseLeave={e=>{ e.target.style.background="#1f2937"; e.target.style.color="#9ca3af"; }}>
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────────────
//  MAIN COMPONENT
// ─────────────────────────────────────────────────────────────────────────────


//  Power Badge helper 
const OS_KEYS = [
  { key:"rhel8",   label:"RHEL 8",   color:"#ef4444" },
  { key:"rhel9",   label:"RHEL 9",   color:"#f97316" },
  { key:"win2016", label:"Win 2016", color:"#3b82f6" },
  { key:"win2019", label:"Win 2019", color:"#6366f1" },
];

function PwrBadge({ state }) {
  const s = (state||"unknown").toLowerCase();
  const isOn  = ["on","poweredon","powered_on","running","started"].includes(s);
  const isOff = ["off","poweredoff","powered_off","shutdown","stopped"].includes(s);
  const cfg = isOn
    ? { bg:"#064e3b", color:"#34d399", text:"On" }
    : isOff
    ? { bg:"#1f2937", color:"#6b7280", text:"Off" }
    : { bg:"#1c1917", color:"#78716c", text:"?" };
  return (
    <span style={{ background:cfg.bg, color:cfg.color, fontSize:11,
      borderRadius:4, padding:"2px 8px", fontWeight:600 }}>{cfg.text}</span>
  );
}

//  OS Group VM list (inner) 
function CISOsGroupVMs({ osKey, onViewVM }) {
  const [data, setData]     = useState({ vms:[], total:0, pages:1 });
  const [page, setPage]     = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading]   = useState(false);
  const [remTarget, setRemTarget] = useState(null);
  const [remResult, setRemResult] = useState(null);
  const [remBusy,   setRemBusy]   = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    API("/api/cis/os-groups/" + osKey + "/vms?page=" + page + "&page_size=30&search=" + encodeURIComponent(search))
      .then(d => setData(d)).catch(() => {}).finally(() => setLoading(false));
  }, [osKey, page, search]);

  useEffect(() => { load(); }, [load]);

  const doBulk = async (vm_scan_id, dry_run) => {
    setRemBusy(true);
    try {
      const r = await API("/api/cis/remediate/bulk-vm", { method:"POST",
        body: JSON.stringify({ vm_scan_id, dry_run }) });
      setRemResult({ ...r, vm_scan_id, dry_run });
    } catch(e) { setRemResult({ error: String(e) }); }
    setRemBusy(false);
  };

  return (
    <div>
      <div style={{ display:"flex", gap:8, marginBottom:12 }}>
        <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
          placeholder="Search hostname / IP..."
          style={{ flex:1, background:"#111827", border:"1px solid #374151",
            borderRadius:6, color:"#e2e8f0", padding:"7px 12px", fontSize:13 }} />
        <button onClick={load} style={{ background:"#374151", color:"#e2e8f0",
          border:"none", borderRadius:6, padding:"7px 14px", cursor:"pointer" }}>Refresh</button>
      </div>
      {loading ? <div style={{ color:"#6b7280", padding:16 }}>Loading...</div> : (
        <div style={{ overflowX:"auto" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
            <thead>
              <tr style={{ background:"#111827" }}>
                {["VM Name","IP","OS","Power","Score","Pass","Fail","Last Scan","Actions"].map(h => (
                  <th key={h} style={{ padding:"8px 10px", color:"#9ca3af", textAlign:"left",
                    borderBottom:"1px solid #1f2937", whiteSpace:"nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data.vms || []).map((vm, i) => (
                <tr key={i} style={{ borderBottom:"1px solid #111827" }}>
                  <td style={{ padding:"8px 10px", color:"#e2e8f0", fontWeight:600 }}>{vm.hostname}</td>
                  <td style={{ padding:"8px 10px", color:"#6b7280", fontFamily:"monospace" }}>{vm.ip_address || "-"}</td>
                  <td style={{ padding:"8px 10px", color:"#9ca3af", maxWidth:160, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{vm.os_name || "-"}</td>
                  <td style={{ padding:"8px 10px" }}><PwrBadge state={vm.power_state} /></td>
                  <td style={{ padding:"8px 10px" }}>
                    {vm.score != null
                      ? <span style={{ color:scoreColor(vm.score), fontWeight:700 }}>{Number(vm.score).toFixed(1)}%</span>
                      : <span style={{ color:"#6b7280" }}>-</span>}
                  </td>
                  <td style={{ padding:"8px 10px", color:"#10b981" }}>{vm.passed ?? 0}</td>
                  <td style={{ padding:"8px 10px", color:"#ef4444" }}>{vm.failed ?? 0}</td>
                  <td style={{ padding:"8px 10px", color:"#6b7280", whiteSpace:"nowrap" }}>{fmtDt(vm.scanned_at)}</td>
                  <td style={{ padding:"8px 10px" }}>
                    <div style={{ display:"flex", gap:5 }}>
                      {vm.vm_scan_id && (
                        <>
                          <button onClick={() => onViewVM(vm)}
                            style={{ background:"#1d4ed8", color:"#fff", border:"none",
                              borderRadius:5, padding:"3px 9px", fontSize:11, cursor:"pointer" }}>Detail</button>
                          <button onClick={() => { setRemTarget(vm); doBulk(vm.vm_scan_id, true); }}
                            style={{ background:"#7c3aed", color:"#fff", border:"none",
                              borderRadius:5, padding:"3px 9px", fontSize:11, cursor:"pointer" }}>Fix All</button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div style={{ display:"flex", gap:8, justifyContent:"center", marginTop:12 }}>
              <button disabled={page<=1} onClick={() => setPage(p => p-1)}
                style={{ background:"#1f2937", color:page<=1?"#374151":"#e2e8f0",
                  border:"none", borderRadius:5, padding:"4px 14px" }}>Prev</button>
              <span style={{ color:"#6b7280", alignSelf:"center", fontSize:13 }}>Page {page}/{data.pages}</span>
              <button disabled={page>=data.pages} onClick={() => setPage(p => p+1)}
                style={{ background:"#1f2937", color:page>=data.pages?"#374151":"#e2e8f0",
                  border:"none", borderRadius:5, padding:"4px 14px" }}>Next</button>
            </div>
          )}
        </div>
      )}

      {remTarget && remResult && (
        <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.75)",
          display:"flex", alignItems:"center", justifyContent:"center", zIndex:9999 }}>
          <div style={{ background:"#111827", border:"1px solid #374151", borderRadius:12,
            padding:24, width:540, maxHeight:"80vh", overflowY:"auto" }}>
            <h3 style={{ color:"#f9fafb", margin:"0 0 12px" }}>Fix All Failed - {remTarget.hostname}</h3>
            {remResult.error && <div style={{ color:"#ef4444" }}>{remResult.error}</div>}
            {remResult.dry_run && !remResult.error && (
              <>
                <p style={{ color:"#9ca3af", fontSize:13, margin:"0 0 10px" }}>
                  Found <strong style={{ color:"#f59e0b" }}>{remResult.total_to_fix}</strong> failed checks with auto-fix commands.
                </p>
                <div style={{ maxHeight:200, overflowY:"auto", marginBottom:14 }}>
                  {(remResult.checks || []).map((c, i) => (
                    <div key={i} style={{ color:"#e2e8f0", fontSize:12, padding:"4px 0",
                      borderBottom:"1px solid #1f2937" }}>
                      <strong style={{ color:"#a78bfa" }}>{c.cis_id}</strong> - {c.title}
                    </div>
                  ))}
                </div>
                <div style={{ display:"flex", gap:8 }}>
                  <button disabled={remBusy} onClick={() => doBulk(remTarget.vm_scan_id, false)}
                    style={{ background:"#7c3aed", color:"#fff", border:"none",
                      borderRadius:7, padding:"8px 20px", cursor:"pointer", fontWeight:700 }}>
                    {remBusy ? "Running..." : "Confirm & Execute"}
                  </button>
                  <button onClick={() => { setRemTarget(null); setRemResult(null); }}
                    style={{ background:"#374151", color:"#e2e8f0", border:"none",
                      borderRadius:7, padding:"8px 20px", cursor:"pointer" }}>Cancel</button>
                </div>
              </>
            )}
            {!remResult.dry_run && !remResult.error && (
              <>
                <div style={{ display:"flex", gap:14, marginBottom:14 }}>
                  <div style={{ background:"#064e3b", borderRadius:8, padding:"8px 18px", textAlign:"center" }}>
                    <div style={{ color:"#34d399", fontSize:24, fontWeight:800 }}>{remResult.fixed}</div>
                    <div style={{ color:"#6ee7b7", fontSize:11 }}>FIXED</div>
                  </div>
                  <div style={{ background:"#450a0a", borderRadius:8, padding:"8px 18px", textAlign:"center" }}>
                    <div style={{ color:"#ef4444", fontSize:24, fontWeight:800 }}>{remResult.failed}</div>
                    <div style={{ color:"#fca5a5", fontSize:11 }}>FAILED</div>
                  </div>
                </div>
                <div style={{ maxHeight:240, overflowY:"auto", marginBottom:12 }}>
                  {(remResult.results || []).map((r, i) => (
                    <div key={i} style={{ padding:"5px 0", borderBottom:"1px solid #1f2937", fontSize:12 }}>
                      <span style={{ color:r.success?"#34d399":"#ef4444", marginRight:8 }}>
                        {r.success ? "OK" : "FAIL"}
                      </span>
                      <strong style={{ color:"#a78bfa" }}>{r.cis_id}</strong>
                      {" - "}<span style={{ color:"#9ca3af" }}>{r.title}</span>
                    </div>
                  ))}
                </div>
                <button onClick={() => { setRemTarget(null); setRemResult(null); load(); }}
                  style={{ background:"#1f2937", color:"#e2e8f0", border:"none",
                    borderRadius:7, padding:"8px 20px", cursor:"pointer" }}>Close</button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

//  OS Groups tab 
function CISOsGroups({ onViewVM }) {
  const [groups,  setGroups]  = useState([]);
  const [selKey,  setSelKey]  = useState("rhel8");
  const [scanning, setScanning] = useState(false);
  const [scanMsg,  setScanMsg]  = useState("");

  useEffect(() => {
    API("/api/cis/os-groups")
      .then(d => setGroups(d.os_groups || []))
      .catch(() => {});
  }, []);

  const triggerScan = async (os_key) => {
    setScanning(true); setScanMsg("");
    try {
      const r = await API("/api/cis/scan", { method:"POST",
        body: JSON.stringify({ os_filter: os_key }) });
      setScanMsg(r.message || ("Scan started - job #" + r.job_id));
    } catch(e) { setScanMsg("Error: " + e); }
    setScanning(false);
  };

  const grpMap = {};
  groups.forEach(g => { grpMap[g.os_key] = g; });

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:20 }}>
      <div style={{ display:"flex", gap:12, flexWrap:"wrap" }}>
        {OS_KEYS.map(osk => {
          const g = grpMap[osk.key] || {};
          const active = selKey === osk.key;
          return (
            <div key={osk.key} onClick={() => setSelKey(osk.key)}
              style={{ background: active ? "#1e1b4b" : "#111827",
                border:"2px solid " + (active ? osk.color : "#1f2937"),
                borderRadius:12, padding:"14px 18px", cursor:"pointer",
                minWidth:180, flex:1, transition:"all 0.2s" }}>
              <div style={{ color:"#f9fafb", fontWeight:700, fontSize:15 }}>{osk.label}</div>
              <div style={{ color:"#6b7280", fontSize:12, marginBottom:8 }}>{g.total_vms || 0} VMs</div>
              <div style={{ display:"flex", gap:10, fontSize:12, marginBottom:8 }}>
                <span style={{ color:"#34d399" }}>On: {g.powered_on || 0}</span>
                <span style={{ color:"#6b7280" }}>Off: {g.powered_off || 0}</span>
              </div>
              {g.avg_score != null && (
                <div style={{ color:scoreColor(g.avg_score), fontWeight:700, fontSize:14, marginBottom:10 }}>
                  Avg: {Number(g.avg_score).toFixed(1)}%
                </div>
              )}
              <button disabled={scanning}
                onClick={e => { e.stopPropagation(); triggerScan(osk.key); }}
                style={{ background:osk.color, color:"#fff", border:"none",
                  borderRadius:6, padding:"5px 12px", fontSize:12, cursor:"pointer",
                  opacity:scanning?0.6:1, width:"100%" }}>
                {scanning ? "Starting..." : "Scan This OS"}
              </button>
            </div>
          );
        })}
      </div>
      {scanMsg && (
        <div style={{ background:"#0c4a6e", border:"1px solid #0ea5e9",
          borderRadius:8, padding:"8px 16px", color:"#7dd3fc", fontSize:13 }}>
          {scanMsg}
        </div>
      )}
      <div style={{ background:"#0d1117", border:"1px solid #1f2937", borderRadius:12, padding:16 }}>
        <div style={{ color:"#f9fafb", fontWeight:700, marginBottom:12, fontSize:15 }}>
          {(OS_KEYS.find(o => o.key === selKey) || {}).label} - VM List
        </div>
        <CISOsGroupVMs osKey={selKey} onViewVM={onViewVM} />
      </div>
    </div>
  );
}

//  Scan History tab 
function CISScanHistory() {
  const [data,     setData]     = useState({ jobs:[], total:0, pages:1 });
  const [page,     setPage]     = useState(1);
  const [osFilter, setOsFilter] = useState("");
  const [loading,  setLoading]  = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    const q = osFilter ? "&os_filter=" + osFilter : "";
    API("/api/cis/scan-history?page=" + page + "&page_size=20" + q)
      .then(d => setData(d)).catch(() => {}).finally(() => setLoading(false));
  }, [page, osFilter]);

  useEffect(() => { load(); }, [load]);

  const stColor = s => s==="completed"?"#10b981":s==="running"?"#f59e0b":s==="failed"?"#ef4444":"#6b7280";

  return (
    <div>
      <div style={{ display:"flex", gap:8, marginBottom:14, alignItems:"center", flexWrap:"wrap" }}>
        <select value={osFilter} onChange={e => { setOsFilter(e.target.value); setPage(1); }}
          style={{ background:"#111827", border:"1px solid #374151", borderRadius:6,
            color:"#e2e8f0", padding:"7px 12px", fontSize:13 }}>
          <option value="">All OS</option>
          <option value="rhel8">RHEL 8</option>
          <option value="rhel9">RHEL 9</option>
          <option value="win2016">Win 2016</option>
          <option value="win2019">Win 2019</option>
        </select>
        <button onClick={load} style={{ background:"#374151", color:"#e2e8f0",
          border:"none", borderRadius:6, padding:"7px 14px", cursor:"pointer" }}>Refresh</button>
        <span style={{ color:"#6b7280", fontSize:12 }}>Total: {data.total} scans</span>
      </div>
      {loading ? <div style={{ color:"#6b7280" }}>Loading...</div> : (
        <div style={{ overflowX:"auto" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:13 }}>
            <thead>
              <tr style={{ background:"#111827" }}>
                {["#","Status","OS Filter","Started","Duration","VMs","PowerOn","PowerOff","NA","Pass","Fail","By"].map(h => (
                  <th key={h} style={{ padding:"8px 10px", color:"#9ca3af", textAlign:"left",
                    borderBottom:"1px solid #1f2937", whiteSpace:"nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data.jobs || []).map((j, i) => (
                <tr key={i} style={{ borderBottom:"1px solid #111827" }}>
                  <td style={{ padding:"8px 10px", color:"#6b7280" }}>{j.id}</td>
                  <td style={{ padding:"8px 10px" }}>
                    <span style={{ color:stColor(j.status), fontWeight:600 }}>{j.status}</span>
                  </td>
                  <td style={{ padding:"8px 10px", color:"#a78bfa" }}>{j.os_filter || "All"}</td>
                  <td style={{ padding:"8px 10px", color:"#9ca3af", whiteSpace:"nowrap" }}>{fmtDt(j.started_at)}</td>
                  <td style={{ padding:"8px 10px", color:"#e2e8f0" }}>
                    {j.duration_sec ? (Math.floor(j.duration_sec/60) + "m " + Math.round(j.duration_sec%60) + "s") : "-"}
                  </td>
                  <td style={{ padding:"8px 10px", color:"#e2e8f0" }}>{j.scanned_vms||0}/{j.target_vms||0}</td>
                  <td style={{ padding:"8px 10px", color:"#34d399" }}>{j.powered_on||0}</td>
                  <td style={{ padding:"8px 10px", color:"#6b7280" }}>{j.powered_off||0}</td>
                  <td style={{ padding:"8px 10px", color:"#f97316" }}>{j.not_accessible||0}</td>
                  <td style={{ padding:"8px 10px", color:"#10b981", fontWeight:600 }}>{j.passed_checks||0}</td>
                  <td style={{ padding:"8px 10px", color:"#ef4444", fontWeight:600 }}>{j.failed_checks||0}</td>
                  <td style={{ padding:"8px 10px", color:"#6b7280" }}>{j.triggered_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div style={{ display:"flex", gap:8, justifyContent:"center", marginTop:12 }}>
              <button disabled={page<=1} onClick={() => setPage(p => p-1)}
                style={{ background:"#1f2937", color:page<=1?"#374151":"#e2e8f0",
                  border:"none", borderRadius:5, padding:"4px 14px", cursor:page>1?"pointer":"default" }}>Prev</button>
              <span style={{ color:"#6b7280", alignSelf:"center", fontSize:13 }}>Page {page}/{data.pages}</span>
              <button disabled={page>=data.pages} onClick={() => setPage(p => p+1)}
                style={{ background:"#1f2937", color:page>=data.pages?"#374151":"#e2e8f0",
                  border:"none", borderRadius:5, padding:"4px 14px", cursor:page<data.pages?"pointer":"default" }}>Next</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

//  Baselines tab 
function CISBaselines() {
  const [selOs,    setSelOs]   = useState("rhel8");
  const [data,     setData]    = useState({ rules:[], total:0, pages:1 });
  const [page,     setPage]    = useState(1);
  const [search,   setSearch]  = useState("");
  const [loading,  setLoading] = useState(false);
  const [editRow,  setEditRow] = useState(null);
  const [editVal,  setEditVal] = useState({});
  const [saving,   setSaving]  = useState(false);
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    API("/api/cis/baselines/" + selOs + "?page=" + page + "&page_size=50&search=" + encodeURIComponent(search))
      .then(d => setData(d)).catch(() => {}).finally(() => setLoading(false));
  }, [selOs, page, search]);

  useEffect(() => { load(); }, [load]);

  const saveEdit = async () => {
    if (!editRow) return;
    setSaving(true);
    try {
      await API("/api/cis/baselines/" + editRow.id, { method:"PATCH", body: JSON.stringify(editVal) });
      setEditRow(null); load();
    } catch(e) { alert("Save failed: " + e); }
    setSaving(false);
  };

  const reimport = async () => {
    setImporting(true); setImportMsg("");
    try {
      const r = await API("/api/cis/baselines/reimport", { method:"POST" });
      setImportMsg(r.success ? "Re-import complete" : "Error: " + r.stderr);
      if (r.success) load();
    } catch(e) { setImportMsg("Error: " + e); }
    setImporting(false);
  };

  return (
    <div>
      <div style={{ display:"flex", gap:8, marginBottom:14, flexWrap:"wrap", alignItems:"center" }}>
        {OS_KEYS.map(o => (
          <button key={o.key} onClick={() => { setSelOs(o.key); setPage(1); }}
            style={{ background:selOs===o.key?o.color:"#1f2937", color:"#fff",
              border:"none", borderRadius:8, padding:"7px 18px", cursor:"pointer",
              fontWeight:selOs===o.key?700:500, fontSize:13 }}>
            {o.label}
          </button>
        ))}
        <button onClick={reimport} disabled={importing}
          style={{ marginLeft:"auto", background:"#1f2937", color:"#e2e8f0",
            border:"1px solid #374151", borderRadius:8, padding:"7px 14px",
            cursor:importing?"default":"pointer", fontSize:13 }}>
          {importing ? "Importing..." : "Re-import Excel"}
        </button>
      </div>
      {importMsg && (
        <div style={{ background:"#0c4a6e", borderRadius:8, padding:"8px 14px",
          color:"#7dd3fc", fontSize:12, marginBottom:10 }}>{importMsg}</div>
      )}
      <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
        placeholder="Search CIS ID or title..."
        style={{ width:"100%", background:"#111827", border:"1px solid #374151",
          borderRadius:6, color:"#e2e8f0", padding:"7px 12px", fontSize:13,
          marginBottom:10, boxSizing:"border-box" }} />
      {loading ? <div style={{ color:"#6b7280" }}>Loading...</div> : (
        <div style={{ overflowX:"auto" }}>
          <div style={{ color:"#6b7280", fontSize:12, marginBottom:6 }}>{data.total} rules</div>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
            <thead>
              <tr style={{ background:"#111827" }}>
                {["CIS ID","Section","Title","Desired Value","Enabled","Actions"].map(h => (
                  <th key={h} style={{ padding:"7px 10px", color:"#9ca3af",
                    textAlign:"left", borderBottom:"1px solid #1f2937" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data.rules || []).map((r, i) => (
                <tr key={i} style={{ borderBottom:"1px solid #111827" }}>
                  <td style={{ padding:"7px 10px", color:"#a78bfa", fontFamily:"monospace", whiteSpace:"nowrap" }}>{r.cis_id}</td>
                  <td style={{ padding:"7px 10px", color:"#6b7280" }}>{r.section}</td>
                  <td style={{ padding:"7px 10px", color:"#e2e8f0", maxWidth:280,
                    overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{r.title}</td>
                  <td style={{ padding:"7px 10px", color:"#9ca3af" }}>{r.desired_value || "-"}</td>
                  <td style={{ padding:"7px 10px" }}>
                    <span style={{ color:r.enabled?"#10b981":"#6b7280", fontWeight:600 }}>
                      {r.enabled ? "Yes" : "No"}
                    </span>
                  </td>
                  <td style={{ padding:"7px 10px" }}>
                    <button onClick={() => { setEditRow(r); setEditVal({ title:r.title, remediation:r.remediation, desired_value:r.desired_value, enabled:r.enabled }); }}
                      style={{ background:"#374151", color:"#e2e8f0", border:"none",
                        borderRadius:5, padding:"3px 10px", fontSize:11, cursor:"pointer" }}>Edit</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.pages > 1 && (
            <div style={{ display:"flex", gap:8, justifyContent:"center", marginTop:12 }}>
              <button disabled={page<=1} onClick={() => setPage(p => p-1)}
                style={{ background:"#1f2937", color:page<=1?"#374151":"#e2e8f0",
                  border:"none", borderRadius:5, padding:"4px 14px", cursor:page>1?"pointer":"default" }}>Prev</button>
              <span style={{ color:"#6b7280", fontSize:12 }}>Page {page}/{data.pages}</span>
              <button disabled={page>=data.pages} onClick={() => setPage(p => p+1)}
                style={{ background:"#1f2937", color:page>=data.pages?"#374151":"#e2e8f0",
                  border:"none", borderRadius:5, padding:"4px 14px", cursor:page<data.pages?"pointer":"default" }}>Next</button>
            </div>
          )}
        </div>
      )}
      {editRow && (
        <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.75)",
          display:"flex", alignItems:"center", justifyContent:"center", zIndex:9999 }}>
          <div style={{ background:"#111827", border:"1px solid #374151",
            borderRadius:12, padding:24, width:520, maxHeight:"80vh", overflowY:"auto" }}>
            <h3 style={{ color:"#f9fafb", margin:"0 0 14px" }}>Edit Rule - {editRow.cis_id}</h3>
            {[["title","Title"],["remediation","Remediation Command"],["desired_value","Desired Value"]].map(([fld,lbl]) => (
              <div key={fld} style={{ marginBottom:12 }}>
                <label style={{ color:"#9ca3af", fontSize:12, display:"block", marginBottom:4 }}>{lbl}</label>
                <textarea value={editVal[fld] || ""} onChange={e => setEditVal(v => ({ ...v, [fld]:e.target.value }))}
                  style={{ width:"100%", background:"#0d1117", border:"1px solid #374151",
                    borderRadius:6, color:"#e2e8f0", padding:"7px 10px", fontSize:12,
                    minHeight:60, resize:"vertical", boxSizing:"border-box" }} />
              </div>
            ))}
            <label style={{ color:"#9ca3af", fontSize:12, display:"flex", alignItems:"center", gap:8, marginBottom:14 }}>
              <input type="checkbox" checked={!!editVal.enabled}
                onChange={e => setEditVal(v => ({ ...v, enabled:e.target.checked }))} />
              Enabled
            </label>
            <div style={{ display:"flex", gap:8 }}>
              <button onClick={saveEdit} disabled={saving}
                style={{ background:"#7c3aed", color:"#fff", border:"none",
                  borderRadius:7, padding:"8px 20px", cursor:"pointer", fontWeight:700 }}>
                {saving ? "Saving..." : "Save"}
              </button>
              <button onClick={() => setEditRow(null)}
                style={{ background:"#374151", color:"#e2e8f0", border:"none",
                  borderRadius:7, padding:"8px 20px", cursor:"pointer" }}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


//  Power Badge helper 
const CIS_TABS = [
  { id: "dashboard",   label: "📊 Dashboard" },
  { id: "osgroups",    label: "🖥️ OS Groups" },
  { id: "vmlist",      label: "📝 VM List" },
  { id: "scanhistory", label: "🗂️ Scan History" },
  { id: "baselines",   label: "📚 Baselines" },
  { id: "exclusions",  label: "⊚ Exclusions" },
  { id: "remlog",      label: "📋 Remediation Log" },
  { id: "reports",     label: "📄 Reports" },
];

export default function CISHardening({ currentUser }) {
  const [tab, setTab]       = useState("dashboard");
  const [selVM, setSelVM]   = useState(null);

  const tabStyle = (id) => ({
    background: tab === id ? "linear-gradient(135deg,#6366f1,#8b5cf6)" : "#111827",
    color: tab === id ? "#fff" : "#9ca3af",
    border: tab === id ? "none" : "1px solid #1f2937",
    borderRadius: 8,
    padding: "8px 18px",
    cursor: "pointer",
    fontWeight: tab === id ? 700 : 500,
    fontSize: 13,
    transition: "all 0.2s",
  });

  const handleViewVM = (vm) => {
    setSelVM(vm);
    setTab("vmdetail");
  };

  const handleBack = () => {
    setSelVM(null);
    setTab("vmlist");
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:20, minHeight:"calc(100vh - 200px)" }}>
      {/* Header */}
      <div style={{ display:"flex", alignItems:"center", gap:14, flexWrap:"wrap" }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <div style={{ width:40, height:40, borderRadius:10,
            background:"linear-gradient(135deg,#6366f1,#8b5cf6)",
            display:"flex", alignItems:"center", justifyContent:"center", fontSize:20 }}>
            🔒
          </div>
          <div>
            <h1 style={{ color:"#f9fafb", fontSize:22, fontWeight:800, margin:0 }}>
              CIS Hardening
            </h1>
            <p style={{ color:"#6b7280", fontSize:13, margin:0 }}>
              CIS Benchmark compliance scanning &amp; auto-remediation
            </p>
          </div>
        </div>

        {/* Tab bar */}
        <div style={{ display:"flex", gap:8, marginLeft:"auto", flexWrap:"wrap" }}>
          {CIS_TABS.map((t) => (
            <button key={t.id} style={tabStyle(t.id)}
              onClick={() => { setTab(t.id); if (t.id !== "vmdetail") setSelVM(null); }}>
              {t.label}
            </button>
          ))}
          {selVM && (
            <button style={tabStyle("vmdetail")}
              onClick={() => setTab("vmdetail")}>
              🔍 {selVM.vm_name}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div>
        {tab === "dashboard"   && <CISDashboard onViewVM={handleViewVM} />}
        {tab === "osgroups"    && <CISOsGroups onViewVM={handleViewVM} />}
        {tab === "vmlist"      && <CISVMList onSelectVM={handleViewVM} />}
        {tab === "scanhistory" && <CISScanHistory />}
        {tab === "baselines"   && <CISBaselines />}
        {tab === "vmdetail"   && selVM && <CISVMDetail vm={selVM} onBack={handleBack} />}
        {tab === "exclusions" && <CISExclusions />}
        {tab === "remlog"     && <CISRemLog />}
        {tab === "reports"    && <CISReports />}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
