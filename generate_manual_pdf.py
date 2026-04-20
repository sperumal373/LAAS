"""
LaaS Portal — End User Manual PDF Generator
Generates: USER_MANUAL.pdf
Run: python generate_manual_pdf.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics import renderPDF
import os

OUT = r"c:\caas-dashboard\USER_MANUAL.pdf"

# ── Colour palette ─────────────────────────────────────────────────────────
C_BG        = colors.HexColor("#060d18")
C_NAVY      = colors.HexColor("#0d1829")
C_PANEL     = colors.HexColor("#111827")
C_PANEL2    = colors.HexColor("#0f172a")
C_DARK_BG   = colors.HexColor("#1e293b")
C_BORDER    = colors.HexColor("#1e293b")
C_ACCENT    = colors.HexColor("#3b82f6")
C_CYAN      = colors.HexColor("#06b6d4")
C_GREEN     = colors.HexColor("#10b981")
C_RED       = colors.HexColor("#ef4444")
C_YELLOW    = colors.HexColor("#f59e0b")
C_ORANGE    = colors.HexColor("#f97316")
C_PURPLE    = colors.HexColor("#8b5cf6")
C_TEXT      = colors.HexColor("#e2e8f0")
C_SUB       = colors.HexColor("#94a3b8")
C_MUTE      = colors.HexColor("#475569")
C_WHITE     = colors.white

W, H = A4

# ── Styles ─────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()
    s = {}

    def st(name, parent="Normal", **kw):
        s[name] = ParagraphStyle(name, parent=base[parent], **kw)

    st("body",    fontSize=10, textColor=C_SUB,   leading=16, spaceAfter=6,
       backColor=C_BG)
    st("h1",      fontSize=20, textColor=C_ACCENT, leading=28, spaceBefore=14,
       spaceAfter=4, fontName="Helvetica-Bold")
    st("h2",      fontSize=14, textColor=C_CYAN,   leading=20, spaceBefore=10,
       spaceAfter=4, fontName="Helvetica-Bold")
    st("h3",      fontSize=12, textColor=C_TEXT,   leading=18, spaceBefore=8,
       spaceAfter=4, fontName="Helvetica-Bold")
    st("bullet",  fontSize=10, textColor=C_SUB,   leading=16, spaceAfter=4,
       leftIndent=16, bulletIndent=4)
    st("cover_title", fontSize=40, textColor=C_ACCENT, leading=50,
       fontName="Helvetica-Bold", alignment=TA_CENTER)
    st("cover_sub",   fontSize=14, textColor=C_CYAN,  leading=22,
       alignment=TA_CENTER, fontName="Helvetica-Oblique")
    st("cover_body",  fontSize=12, textColor=C_SUB,   leading=20,
       alignment=TA_CENTER)
    st("toc_num",  fontSize=11, textColor=C_ACCENT, fontName="Helvetica-Bold", leading=18)
    st("toc_lbl",  fontSize=11, textColor=C_SUB,   leading=18)
    st("note",     fontSize=10, textColor=C_YELLOW, leading=14, spaceAfter=6,
       leftIndent=12, borderPad=6)
    st("warn",     fontSize=10, textColor=C_RED,    leading=14, spaceAfter=6,
       leftIndent=12)
    st("tip",      fontSize=10, textColor=C_GREEN,  leading=14, spaceAfter=6,
       leftIndent=12)
    st("code",     fontSize=9,  textColor=C_CYAN,   leading=14, spaceAfter=4,
       fontName="Courier", backColor=C_PANEL2, leftIndent=12)
    st("footer",   fontSize=8,  textColor=C_MUTE,   leading=12, alignment=TA_CENTER)
    st("small",    fontSize=9,  textColor=C_MUTE,   leading=12)
    return s


S = make_styles()


class ColorRect(Flowable):
    """A coloured rectangle used as a section banner background."""
    def __init__(self, w, h, color, radius=6):
        Flowable.__init__(self)
        self.w = w; self.h = h; self.color = color; self.radius = radius
    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.roundRect(0, 0, self.w, self.h, self.radius, fill=1, stroke=0)
    def wrap(self, *args):
        return self.w, self.h


def divider(color=C_BORDER, width=1):
    return HRFlowable(width="100%", thickness=width, color=color, spaceAfter=8, spaceBefore=4)


def sp(n=6):
    return Spacer(1, n)


def h1(text):
    return [Paragraph(text, S["h1"]), divider(C_ACCENT, 1.5), sp(4)]


def h2(text):
    return [Paragraph(f"<b>{text}</b>", S["h2"]), sp(2)]


def body(text):
    return Paragraph(text, S["body"])


def bullet_p(text):
    return Paragraph(f"• &nbsp;{text}", S["bullet"])


def note(text, style="note"):
    return [
        Paragraph(f"<b>{'💡 Tip' if style=='tip' else '⚠️ Warning' if style=='warn' else 'ℹ️ Note'}:</b> {text}", S[style]),
        sp(4)
    ]


def table_block(headers, rows, col_widths=None, accent=C_ACCENT):
    n = len(headers)
    data = [headers] + rows
    if col_widths is None:
        page_w = W - 5*cm
        col_widths = [page_w / n] * n

    ts = TableStyle([
        # Header
        ("BACKGROUND",  (0,0), (-1,0),  C_DARK_BG),
        ("TEXTCOLOR",   (0,0), (-1,0),  accent),
        ("FONTNAME",    (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,0),  9),
        ("BOTTOMPADDING",(0,0),(-1,0),  8),
        ("TOPPADDING",  (0,0), (-1,0),  8),
        # Body
        ("BACKGROUND",  (0,1), (-1,-1), C_NAVY),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[C_PANEL, C_NAVY]),
        ("TEXTCOLOR",   (0,1), (-1,-1), C_SUB),
        ("FONTNAME",    (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",    (0,1), (-1,-1), 9),
        ("TOPPADDING",  (0,1), (-1,-1), 6),
        ("BOTTOMPADDING",(0,1),(-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING",(0,0), (-1,-1), 8),
        # Grid
        ("GRID",        (0,0), (-1,-1), 0.5, C_BORDER),
        ("BOX",         (0,0), (-1,-1), 1,   C_BORDER),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("WORDWRAP",    (0,0), (-1,-1), True),
    ])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(ts)
    return [t, sp(10)]


# ── Page decoration ────────────────────────────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()
    # Background
    canvas.setFillColor(C_BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    # Header bar
    canvas.setFillColor(C_NAVY)
    canvas.rect(0, H-28, W, 28, fill=1, stroke=0)
    canvas.setFillColor(C_ACCENT)
    canvas.rect(0, H-30, W, 2, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(C_MUTE)
    canvas.drawString(2*cm, H-19, "⚡  LaaS Portal — End User Manual v6.0")
    canvas.drawRightString(W-2*cm, H-19, "Wipro SDX INFRA & DC Operations  |  March 2026")
    # Footer bar
    canvas.setFillColor(C_NAVY)
    canvas.rect(0, 0, W, 22, fill=1, stroke=0)
    canvas.setFillColor(C_ACCENT)
    canvas.rect(0, 22, W, 1, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(C_MUTE)
    canvas.drawString(2*cm, 7, "Confidential — Internal Use Only")
    canvas.drawRightString(W-2*cm, 7, f"Page {doc.page}")
    canvas.restoreState()


def on_cover(canvas, doc):
    canvas.saveState()
    # Full dark background
    canvas.setFillColor(C_BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    # Gradient accent band at top
    canvas.setFillColor(C_ACCENT)
    canvas.rect(0, H-6, W, 6, fill=1, stroke=0)
    # Grid lines
    canvas.setStrokeColor(C_BORDER)
    canvas.setLineWidth(0.5)
    for x in range(0, int(W)+1, 48):
        canvas.line(x, 0, x, H)
    for y in range(0, int(H)+1, 48):
        canvas.line(0, y, W, y)
    # Cyan bottom accent
    canvas.setFillColor(C_CYAN)
    canvas.rect(0, 0, W, 6, fill=1, stroke=0)
    canvas.restoreState()


# ── Sections ───────────────────────────────────────────────────────────────
def cover_section():
    els = []
    els.append(sp(80))
    els.append(Paragraph("⚡  LaaS Portal", S["cover_title"]))
    els.append(sp(16))
    els.append(Paragraph("End User Manual &amp; Technical Reference Guide", S["cover_sub"]))
    els.append(sp(8))
    els.append(Paragraph("Lab as a Service  ·  Unified Infrastructure Management Platform", S["cover_body"]))
    els.append(sp(24))
    els.append(HRFlowable(width="60%", thickness=1.5, color=C_ACCENT, hAlign="CENTER", spaceAfter=20, spaceBefore=4))

    meta = [
        ["Version", "6.0"],
        ["Date", "March 2026"],
        ["Organisation", "Wipro SDX INFRA & DC Operations"],
        ["Prepared By", "Sekhar Perumal"],
        ["Approved By", "Khalid Khan"],
    ]
    mt = Table(meta, colWidths=[5*cm, 9*cm], hAlign="CENTER")
    mt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_DARK_BG),
        ("TEXTCOLOR",    (0,0),(0,-1),  C_MUTE),
        ("TEXTCOLOR",    (1,0),(1,-1),  C_TEXT),
        ("FONTNAME",     (0,0),(0,-1),  "Helvetica-Bold"),
        ("FONTNAME",     (1,0),(1,-1),  "Helvetica"),
        ("FONTSIZE",     (0,0),(-1,-1), 11),
        ("PADDING",      (0,0),(-1,-1), 9),
        ("GRID",         (0,0),(-1,-1), 0.5, C_BORDER),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[C_PANEL, C_NAVY]),
    ]))
    els.append(mt)
    els.append(sp(24))

    plat_data = [["🖥️ VMware", "🔴 OpenShift", "🟦 Nutanix", "🎛️ Ansible", "📡 IPAM"]]
    pt = Table(plat_data, colWidths=[3*cm]*5, hAlign="CENTER")
    pt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_DARK_BG),
        ("TEXTCOLOR",    (0,0),(-1,-1), C_CYAN),
        ("FONTSIZE",     (0,0),(-1,-1), 11),
        ("FONTNAME",     (0,0),(-1,-1), "Helvetica-Bold"),
        ("ALIGN",        (0,0),(-1,-1), "CENTER"),
        ("PADDING",      (0,0),(-1,-1), 8),
        ("BOX",          (0,0),(-1,-1), 1, C_ACCENT),
        ("INNERGRID",    (0,0),(-1,-1), 0.5, C_BORDER),
    ]))
    els.append(pt)
    els.append(PageBreak())
    return els


def toc_section():
    els = []
    els += h1("Table of Contents")
    items = [
        ("01", "Introduction & About LaaS Portal"),
        ("02", "System Requirements"),
        ("03", "Quick Start Guide"),
        ("04", "Navigation & UI Overview"),
        ("05", "Overview Dashboard"),
        ("06", "VMware Module"),
        ("07", "Snapshot Management"),
        ("08", "Red Hat OpenShift Module"),
        ("09", "Nutanix AHV Module"),
        ("10", "Ansible AAP Module"),
        ("11", "Capacity Planning"),
        ("12", "Project Utilization"),
        ("13", "Chargeback"),
        ("14", "Networks & IPAM"),
        ("15", "VM Request Workflow"),
        ("16", "Audit Log"),
        ("17", "User Roles & Permissions"),
        ("18", "Technical Specifications"),
        ("19", "FAQ & Troubleshooting"),
        ("20", "Document Authorization"),
    ]
    toc_data = [[Paragraph(f"<b>{num}</b>", S["toc_num"]),
                 Paragraph(label, S["toc_lbl"])] for num, label in items]
    t = Table(toc_data, colWidths=[1.5*cm, 14*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C_PANEL),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [C_PANEL, C_NAVY]),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("GRID",          (0,0),(-1,-1), 0.3, C_BORDER),
    ]))
    els.append(t)
    els.append(PageBreak())
    return els


def intro_section():
    els = []
    els += h1("1.  Introduction & About LaaS Portal")
    els.append(body(
        "The <b>LaaS Portal (Lab as a Service)</b> is Wipro's unified infrastructure management platform for "
        "SDX INFRA &amp; DC Operations. It provides a single-pane-of-glass web dashboard to manage, monitor, "
        "and operate multi-cloud and on-premises resources across VMware vCenter, Red Hat OpenShift, Nutanix AHV, "
        "and Ansible Automation Platform."
    ))
    els.append(sp(8))
    els += h2("Key Features")
    features = [
        ("Unified Multi-Platform View", "Single dashboard for VMware, OpenShift, Nutanix, and Ansible — no separate logins."),
        ("VM Lifecycle Management", "Power on/off, clone, migrate, snapshot, and delete VMs directly from the portal."),
        ("Capacity Planning", "CPU, RAM, and storage utilisation trends with forecasting gauges."),
        ("Role-Based Access Control", "Admin, Operator, Viewer, and Requester roles with granular permissions."),
        ("VM Request & Approval Workflow", "Requesters raise VM provisioning requests; Admins approve or reject."),
        ("Automated Chargeback", "Project-based cost allocation with monthly PDF/CSV export."),
        ("IPAM Integration", "Live IP address management — subnet occupancy, free IPs, allocation history."),
        ("Full Audit Log", "Every action logged with user, timestamp, and resource for compliance."),
    ]
    for title, desc in features:
        els.append(Paragraph(f"• &nbsp;<b>{title}:</b> &nbsp;{desc}", S["bullet"]))
    els.append(PageBreak())
    return els


def sysreq_section():
    els = []
    els += h1("2.  System Requirements")
    els += table_block(
        ["Requirement", "Details"],
        [
            ["Supported Browsers", "Chrome 110+, Edge 110+, Firefox 115+, Safari 16+"],
            ["JavaScript", "Must be enabled (React single-page application)"],
            ["Screen Resolution", "Minimum 1280×768 · Recommended 1920×1080"],
            ["Network", "Corporate LAN or VPN connection required"],
            ["Portal URL", "http://<server-ip>:5173 (dev) · http://<server-ip>:80 (prod)"],
            ["Authentication", "Username + Password (local accounts managed by Admin)"],
            ["Session Timeout", "Auto-logout after 30 minutes of inactivity"],
        ],
        col_widths=[5*cm, 11*cm]
    )
    els.append(PageBreak())
    return els


def quickstart_section():
    els = []
    els += h1("3.  Quick Start Guide")
    steps = [
        ("1", "Open the Portal", "Navigate to http://<server-ip> in your browser. Ensure you are on the corporate network or VPN."),
        ("2", "Log In", "Enter your username and password. Default demo credentials: admin / admin123"),
        ("3", "Select Environment", "Use the vCenter dropdown to choose a specific vCenter or 'All vCenters' for an aggregated view."),
        ("4", "Explore the Dashboard", "The Overview page shows the SDx Infrastructure banner with live platform counts and KPI cards."),
        ("5", "Navigate by Platform", "Use the left sidebar to switch between VMware (with Snapshots nested), OpenShift, Nutanix, Ansible, IPAM, etc."),
        ("6", "Global Search", "Press Ctrl+K or use the search bar to instantly jump to any VM, snapshot, or cluster."),
    ]
    step_data = [[Paragraph(f"<b>{n}</b>", S["h3"]),
                  Paragraph(f"<b>{t}</b><br/><font color='#{C_SUB.hexval()[2:]}'>{b}</font>", S["body"])]
                 for n, t, b in steps]
    t = Table(step_data, colWidths=[1.5*cm, 14*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(0,-1), C_ACCENT),
        ("TEXTCOLOR",    (0,0),(0,-1), C_WHITE),
        ("ALIGN",        (0,0),(0,-1), "CENTER"),
        ("VALIGN",       (0,0),(-1,-1),"TOP"),
        ("BACKGROUND",   (1,0),(1,-1), C_PANEL),
        ("ROWBACKGROUNDS",(1,0),(1,-1),[C_PANEL, C_NAVY]),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("GRID",         (0,0),(-1,-1), 0.3, C_BORDER),
    ]))
    els.append(t)
    els.append(sp(8))
    els += note("Press <b>Ctrl+K</b> or click the global search bar to instantly navigate to any VM, OCP cluster, snapshot, or page.", "tip")
    els.append(PageBreak())
    return els


def navigation_section():
    els = []
    els += h1("4.  Navigation & UI Overview")
    els += h2("Portal Layout — Three Zones")
    zones = [
        ["Left Sidebar", "Navigation links, Solution Sphere analog clock, multi-platform live health status (VMware / OCP / Nutanix)."],
        ["Top Bar", "vCenter selector, global search, dark/light theme toggle, user profile, notification bell."],
        ["Main Content", "Page-specific content: dashboards, tables, forms, charts — updates per selected navigation item."],
    ]
    els += table_block(["Zone", "Description"], zones, col_widths=[4*cm, 12*cm])
    els += h2("Sidebar Navigation Items")
    els += table_block(
        ["Icon", "Label", "Description", "Roles"],
        [
            ["🏠", "Overview", "SDx Infrastructure banner, platform health, KPIs", "All"],
            ["🖥️", "VMware", "VM list, power/clone/migrate/snapshot actions", "Admin, Operator, Viewer"],
            ["📸", "↳ Snapshots", "All VM snapshots — nested under VMware", "Admin, Operator, Viewer"],
            ["🔴", "Red Hat OpenShift", "Cluster status, node/pod/operator health", "Admin, Operator, Viewer"],
            ["🟦", "Nutanix", "Prism Central overview, cluster/VM/storage", "Admin, Operator, Viewer"],
            ["🎛️", "Ansible AAP", "Job templates, inventory, recent runs", "Admin, Operator, Viewer"],
            ["🏷️", "Project Utilization", "Per-project resource allocation breakdown", "Admin, Operator, Viewer"],
            ["🗄️", "Capacity", "CPU/RAM/storage gauges, trend charts", "Admin, Operator, Viewer"],
            ["💳", "Chargeback", "Monthly cost by project, export PDF/CSV", "Admin, Operator, Viewer"],
            ["🌐", "Networks", "Port groups, VLANs, connected VMs", "Admin, Operator, Viewer"],
            ["📡", "IPAM", "Subnet overview, IP allocation, free IP finder", "Admin, Operator, Viewer"],
            ["🗃️", "Asset Mgmt", "Physical and virtual asset inventory", "Admin, Operator, Viewer"],
            ["📋", "VM Requests", "Raise new VM request, view history", "All"],
            ["🔍", "Audit Log", "Complete action history with filters", "Admin, Operator"],
            ["🌲", "AD & DNS", "Active Directory and DNS management", "Admin, Operator"],
            ["👥", "Users & Roles", "Create/edit users, assign roles", "Admin only"],
        ],
        col_widths=[1.2*cm, 3.5*cm, 7*cm, 4*cm]
    )
    els.append(PageBreak())
    return els


def roles_section():
    els = []
    els += h1("17.  User Roles & Permissions")
    els += h2("Role Descriptions")
    els += table_block(
        ["Role", "Description", "Key Permissions"],
        [
            ["Admin", "Full administrative access", "All operations including user management and VM deletion"],
            ["Operator", "Day-to-day operations", "VM power/clone/migrate/snapshot, Ansible jobs, all reports"],
            ["Viewer", "Read-only access", "View dashboards, reports, VM list, IPAM — no writes"],
            ["Requester", "Self-service requests", "Raise VM requests only — limited to VM Requests + Overview"],
        ],
        col_widths=[3*cm, 5*cm, 8.5*cm]
    )
    els += h2("Permission Matrix")
    els += table_block(
        ["Feature / Action", "Admin", "Operator", "Viewer", "Requester"],
        [
            ["View Overview Dashboard", "✅", "✅", "✅", "✅"],
            ["View VM List", "✅", "✅", "✅", "❌"],
            ["Power On/Off/Reboot VM", "✅", "✅", "❌", "❌"],
            ["Clone VM", "✅", "✅", "❌", "❌"],
            ["Migrate VM (vMotion)", "✅", "✅", "❌", "❌"],
            ["Create Snapshot", "✅", "✅", "❌", "❌"],
            ["Delete Snapshot", "✅", "✅", "❌", "❌"],
            ["Delete VM from Disk", "✅", "❌", "❌", "❌"],
            ["View Capacity Reports", "✅", "✅", "✅", "❌"],
            ["View Chargeback", "✅", "✅", "✅", "❌"],
            ["View Audit Log", "✅", "✅", "❌", "❌"],
            ["Manage Users & Roles", "✅", "❌", "❌", "❌"],
            ["Raise VM Request", "✅", "✅", "✅", "✅"],
            ["Approve/Reject VM Request", "✅", "❌", "❌", "❌"],
            ["Launch Ansible Jobs", "✅", "✅", "❌", "❌"],
            ["Export Reports (CSV/PDF)", "✅", "✅", "❌", "❌"],
        ],
        col_widths=[7*cm, 2*cm, 2.5*cm, 2*cm, 2.5*cm]
    )
    els.append(PageBreak())
    return els


def techspecs_section():
    els = []
    els += h1("18.  Technical Specifications")
    els += h2("Server Hardware")
    els += table_block(
        ["Component", "Specification"],
        [
            ["CPU", "Intel Xeon Gold 6130 — 2× 8-core / 16-thread = 16 physical cores / 32 threads"],
            ["RAM", "24 GB DDR4 ECC (usable ~22 GB)"],
            ["Storage", "300 GB SSD"],
            ["Network", "1 Gbps NIC to corporate LAN"],
            ["Operating System", "Windows Server 2019 Standard"],
            ["Concurrent Users", "30–60 (up to 100+ with software optimisations)"],
        ],
        col_widths=[5*cm, 11*cm]
    )
    els += h2("Software Stack")
    els += table_block(
        ["Component", "Technology"],
        [
            ["Frontend", "React 18 + Vite 7 (single-page application)"],
            ["Backend", "FastAPI 0.111+ (Python 3.11+)"],
            ["ASGI Server", "Uvicorn (4–8 workers recommended)"],
            ["Database", "SQLite 3 with WAL mode"],
            ["VMware SDK", "pyVmomi (vSphere SDK for Python)"],
            ["OCP Integration", "kubernetes Python client + Prometheus HTTP API"],
            ["Nutanix Integration", "Prism Central REST API v3"],
            ["Ansible Integration", "Ansible AAP REST API v2"],
            ["IPAM Integration", "phpIPAM REST API"],
        ],
        col_widths=[5*cm, 11*cm]
    )
    els += h2("Key API Endpoints")
    els += table_block(
        ["Method", "Endpoint", "Description"],
        [
            ["GET",    "/api/vcenters",                        "List all registered vCenter instances"],
            ["GET",    "/api/vms/{vc_id}",                     "Fetch all VMs for a vCenter"],
            ["POST",   "/api/vm/{vc_id}/{vm_name}/power",      "Power on/off/reboot a VM"],
            ["POST",   "/api/vm/{vc_id}/{vm_name}/snapshot",   "Create a VM snapshot"],
            ["DELETE", "/api/vm/{vc_id}/{vm_name}/snapshot",   "Delete a VM snapshot"],
            ["POST",   "/api/vm/{vc_id}/{vm_name}/clone",      "Clone a VM"],
            ["GET",    "/api/ocp/clusters",                    "List all OCP clusters"],
            ["GET",    "/api/nutanix/pcs",                     "List all Nutanix Prism Centrals"],
            ["GET",    "/api/audit",                           "Fetch audit log entries"],
        ],
        col_widths=[2.5*cm, 7.5*cm, 6.5*cm]
    )
    els.append(PageBreak())
    return els


def faq_section():
    els = []
    els += h1("19.  FAQ & Troubleshooting")
    faqs = [
        ("Portal shows '0 VMs' but vCenter has VMs",
         "Check the vCenter is registered and credentials are valid. Try Retry/Refresh on the Overview page. Check backend logs for API errors."),
        ("Cannot see Audit Log or Users menu",
         "Audit Log requires Operator or Admin role. Users & Roles requires Admin. Contact your Admin to upgrade your role."),
        ("Snapshot creation timed out",
         "Large VMs on busy datastores can exceed the portal timeout. Check the vCenter task list directly. Retry during off-peak hours."),
        ("OCP cluster shows 'Degraded' but seems healthy",
         "The portal flags Degraded if >25% of nodes are NotReady OR >15% of Cluster Operators are degraded. Transient cycling during upgrades can trigger this briefly."),
        ("How to add a new vCenter / OCP cluster / Nutanix?",
         "Navigate to Settings (Admin only) → Add vCenter / Add OCP Cluster / Add Nutanix PC. Enter the endpoint URL and credentials, then save."),
        ("Can I export VM lists or capacity reports?",
         "Yes — most tables have CSV export (Admin and Operator). Chargeback also has PDF export. Audit log CSV requires Admin."),
        ("Analog clock shows wrong time",
         "The clock uses the browser's local system clock. Ensure your workstation is synchronized to the corporate NTP server."),
    ]
    for q, a in faqs:
        els.append(Paragraph(f"<b>Q: {q}</b>", S["h3"]))
        els.append(Paragraph(f"A: {a}", S["body"]))
        els.append(divider())
    els.append(PageBreak())
    return els


def auth_section():
    els = []
    els += h1("20.  Document Authorization")
    auth_data = [
        [Paragraph("<b>PREPARED BY</b>", S["small"]),
         Paragraph("<b>APPROVED BY</b>", S["small"])],
        [Paragraph("<b><font size='16' color='#e2e8f0'>Sekhar Perumal</font></b><br/>"
                   "<font color='#3b82f6'>SDX Infrastructure &amp; DC Operations · Wipro</font><br/>"
                   "<font color='#475569'>March 2026</font>", S["body"]),
         Paragraph("<b><font size='16' color='#e2e8f0'>Khalid Khan</font></b><br/>"
                   "<font color='#10b981'>SDX Infrastructure &amp; DC Operations · Wipro</font><br/>"
                   "<font color='#475569'>March 2026</font>", S["body"])],
    ]
    at = Table(auth_data, colWidths=[8*cm, 8*cm])
    at.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_DARK_BG),
        ("TEXTCOLOR",    (0,0),(-1,0),  C_MUTE),
        ("TOPPADDING",   (0,0),(-1,-1), 14),
        ("BOTTOMPADDING",(0,0),(-1,-1), 14),
        ("LEFTPADDING",  (0,0),(-1,-1), 18),
        ("RIGHTPADDING", (0,0),(-1,-1), 18),
        ("GRID",         (0,0),(-1,-1), 0.5, C_BORDER),
        ("BOX",          (0,0),(-1,-1), 1.5, C_ACCENT),
        ("LINEAFTER",    (0,0),(0,-1),  1,   C_BORDER),
    ]))
    els.append(at)
    els.append(sp(24))
    els.append(HRFlowable(width="100%", thickness=1, color=C_ACCENT, spaceAfter=12))
    els.append(Paragraph(
        "<b>LaaS Portal — End User Manual v6.0</b>  ·  Wipro SDX INFRA &amp; DC Operations  ·  March 2026",
        S["footer"]
    ))
    els.append(Paragraph("Confidential — Internal Use Only", S["footer"]))
    return els


def vmware_section():
    els = []
    els += h1("6.  VMware Module")
    els.append(body("Full VM lifecycle management across all registered vCenter instances."))
    els.append(sp(6))
    els += h2("VM Table Columns")
    els += table_block(
        ["Column", "Description"],
        [
            ["VM Name", "Display name of the virtual machine"],
            ["Status", "Power state: Running / Stopped / Suspended"],
            ["IP Address", "Primary guest IP (requires VMware Tools)"],
            ["OS", "Guest OS type detected via VMware Tools"],
            ["CPU / RAM", "vCPU count and allocated RAM in GB"],
            ["Host", "ESXi host the VM is currently running on"],
            ["Snapshots", "📸 count badge — click to view/delete"],
            ["Uptime", "How long the VM has been powered on"],
            ["Actions", "Power · Snapshot · Clone · Migrate · Delete"],
        ],
        col_widths=[5*cm, 11*cm]
    )
    els += h2("Available Actions")
    els += table_block(
        ["Action", "Description", "Required Role"],
        [
            ["Power On / Off", "Start or shutdown the VM", "Operator, Admin"],
            ["Reboot", "Restart the guest OS", "Operator, Admin"],
            ["Clone", "Create a copy to a new name", "Operator, Admin"],
            ["Live Migrate", "Move running VM to another ESXi host", "Operator, Admin"],
            ["Create Snapshot", "Take a point-in-time snapshot", "Operator, Admin"],
            ["Delete Snapshot", "Remove a specific snapshot", "Operator, Admin"],
            ["Delete from Disk", "Permanently remove VM and all files", "Admin only"],
        ],
        col_widths=[4*cm, 7.5*cm, 5*cm]
    )
    els += note("'Delete from Disk' permanently removes the VM and all its files. This action CANNOT be undone.", "warn")
    els.append(PageBreak())
    return els


# ── MAIN ───────────────────────────────────────────────────────────────────
def build():
    doc = SimpleDocTemplate(
        OUT,
        pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2.5*cm,
        topMargin=2.5*cm, bottomMargin=2.5*cm,
        title="LaaS Portal — End User Manual v6.0",
        author="Sekhar Perumal — Wipro SDX INFRA & DC Operations",
        subject="LaaS Portal End User Manual",
        creator="LaaS Portal Documentation Generator",
    )

    story = []

    # Cover (uses different page template — no header/footer)
    story += cover_section()
    story += toc_section()
    story += intro_section()
    story += sysreq_section()
    story += quickstart_section()
    story += navigation_section()

    # Overview
    story += h1("5.  Overview Dashboard")
    story.append(body("The SDx Infrastructure Overview banner shows live aggregate stats: platform pills (VMware/OCP/Nutanix), and five KPI cards: Total VMs, ESXi Hosts, OCP Nodes, Nutanix Hosts, OCP Pods. Below the banner are Environment Charts, vCenter Summary Cards, Quick KPI Cards, and Capacity Detail rows."))
    story.append(PageBreak())

    story += vmware_section()

    # Snapshots
    story += h1("7.  Snapshot Management")
    story.append(body("The Snapshots page (nested under VMware) provides a centralised view of all VM snapshots across all vCenters. Columns: VM Name · Snapshot Name · Creation Date · Age (days) · vCenter. Actions: Delete individual or bulk-select and delete multiple snapshots."))
    story += note("Aged snapshots (&gt;7 days) consume significant datastore space and degrade VM performance. Review and clean up regularly.", "tip")
    story.append(PageBreak())

    # OCP
    story += h1("8.  Red Hat OpenShift Module")
    for item in ["Cluster Health — status, API health, version", "Node Status — Master/Worker/Infra counts with Ready/NotReady", "Pod Overview — Running, Pending, Failed counts", "Cluster Operators — Available/Degraded/Progressing", "Resource Usage — CPU/Memory gauges via Prometheus", "Alerts — Firing alerts from Alertmanager"]:
        story.append(bullet_p(item))
    story.append(PageBreak())

    # Nutanix
    story += h1("9.  Nutanix AHV Module")
    for item in ["Cluster Overview — host count, VM count, storage, AOS version", "VM Status — running/stopped with resource allocation", "Storage — storage pool usage, container free space", "Alerts — Critical/Warning/Info from Prism Central", "Hardware Health — node/disk/NIC status"]:
        story.append(bullet_p(item))
    story.append(PageBreak())

    # Ansible
    story += h1("10.  Ansible AAP Module")
    story += table_block(
        ["Feature", "Description"],
        [["Job Templates", "Browse all templates; launch directly from portal"],
         ["Job History", "Recent job runs with status, duration, user"],
         ["Inventory", "Host groups, counts, sync status"],
         ["Dashboard Stats", "Total hosts, success rate, running jobs"]],
        col_widths=[5*cm, 11*cm]
    )
    story.append(PageBreak())

    # Capacity
    story += h1("11.  Capacity Planning")
    for item in ["Utilisation Gauges — animated arc, green <60%, yellow 60–80%, red >80%", "ESXi Host Table — per-host CPU/RAM free, VM count", "Datastore Table — name, type, capacity, free space, usage bar", "Trend Charts — 7/14/30-day historical trend lines"]:
        story.append(bullet_p(item))
    story += note("When any resource exceeds 80% utilisation, the gauge turns red. Notify your infrastructure team immediately.", "warn")
    story.append(PageBreak())

    # Sections 12–16 abbreviated
    for num, title, content in [
        ("12", "Project Utilization", "Displays resource consumption by project (cost center/tag). Each row shows VM count, vCPU, RAM (GB), Storage (GB), and a visual bar showing the project's share of total resources."),
        ("13", "Chargeback", "Calculates monthly infrastructure costs per project using configurable rate cards (vCPU, RAM GB, Storage GB per month). Supports month selector, project filter, and export to PDF/CSV."),
        ("14", "Networks & IPAM", "Networks: vCenter port groups with VLAN IDs and connected VM counts. IPAM: subnet overview with used/free IP counts, occupancy bar, allocation table, and free IP finder."),
        ("15", "VM Request Workflow", "Requesters raise VM requests (name, vCPU, RAM, OS, project). Admins receive a notification badge, review the request, then Approve or Reject with optional comments. Approved requests are provisioned from a template."),
        ("16", "Audit Log", "Every user action is recorded: Timestamp · User · Action Type · Resource · Status · Details. Filters: date range, user, action type, status. CSV export available to Admins."),
    ]:
        story += h1(f"{num}.  {title}")
        story.append(body(content))
        story.append(PageBreak())

    story += roles_section()
    story += techspecs_section()
    story += faq_section()
    story += auth_section()

    # Build with page templates
    doc.build(story,
              onFirstPage=on_cover,
              onLaterPages=on_page)
    print(f"✅  Saved: {OUT}")


if __name__ == "__main__":
    build()
