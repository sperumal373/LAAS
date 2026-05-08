"""
cis_reports.py  --  CIS Hardening Report Generator
====================================================
Generates per-VM and fleet-wide CIS compliance reports in:
  - CSV   : Raw check data, Excel-compatible
  - HTML  : Styled, printable, browser-renderable
  - PDF   : Native PDF via fpdf2 (pure Python, no system deps)
"""

import csv, io, json
from datetime import datetime, timezone
import psycopg2, psycopg2.extras

PG_CONFIG = dict(
    host="127.0.0.1", port=5433, dbname="caas_dashboard",
    user="caas_app", password="CaaS@App2024#", connect_timeout=10,
)

def _db():
    return psycopg2.connect(**PG_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


# ── Data Helpers ──────────────────────────────────────────────────────────────

def _get_vm_scan(vm_scan_id: int) -> tuple:
    """Return (vm_row, [check_rows])"""
    conn = _db()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM cis_vm_scans WHERE id=%s", (vm_scan_id,))
        vm = dict(cur.fetchone() or {})
        cur.execute("""
            SELECT * FROM cis_check_results WHERE vm_scan_id=%s
            ORDER BY section, cis_id
        """, (vm_scan_id,))
        checks = [dict(r) for r in cur.fetchall()]
    conn.close()
    return vm, checks


def _get_fleet_scans(benchmark: str = "", os_family: str = "") -> list:
    """Return list of (vm_row, [check_rows]) for latest scan per VM."""
    conn = _db()
    conds = ["1=1"]
    params: list = []
    if benchmark:
        conds.append("vs.benchmark ILIKE %s"); params.append(f"%{benchmark}%")
    if os_family:
        conds.append("vs.os_family = %s"); params.append(os_family)
    where = "WHERE " + " AND ".join(conds)

    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT DISTINCT ON (vs.vm_name) vs.*
            FROM cis_vm_scans vs
            {where}
            ORDER BY vs.vm_name, vs.scanned_at DESC
        """, params)
        vms = [dict(r) for r in cur.fetchall()]

        results = []
        for vm in vms:
            cur.execute("""
                SELECT * FROM cis_check_results WHERE vm_scan_id=%s
                ORDER BY section, cis_id
            """, (vm["id"],))
            checks = [dict(r) for r in cur.fetchall()]
            results.append((vm, checks))
    conn.close()
    return results


def _score_color_hex(score) -> str:
    s = float(score or 0)
    if s >= 80: return "#10b981"
    if s >= 60: return "#f59e0b"
    if s >= 40: return "#f97316"
    return "#ef4444"

def _status_color(st: str) -> str:
    return {"pass":"#10b981","fail":"#ef4444","skip":"#6b7280","excluded":"#8b5cf6"}.get(st,"#6b7280")

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────────────────────────────────────
#  CSV
# ─────────────────────────────────────────────────────────────────────────────

def generate_csv_vm(vm_scan_id: int) -> tuple:
    """Returns (bytes, filename)"""
    vm, checks = _get_vm_scan(vm_scan_id)
    out = io.StringIO()
    w = csv.writer(out)

    w.writerow(["CIS Compliance Report"])
    w.writerow(["VM Name", vm.get("vm_name",""),"IP", vm.get("ip_address",""),
                "OS", vm.get("os_name",""),"Benchmark", vm.get("benchmark",""),
                "Score", vm.get("score",""),"Scanned", str(vm.get("scanned_at",""))])
    w.writerow(["Pass", vm.get("passed",""),"Fail", vm.get("failed",""),
                "Skip", vm.get("skipped",""),"Excluded", vm.get("excluded","")])
    w.writerow([])
    w.writerow(["CIS ID","Section","Category","Title","Status",
                "Found Value","Expected Value","IG1","IG2","IG3","Remediation"])

    for c in checks:
        w.writerow([c.get("cis_id",""),c.get("section",""),c.get("category",""),
                    c.get("title",""),c.get("status","").upper(),
                    c.get("found_value",""),c.get("expected_value",""),
                    "Yes" if c.get("is_ig1") else "No",
                    "Yes" if c.get("is_ig2") else "No",
                    "Yes" if c.get("is_ig3") else "No",
                    c.get("remediation_cmd","")[:120]])

    name = f"cis_report_{vm.get('vm_name','vm')}_{datetime.now().strftime('%Y%m%d')}.csv"
    return out.getvalue().encode("utf-8-sig"), name


def generate_csv_fleet(benchmark: str = "", os_family: str = "") -> tuple:
    """Fleet CSV — one row per (VM, check)."""
    fleet = _get_fleet_scans(benchmark, os_family)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["CIS Fleet Report", f"Generated: {_now()}"])
    w.writerow([])
    w.writerow(["VM Name","IP","OS","Benchmark","Score",
                "CIS ID","Section","Category","Title","Status",
                "Found Value","Expected Value","IG1","IG2","IG3"])

    for vm, checks in fleet:
        for c in checks:
            w.writerow([vm.get("vm_name",""),vm.get("ip_address",""),
                        vm.get("os_name",""),vm.get("benchmark",""),
                        vm.get("score",""),
                        c.get("cis_id",""),c.get("section",""),c.get("category",""),
                        c.get("title",""),c.get("status","").upper(),
                        c.get("found_value",""),c.get("expected_value",""),
                        "Yes" if c.get("is_ig1") else "No",
                        "Yes" if c.get("is_ig2") else "No",
                        "Yes" if c.get("is_ig3") else "No"])

    name = f"cis_fleet_report_{datetime.now().strftime('%Y%m%d')}.csv"
    return out.getvalue().encode("utf-8-sig"), name


# ─────────────────────────────────────────────────────────────────────────────
#  HTML
# ─────────────────────────────────────────────────────────────────────────────

_HTML_CSS = """
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #e2e8f0;
  padding: 0; margin: 0; }
@media print {
  body { background: #fff; color: #111; }
  .no-print { display: none !important; }
  .card { break-inside: avoid; }
  table { font-size: 10px; }
}
.page { max-width: 1200px; margin: 0 auto; padding: 24px; }
h1 { font-size: 28px; font-weight: 800; }
h2 { font-size: 20px; font-weight: 700; margin: 24px 0 12px; }
h3 { font-size: 16px; font-weight: 700; margin: 0 0 10px; }
.header { background: linear-gradient(135deg,#1e1b4b,#312e81);
  border-radius: 16px; padding: 28px 32px; margin-bottom: 24px;
  display: flex; align-items: center; gap: 20px; border: 1px solid #3730a3; }
.header-icon { font-size: 48px; }
.header-info { flex: 1; }
.header-score { text-align: right; }
.score-val { font-size: 48px; font-weight: 900; }
.score-lbl { font-size: 13px; color: #94a3b8; margin-top: 2px; }
.kpi-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 24px; }
.kpi { background: #1e293b; border: 1px solid #334155; border-radius: 12px;
  padding: 16px; text-align: center; }
.kpi-val { font-size: 26px; font-weight: 800; }
.kpi-lbl { font-size: 12px; color: #64748b; margin-top: 4px; }
.section-header { display: flex; align-items: center; gap: 12px; padding: 14px 16px;
  background: #1e293b; border-radius: 10px 10px 0 0; border-bottom: 1px solid #334155; }
.section-badge { width: 30px; height: 30px; border-radius: 6px; display: flex;
  align-items: center; justify-content: center; font-weight: 700; font-size: 13px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; background: #1e293b;
  border-radius: 0 0 10px 10px; overflow: hidden; }
th { padding: 10px 12px; background: #0f172a; color: #64748b; text-align: left;
  font-weight: 600; font-size: 12px; border-bottom: 1px solid #334155; }
td { padding: 9px 12px; border-bottom: 1px solid #1e293b; vertical-align: top;
  color: #cbd5e1; }
tr:hover td { background: #263349; }
.pill { display: inline-block; padding: 2px 10px; border-radius: 4px;
  font-size: 11px; font-weight: 700; letter-spacing: .5px; }
.pill-pass { background: #064e3b; color: #10b981; }
.pill-fail { background: #450a0a; color: #ef4444; }
.pill-skip { background: #1e293b; color: #64748b; }
.pill-excluded { background: #2e1065; color: #a78bfa; }
.ig-tag { display: inline-block; background: #1e3a5f; color: #60a5fa;
  border-radius: 4px; padding: 1px 5px; font-size: 10px; margin-right: 2px; }
.found-fail { color: #f87171; }
.exp { color: #34d399; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 12px;
  padding: 20px; margin-bottom: 16px; }
.score-bar-wrap { background: #0f172a; border-radius: 6px; height: 12px;
  overflow: hidden; margin-top: 6px; }
.score-bar { height: 100%; border-radius: 6px; transition: width .6s; }
.meta-table td { border: none; padding: 4px 8px; font-size: 13px; }
.meta-table td:first-child { color: #64748b; width: 160px; }
.fleet-vm-header { background: #0f172a; padding: 12px 16px; border-radius: 8px;
  margin: 20px 0 8px; display: flex; align-items: center; gap: 12px; }
.logo { font-size: 32px; font-weight: 900; color: #6366f1; }
.tagline { font-size: 12px; color: #64748b; }
.print-btn { position: fixed; top: 16px; right: 16px; background: #6366f1;
  color: #fff; border: none; border-radius: 8px; padding: 10px 20px;
  font-weight: 700; font-size: 14px; cursor: pointer; z-index: 999; }
@media (prefers-color-scheme: light) {
  body { background: #f8fafc; color: #0f172a; }
  .card, .kpi, table { background: #fff; border-color: #e2e8f0; }
  th { background: #f1f5f9; color: #475569; }
  .header { background: linear-gradient(135deg,#4338ca,#6366f1); }
  td { color: #334155; }
}
</style>
"""

def _score_label(s) -> str:
    s = float(s or 0)
    if s >= 80: return "✅ Compliant"
    if s >= 60: return "⚠️ Warning"
    if s >= 40: return "🔶 At Risk"
    return "🔴 Critical"

def _pill(status: str) -> str:
    cls = {"pass":"pass","fail":"fail","skip":"skip","excluded":"excluded"}.get(status,"skip")
    txt = {"pass":"PASS","fail":"FAIL","skip":"SKIP","excluded":"EXCL"}.get(status,"?")
    return f'<span class="pill pill-{cls}">{txt}</span>'

def _ig_tags(c: dict) -> str:
    t = ""
    if c.get("is_ig1"): t += '<span class="ig-tag">IG1</span>'
    if c.get("is_ig2"): t += '<span class="ig-tag">IG2</span>'
    if c.get("is_ig3"): t += '<span class="ig-tag">IG3</span>'
    return t

_SEC_NAMES = {
    "1":"Initial Setup","2":"Services","3":"Network Configuration",
    "4":"Logging & Auditing","5":"Access Control","6":"System Maintenance",
    "9":"Audit Policy","18":"Advanced Security"
}
_SEC_COLORS = ["#6366f1","#f59e0b","#10b981","#3b82f6","#ef4444","#8b5cf6","#06b6d4","#ec4899"]

def _section_color(sec: str) -> str:
    return _SEC_COLORS[int(sec or 0) % len(_SEC_COLORS)]


def generate_html_vm(vm_scan_id: int) -> tuple:
    """Returns (html_string, filename)"""
    vm, checks = _get_vm_scan(vm_scan_id)
    score = float(vm.get("score") or 0)
    sc = _score_color_hex(score)
    scanned = str(vm.get("scanned_at",""))[:16]

    # Group by section
    by_sec: dict = {}
    for c in checks:
        by_sec.setdefault(c.get("section","?"), []).append(c)

    sec_rows = ""
    for sec in sorted(by_sec.keys(), key=lambda x: (int(x) if x.isdigit() else 99)):
        cs = by_sec[sec]
        fail_c = sum(1 for c in cs if c["status"]=="fail")
        pass_c = sum(1 for c in cs if c["status"]=="pass")
        sec_color = _section_color(sec)
        sec_name  = _SEC_NAMES.get(sec, f"Section {sec}")
        rows_html = ""
        for c in cs:
            fail_detail = ""
            if c["status"] == "fail":
                fail_detail = (f'<br><span class="found-fail">Found:</span> '
                               f'{c.get("found_value","") or "(empty)"} &nbsp;'
                               f'<span class="exp">Expected:</span> {c.get("expected_value","")}')
            rows_html += f"""
            <tr>
              <td style="font-family:monospace;color:#a78bfa;font-weight:700;white-space:nowrap">
                {c.get("cis_id","")}
              </td>
              <td>{_pill(c.get("status","skip"))}</td>
              <td style="max-width:420px">
                {c.get("title","")} {_ig_tags(c)}{fail_detail}
              </td>
              <td style="font-size:11px;color:#94a3b8;max-width:200px">
                {c.get("remediation_cmd","")[:80] if c.get("status")=="fail" else "—"}
              </td>
            </tr>"""

        sec_rows += f"""
        <div class="card" style="padding:0;margin-bottom:20px">
          <div class="section-header">
            <div class="section-badge" style="background:{sec_color}22;color:{sec_color}">§{sec}</div>
            <span style="font-weight:700;font-size:15px;color:#f1f5f9">{sec_name}</span>
            <span style="color:#64748b;font-size:12px">({len(cs)} checks)</span>
            {'<span style="background:#450a0a;color:#ef4444;border-radius:12px;padding:1px 10px;font-size:11px;font-weight:700">'+str(fail_c)+' FAIL</span>' if fail_c else ""}
            {'<span style="background:#064e3b;color:#10b981;border-radius:12px;padding:1px 10px;font-size:11px;font-weight:700">'+str(pass_c)+' PASS</span>' if pass_c else ""}
          </div>
          <table>
            <thead><tr>
              <th style="width:80px">CIS ID</th><th style="width:70px">Status</th>
              <th>Control Title</th><th>Remediation hint</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>"""

    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CIS Report — {vm.get('vm_name','')} — {scanned}</title>
{_HTML_CSS}
</head><body>
<button class="print-btn no-print" onclick="window.print()">🖨 Print / Save PDF</button>
<div class="page">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:20px">
    <span class="logo">🔒</span>
    <div>
      <div style="font-size:12px;color:#64748b">CompliSphere CIS Hardening</div>
      <div class="tagline">Generated {_now()} &nbsp;|&nbsp; {vm.get("benchmark","").replace("_"," ")}</div>
    </div>
  </div>

  <div class="header">
    <div class="header-icon">{'🪟' if vm.get('os_family')=='windows' else '🐧'}</div>
    <div class="header-info">
      <h1>{vm.get("vm_name","")}</h1>
      <div style="color:#94a3b8;font-size:14px;margin-top:6px">
        {vm.get("ip_address","—")} &nbsp;·&nbsp; {vm.get("os_name","—")} &nbsp;·&nbsp; {scanned}
      </div>
      <div style="color:#94a3b8;font-size:13px;margin-top:4px">
        Benchmark: <strong style="color:#c7d2fe">{vm.get("benchmark","—").replace("_"," ")}</strong>
      </div>
    </div>
    <div class="header-score">
      <div class="score-val" style="color:{sc}">{round(score,1)}%</div>
      <div class="score-lbl">{_score_label(score)}</div>
      <div class="score-bar-wrap" style="width:120px;margin-top:8px">
        <div class="score-bar" style="width:{round(score,0)}%;background:{sc}"></div>
      </div>
    </div>
  </div>

  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-val" style="color:#6366f1">{vm.get("total_checks",0)}</div><div class="kpi-lbl">Total Checks</div></div>
    <div class="kpi"><div class="kpi-val" style="color:#10b981">{vm.get("passed",0)}</div><div class="kpi-lbl">Passed</div></div>
    <div class="kpi"><div class="kpi-val" style="color:#ef4444">{vm.get("failed",0)}</div><div class="kpi-lbl">Failed</div></div>
    <div class="kpi"><div class="kpi-val" style="color:#8b5cf6">{vm.get("excluded",0)}</div><div class="kpi-lbl">Excluded</div></div>
  </div>

  <h2>📋 CIS Control Results by Section</h2>
  {sec_rows}

  <div style="text-align:center;color:#334155;font-size:12px;margin-top:32px;padding-top:16px;border-top:1px solid #1e293b">
    CompliSphere CIS Hardening Report &nbsp;·&nbsp; Generated {_now()} &nbsp;·&nbsp; CONFIDENTIAL
  </div>
</div>
</body></html>"""

    name = f"cis_report_{vm.get('vm_name','vm')}_{datetime.now().strftime('%Y%m%d')}.html"
    return html, name


def generate_html_fleet(benchmark: str = "", os_family: str = "") -> tuple:
    """Fleet-wide HTML report."""
    fleet = _get_fleet_scans(benchmark, os_family)

    # Summary stats
    total_vms  = len(fleet)
    compliant  = sum(1 for vm,_ in fleet if float(vm.get("score") or 0) >= 80)
    warning    = sum(1 for vm,_ in fleet if 50 <= float(vm.get("score") or 0) < 80)
    critical   = sum(1 for vm,_ in fleet if float(vm.get("score") or 0) < 50)
    avg_score  = (sum(float(vm.get("score") or 0) for vm,_ in fleet) / total_vms) if total_vms else 0

    vm_rows = ""
    for vm, checks in sorted(fleet, key=lambda x: float(x[0].get("score") or 0)):
        sc = _score_color_hex(vm.get("score"))
        score = float(vm.get("score") or 0)
        vm_rows += f"""
        <tr>
          <td style="font-weight:700;color:#f1f5f9">
            {'🪟' if vm.get('os_family')=='windows' else '🐧'} {vm.get("vm_name","")}
          </td>
          <td style="font-family:monospace;font-size:12px;color:#94a3b8">{vm.get("ip_address","—")}</td>
          <td style="color:#94a3b8;font-size:12px">{vm.get("os_name","—")}</td>
          <td style="color:#a78bfa;font-size:12px">{vm.get("benchmark","—").replace("_"," ")}</td>
          <td>
            <span style="font-weight:800;color:{sc}">{round(score,1)}%</span>
            <div style="background:#0f172a;border-radius:4px;height:6px;width:80px;margin-top:3px;overflow:hidden">
              <div style="width:{round(score,0)}%;height:100%;background:{sc}"></div>
            </div>
          </td>
          <td style="color:#10b981;font-weight:600">{vm.get("passed",0)}</td>
          <td style="color:#ef4444;font-weight:600">{vm.get("failed",0)}</td>
          <td style="color:#6b7280">{vm.get("skipped",0)}</td>
          <td style="color:#8b5cf6">{vm.get("excluded",0)}</td>
          <td style="font-size:12px;color:#64748b">{str(vm.get("scanned_at",""))[:16]}</td>
        </tr>"""

    # Top failing controls across fleet
    fail_counts: dict = {}
    for _, checks in fleet:
        for c in checks:
            if c["status"] == "fail":
                k = c["cis_id"]
                if k not in fail_counts:
                    fail_counts[k] = {"title": c.get("title",""), "count": 0}
                fail_counts[k]["count"] += 1
    top_fails = sorted(fail_counts.items(), key=lambda x: -x[1]["count"])[:15]
    top_rows = "".join(f"""
        <tr>
          <td style="font-family:monospace;color:#ef4444;font-weight:700">{cid}</td>
          <td>{info['title'][:80]}</td>
          <td style="color:#f87171;font-weight:600;text-align:center">{info['count']}</td>
        </tr>""" for cid, info in top_fails)

    html = f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CIS Fleet Report — {_now()[:10]}</title>
{_HTML_CSS}
</head><body>
<button class="print-btn no-print" onclick="window.print()">🖨 Print / Save PDF</button>
<div class="page">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:20px">
    <span class="logo">🔒</span>
    <div>
      <div style="font-size:12px;color:#64748b">CompliSphere CIS Hardening — Fleet Report</div>
      <div class="tagline">Generated {_now()} &nbsp;{("| Benchmark: "+benchmark) if benchmark else ""} {("| OS: "+os_family) if os_family else ""}</div>
    </div>
  </div>

  <h1 style="margin-bottom:20px">CIS Compliance Fleet Report</h1>

  <div class="kpi-grid" style="grid-template-columns:repeat(5,1fr)">
    <div class="kpi"><div class="kpi-val" style="color:#6366f1">{total_vms}</div><div class="kpi-lbl">Total VMs</div></div>
    <div class="kpi"><div class="kpi-val" style="color:{'#10b981' if avg_score>=80 else '#f59e0b'}">{round(avg_score,1)}%</div><div class="kpi-lbl">Avg Score</div></div>
    <div class="kpi"><div class="kpi-val" style="color:#10b981">{compliant}</div><div class="kpi-lbl">✅ Compliant ≥80%</div></div>
    <div class="kpi"><div class="kpi-val" style="color:#f59e0b">{warning}</div><div class="kpi-lbl">⚠️ Warning 50-79%</div></div>
    <div class="kpi"><div class="kpi-val" style="color:#ef4444">{critical}</div><div class="kpi-lbl">🔴 Critical &lt;50%</div></div>
  </div>

  <h2>🖥️ VM Compliance Summary</h2>
  <div class="card" style="padding:0">
    <table>
      <thead><tr>
        <th>VM Name</th><th>IP</th><th>OS</th><th>Benchmark</th>
        <th>Score</th><th>Pass</th><th>Fail</th><th>Skip</th><th>Excl</th><th>Scanned</th>
      </tr></thead>
      <tbody>{vm_rows}</tbody>
    </table>
  </div>

  <h2>🚨 Top Failing CIS Controls (Fleet-wide)</h2>
  <div class="card" style="padding:0">
    <table>
      <thead><tr><th style="width:80px">CIS ID</th><th>Control Title</th><th style="width:80px;text-align:center">Affected VMs</th></tr></thead>
      <tbody>{top_rows}</tbody>
    </table>
  </div>

  <div style="text-align:center;color:#334155;font-size:12px;margin-top:32px;padding-top:16px;border-top:1px solid #1e293b">
    CompliSphere CIS Fleet Report &nbsp;·&nbsp; Generated {_now()} &nbsp;·&nbsp; CONFIDENTIAL — DO NOT DISTRIBUTE
  </div>
</div>
</body></html>"""

    name = f"cis_fleet_report_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    return html, name


# ─────────────────────────────────────────────────────────────────────────────
#  PDF  (via fpdf2 — pure Python)
# ─────────────────────────────────────────────────────────────────────────────

def _try_fpdf():
    try:
        from fpdf import FPDF
        return FPDF
    except ImportError:
        return None


def generate_pdf_vm(vm_scan_id: int) -> tuple:
    """Returns (pdf_bytes, filename). Falls back to HTML bytes if fpdf2 missing."""
    FPDF = _try_fpdf()
    vm, checks = _get_vm_scan(vm_scan_id)
    score = float(vm.get("score") or 0)
    name  = f"cis_report_{vm.get('vm_name','vm')}_{datetime.now().strftime('%Y%m%d')}.pdf"

    if not FPDF:
        # Fallback: return HTML with .pdf extension hint
        html, _ = generate_html_vm(vm_scan_id)
        return html.encode(), name.replace(".pdf",".html")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Cover / Header ─────────────────────────────────────────────────────
    pdf.set_fill_color(30, 27, 75)
    pdf.rect(0, 0, 210, 50, "F")

    pdf.set_xy(10, 8)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(99, 102, 241)
    pdf.cell(0, 10, "CIS Hardening Report", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(148, 163, 184)
    pdf.set_x(10)
    pdf.cell(0, 7, f"Generated: {_now()}    Benchmark: {vm.get('benchmark','').replace('_',' ')}", ln=True)

    pdf.set_xy(10, 28)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(241, 245, 249)
    pdf.cell(0, 8, vm.get("vm_name",""), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(148, 163, 184)
    pdf.set_x(10)
    pdf.cell(0, 6, f"IP: {vm.get('ip_address','—')}    OS: {vm.get('os_name','—')}    Scanned: {str(vm.get('scanned_at',''))[:16]}", ln=True)

    # Score box
    sc_r, sc_g, sc_b = (16,185,129) if score>=80 else (245,158,11) if score>=60 else (239,68,68)
    pdf.set_fill_color(sc_r, sc_g, sc_b)
    pdf.rect(160, 8, 40, 38, "F")
    pdf.set_xy(160, 14)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(40, 14, f"{round(score,1)}%", align="C", ln=True)
    pdf.set_xy(160, 28)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(40, 6, _score_label(score).split(" ",1)[-1], align="C", ln=True)

    pdf.ln(10)

    # ── KPI row ────────────────────────────────────────────────────────────
    pdf.set_text_color(30, 41, 59)
    for label, val, color in [
        ("Total",    vm.get("total_checks",0), (99,102,241)),
        ("Passed",   vm.get("passed",0),       (16,185,129)),
        ("Failed",   vm.get("failed",0),       (239,68,68)),
        ("Excluded", vm.get("excluded",0),     (139,92,246)),
    ]:
        r, g, b = color
        pdf.set_fill_color(r, g, b)
        x = pdf.get_x(); y = pdf.get_y()
        pdf.rect(x, y, 44, 20, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x, y+2)
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(44, 8, str(val), align="C", ln=False)
        pdf.set_xy(x, y+11)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(44, 6, label, align="C", ln=False)
        pdf.set_xy(x+46, y)

    pdf.ln(28)

    # ── Checks table ───────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(99, 102, 241)
    pdf.cell(0, 8, "CIS Control Results", ln=True)
    pdf.ln(2)

    # Table header
    col_w = [22, 16, 120, 30]
    headers = ["CIS ID", "Status", "Control Title", "IG Levels"]
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(100, 116, 139)
    pdf.set_font("Helvetica", "B", 8)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=0, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    fill = False
    for c in checks:
        st = c.get("status","skip")
        if st == "pass":
            r, g, b = 6, 78, 59
        elif st == "fail":
            r, g, b = 69, 10, 10
        else:
            r, g, b = 30, 41, 59

        pdf.set_fill_color(r, g, b)

        status_color = {"pass":(16,185,129),"fail":(239,68,68),"skip":(100,116,139),"excluded":(139,92,246)}.get(st,(100,116,139))
        title = (c.get("title","") or "")[:65]

        ig = " ".join(["IG1" if c.get("is_ig1") else "",
                       "IG2" if c.get("is_ig2") else "",
                       "IG3" if c.get("is_ig3") else ""]).strip()

        pdf.set_text_color(167, 139, 250)
        pdf.cell(col_w[0], 6, c.get("cis_id",""), fill=True, border=0)
        pdf.set_text_color(*status_color)
        pdf.cell(col_w[1], 6, st.upper(), fill=True, border=0)
        pdf.set_text_color(203, 213, 225)
        pdf.cell(col_w[2], 6, title, fill=True, border=0)
        pdf.set_text_color(96, 165, 250)
        pdf.cell(col_w[3], 6, ig, fill=True, border=0)
        pdf.ln()

        # Show found/expected for failures
        if st == "fail" and (c.get("found_value") or c.get("expected_value")):
            pdf.set_fill_color(r, g, b)
            pdf.set_text_color(248, 113, 113)
            pdf.cell(22, 5, "", fill=True, border=0)
            pdf.cell(col_w[1]+col_w[2]+col_w[3], 5,
                     f"  Found: {str(c.get('found_value',''))[:60]}  Expected: {str(c.get('expected_value',''))[:40]}",
                     fill=True, border=0)
            pdf.ln()

    # Footer
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, f"CompliSphere CIS Hardening Report  |  {_now()}  |  CONFIDENTIAL", align="C")

    return pdf.output(), name


def generate_pdf_fleet(benchmark: str = "", os_family: str = "") -> tuple:
    """Fleet PDF summary."""
    FPDF = _try_fpdf()
    fleet = _get_fleet_scans(benchmark, os_family)
    name  = f"cis_fleet_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    if not FPDF:
        html, _ = generate_html_fleet(benchmark, os_family)
        return html.encode(), name.replace(".pdf",".html")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_fill_color(30, 27, 75)
    pdf.rect(0, 0, 210, 40, "F")
    pdf.set_xy(10, 8)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(99, 102, 241)
    pdf.cell(0, 10, "CIS Fleet Compliance Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(148, 163, 184)
    pdf.set_x(10)
    bm_lbl = f"  |  Benchmark: {benchmark}" if benchmark else ""
    os_lbl = f"  |  OS: {os_family}" if os_family else ""
    pdf.cell(0, 6, f"Generated: {_now()}{bm_lbl}{os_lbl}", ln=True)
    pdf.ln(10)

    # Fleet KPIs
    total  = len(fleet)
    comp   = sum(1 for vm,_ in fleet if float(vm.get("score") or 0) >= 80)
    warn   = sum(1 for vm,_ in fleet if 50 <= float(vm.get("score") or 0) < 80)
    crit   = sum(1 for vm,_ in fleet if float(vm.get("score") or 0) < 50)
    avg    = (sum(float(vm.get("score") or 0) for vm,_ in fleet) / total) if total else 0

    for label, val, color in [
        ("Total VMs",   total, (99,102,241)),
        ("Avg Score",   f"{round(avg,1)}%", (16,185,129) if avg>=80 else (245,158,11)),
        ("Compliant",   comp,  (16,185,129)),
        ("Warning",     warn,  (245,158,11)),
        ("Critical",    crit,  (239,68,68)),
    ]:
        r, g, b = color
        pdf.set_fill_color(r, g, b)
        x = pdf.get_x(); y = pdf.get_y()
        pdf.rect(x, y, 36, 18, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(x, y+1)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(36, 8, str(val), align="C", ln=False)
        pdf.set_xy(x, y+10)
        pdf.set_font("Helvetica", "", 7)
        pdf.cell(36, 5, label, align="C", ln=False)
        pdf.set_xy(x+38, y)
    pdf.ln(25)

    # VM Table
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(99, 102, 241)
    pdf.cell(0, 8, "VM Compliance Summary", ln=True)
    pdf.ln(2)

    col_w = [50, 30, 35, 30, 18, 15, 15]
    hdrs  = ["VM Name","IP","OS / Benchmark","Score","Pass","Fail","Excl"]
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(100, 116, 139)
    pdf.set_font("Helvetica", "B", 8)
    for i, h in enumerate(hdrs):
        pdf.cell(col_w[i], 7, h, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for vm, _ in sorted(fleet, key=lambda x: float(x[0].get("score") or 0)):
        score = float(vm.get("score") or 0)
        sc_r, sc_g, sc_b = (16,185,129) if score>=80 else (245,158,11) if score>=50 else (239,68,68)
        pdf.set_fill_color(22, 33, 62)
        pdf.set_text_color(241, 245, 249)
        pdf.cell(col_w[0], 6, (vm.get("vm_name","") or "")[:24], fill=True)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(col_w[1], 6, (vm.get("ip_address","") or "")[:16], fill=True)
        pdf.cell(col_w[2], 6, (vm.get("os_name","") or "")[:18], fill=True)
        pdf.set_text_color(sc_r, sc_g, sc_b)
        pdf.cell(col_w[3], 6, f"{round(score,1)}%", fill=True)
        pdf.set_text_color(16, 185, 129)
        pdf.cell(col_w[4], 6, str(vm.get("passed","")), fill=True)
        pdf.set_text_color(239, 68, 68)
        pdf.cell(col_w[5], 6, str(vm.get("failed","")), fill=True)
        pdf.set_text_color(139, 92, 246)
        pdf.cell(col_w[6], 6, str(vm.get("excluded","")), fill=True)
        pdf.ln()

    # Top failures
    pdf.ln(8)
    pdf.set_font("Helvetica","B",11)
    pdf.set_text_color(239, 68, 68)
    pdf.cell(0, 8, "Top Failing CIS Controls", ln=True)
    pdf.ln(2)

    fail_counts: dict = {}
    for _, checks in fleet:
        for c in checks:
            if c["status"] == "fail":
                k = c["cis_id"]
                if k not in fail_counts:
                    fail_counts[k] = {"title": c.get("title",""), "count": 0}
                fail_counts[k]["count"] += 1
    top = sorted(fail_counts.items(), key=lambda x: -x[1]["count"])[:15]

    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(100, 116, 139)
    pdf.set_font("Helvetica","B",8)
    pdf.cell(25, 7, "CIS ID", fill=True)
    pdf.cell(140, 7, "Control Title", fill=True)
    pdf.cell(25, 7, "Affected VMs", fill=True)
    pdf.ln()
    pdf.set_font("Helvetica","",8)
    for cid, info in top:
        pdf.set_fill_color(22, 33, 62)
        pdf.set_text_color(239, 68, 68)
        pdf.cell(25, 6, cid, fill=True)
        pdf.set_text_color(203, 213, 225)
        pdf.cell(140, 6, (info["title"] or "")[:70], fill=True)
        pdf.set_text_color(248, 113, 113)
        pdf.cell(25, 6, str(info["count"]), align="C", fill=True)
        pdf.ln()

    pdf.set_y(-20)
    pdf.set_font("Helvetica","",8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 5, f"CompliSphere CIS Fleet Report  |  {_now()}  |  CONFIDENTIAL", align="C")

    return pdf.output(), name
