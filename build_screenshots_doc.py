"""Build the LaaS Features & Screenshots HTML document with base64-embedded images."""
import base64, os

DIR = r"C:\caas-dashboard\screenshots"
OUT_HTML = r"C:\caas-dashboard\LaaS_Features_Screenshots.html"

def b64(fname):
    path = os.path.join(DIR, fname)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()

# Define sections: (screenshot_file, title, description, features_list)
SECTIONS = [
    ("00_login.png", "Login Page",
     "Secure authentication portal with Active Directory integration and local account support.",
     ["Active Directory (sdxtest.local) SSO authentication",
      "Local portal accounts with JWT Bearer tokens",
      "Role-based access: Admin, Operator, Viewer, Requester",
      "Session persistence via sessionStorage",
      "Clean, branded login experience with LaaS identity"]),

    ("01_overview.png", "Overview Dashboard",
     "The main landing page providing a unified view across all eight managed infrastructure platforms at a glance.",
     ["Global Infrastructure Banner with live platform health (RAG indicators)",
      "VMware, OpenShift, Nutanix, AWS, Hyper-V connection status pills",
      "Interactive multi-platform VM distribution donut charts",
      "VMware capacity gauges — CPU, RAM, Storage with animated fill bars",
      "Top utilised IPAM subnets with usage percentage bars",
      "Live alerts summary with severity chips",
      "SDx Lab Topology quick-launch button",
      "Analog + digital clock with date display"]),

    ("02_vmware.png", "VMware vCenter Management",
     "Full VM lifecycle management across all connected vCenter instances with bulk operations and topology views.",
     ["Live VMs list with power state, CPU, RAM, disk, IP, host, OS",
      "Power On / Off / Restart / Clone / Migrate (vMotion) actions",
      "Reconfigure CPU, RAM, disk size dynamically",
      "Snapshot create, delete, and age tracking",
      "ESXi host capacity: CPU & memory utilisation charts",
      "Datastore usage with colour-coded free space indicators",
      "Network inventory across all vCenters",
      "Bulk VM actions: power, clone, migrate multiple VMs",
      "Full-text search by VM name, OS, IP, or host",
      "VM-to-host topology relationship diagrams"]),

    ("03_openshift.png", "Red Hat OpenShift",
     "Comprehensive OpenShift cluster monitoring with node management, pod inventory, and operator health tracking.",
     ["Multi-cluster monitoring with per-cluster health indicators",
      "Node management: CPU/RAM bars, cordon, uncordon, drain",
      "Pod inventory with namespace, node, phase, age, log streaming",
      "Namespace overview with pod/service/deployment counts",
      "Operator health: Available / Progressing / Degraded status",
      "Routes with clickable HTTPS/HTTP URLs and TLS info",
      "Storage classes with provisioner and reclaim policy",
      "RHOAI (Red Hat OpenShift AI) dashboard integration",
      "Interactive cluster topology diagrams",
      "Events stream with severity filtering"]),

    ("04_nutanix.png", "Nutanix Prism Central",
     "Multi-site DC/DR Prism Central management with VM, host, storage, and alert monitoring across all clusters.",
     ["Separate DC and DR Prism Central grouping",
      "AHV VMs: power state, vCPUs, RAM, IPs, power actions",
      "On-demand VM snapshots via Prism Central v3 API",
      "Host inventory with CPU, RAM, IPMI and CVM IPs",
      "Storage containers with usage and free space metrics",
      "Network subnets with VLAN ID and IP pool ranges",
      "Live cluster alerts: Critical / Warning severity",
      "3-step VM provisioning wizard with live image dropdown",
      "Per-PC health status with RAG indicators",
      "Storage total/used with percentage utilisation"]),

    ("05_ansible.png", "Ansible Automation Platform",
     "Job template management, inventory browsing, and playbook execution with live output streaming.",
     ["Browse all job templates across AAP instances",
      "View inventories, credentials, and host groups",
      "Launch job templates with custom extra-vars from portal",
      "Live job execution with real-time stdout streaming",
      "Activity stream for full automation audit trail",
      "Filter by event type, timestamp, and user",
      "Correlates with portal-wide audit log"]),

    ("06_aws.png", "Amazon Web Services",
     "EC2 instance management, S3/RDS discovery, VPC networking, and cost tracking via AWS SDK.",
     ["EC2 instance discovery with type, AZ, state, IPs",
      "Start, Stop, and Reboot EC2 instances from portal",
      "S3 bucket listing and RDS database inventory",
      "VPC and subnet IP utilisation tracking",
      "IAM user and SSO session token support",
      "AWS Cost Explorer integration for spending data",
      "Live status indicator in Overview banner"]),

    ("07_hyperv.png", "Microsoft Hyper-V",
     "Standalone Hyper-V host management via WinRM PowerShell remoting with no agent installation required.",
     ["VM inventory with power state, CPU, memory, disk",
      "Power actions: start, stop, restart VMs",
      "Checkpoint management: create, restore, delete",
      "Per-host CPU usage % and RAM utilisation bars",
      "Logical processor count and total/used RAM",
      "WinRM PowerShell remoting — no agent required",
      "Live health status in Overview banner"]),

    ("08_ad_dns.png", "Active Directory & DNS",
     "Full AD user, group, and DNS record management via pure LDAP — no WinRM or PowerShell agents needed.",
     ["Browse all AD users with OU and account status",
      "Create users with password policy and group copy",
      "Enable / Disable / Unlock / Delete accounts",
      "Reset passwords without domain controller access",
      "Group membership management: add and remove",
      "DNS zones: A, CNAME, MX, PTR, SRV, NS, TXT records",
      "Add and delete DNS records from the portal",
      "Flush entire DNS server cache",
      "Pure LDAP (MS-ADTS / MS-DNSP) — no WinRM"]),

    ("09_ipam.png", "IPAM & Network Management",
     "SolarWinds IPAM integration providing subnet grid, utilisation tracking, and IP search capabilities.",
     ["Subnet grid with percentage utilisation bars",
      "IP search within any subnet",
      "Top utilised subnets on Overview page",
      "Subnet details: CIDR, gateway, VLAN, IP counts",
      "Colour-coded utilisation thresholds",
      "SolarWinds REST API integration"]),

    ("10_chargeback.png", "Chargeback & Pricing",
     "Per-platform cost calculation with configurable pricing rates and project-level billing aggregation.",
     ["VMware, OpenShift, and Nutanix pricing panels",
      "Per-resource rates: CPU, RAM, disk, pod",
      "Monthly cost breakdown in INR (₹) and USD ($)",
      "Project-level billing via VMware tags",
      "Owner and email mapped per project",
      "Configurable pricing rates saved server-side",
      "PDF export for billing and planning"]),

    ("11_assets.png", "Asset Inventory",
     "Physical and logical asset tracking with search, inline editing, filters, and CSV export.",
     ["Physical and virtual asset tracking",
      "Full-text search across all asset fields",
      "Inline editing of asset properties",
      "Filter by type, location, status",
      "CSV export of entire asset inventory",
      "Rack topology and location mapping"]),

    ("12_vm_requests.png", "VM Request Workflow",
     "Self-service VM provisioning with platform picker, guided wizard, and admin approval workflow.",
     ["Single '+ Request VM' button with platform picker",
      "VMware: standard provisioning form",
      "OpenShift: 3-step form — cluster, namespace, workload type",
      "Nutanix: live image dropdown from Prism Central",
      "Admin/Operator approval or decline workflow",
      "Request status tracking for requesters",
      "Reviews page with platform tabs: VMware · OCP · Nutanix"]),

    ("13_insights.png", "Insights & Analytics (NEW v6.2)",
     "The flagship v6.2 feature — four dedicated analytics tabs powered by PostgreSQL daily snapshots.",
     ["Health Scorecard: RAG status across all 8 platforms with trend arrows",
      "Change Detection: automatic day-over-day drift alerts",
      "Capacity & Cost: storage exhaustion predictions + INR/USD chargeback",
      "Executive Summary: one-page PDF-ready overview with KPI matrix",
      "PostgreSQL 16 database with 12 snapshot tables",
      "Automated daily collector at 11 PM across all platforms",
      "30-day rolling retention with automatic data purge",
      "Retry logic with exponential back-off for resilient collection"]),

    ("14_history.png", "Historical Trending (NEW v6.2)",
     "Interactive trend charts displaying metric changes over 7, 14, and 30-day windows.",
     ["Interactive trend charts for 7/14/30-day windows",
      "VM count, host count, pod count trends",
      "IP utilisation trends over time",
      "Day-over-day change arrows with % shift values",
      "CSV-exportable historical data snapshots",
      "Backed by PostgreSQL daily snapshots"]),

    ("15_forecast.png", "Capacity Forecasting (NEW v6.2)",
     "Linear regression predictions for storage, compute, and network resource exhaustion dates.",
     ["Linear regression capacity forecasting per metric",
      "Storage exhaustion date predictions",
      "Compute resource exhaustion warnings",
      "Network/IP utilisation growth projections",
      "Visual forecast trend lines with confidence bands",
      "Early-warning indicators for capacity planning"]),

    ("16_audit.png", "Audit Log",
     "Comprehensive portal-wide audit trail recording every user action with timestamps and details.",
     ["Full portal audit log — every action recorded",
      "Filter by user, action type, timestamp, platform",
      "Exportable audit data for compliance",
      "Correlates with Ansible activity stream",
      "Action details: target resource, outcome, IP address"]),

    ("17_about_laas.png", "About LaaS",
     "In-app information modal with version history, features list, how-to guide, and role documentation.",
     ["What's New tab with version-by-version changelog",
      "What is LaaS: platform overview with descriptions",
      "Features tab: detailed per-platform feature cards",
      "How To Use: step-by-step getting started guide",
      "Access & Roles: permission matrix for all 4 roles",
      "Portal voiceover: 2-minute audio feature walkthrough"]),

    ("18_support.png", "Support & Escalation Matrix",
     "Team contact directory with org hierarchy, designations, technology areas, and direct email links.",
     ["Full org hierarchy: ADH → Engineering Head → Domain Teams",
      "DC & VMware, OpenShift & AI, Storage & Nutanix domains",
      "Full names, designations, technology areas",
      "Wipro email IDs with click-to-email and copy",
      "Searchable via Universal Global Search"]),
]

# Build HTML
html_parts = []
html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LaaS Dashboard — Features, Capabilities & Screenshots v6.2</title>
<style>
  @page { size: A4 landscape; margin: 14mm 12mm; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'Segoe UI', Calibri, Arial, sans-serif;
    color: #1e293b; background: #fff; line-height: 1.6; font-size: 10.5pt;
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
  }
  .cover {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #1e40af 100%);
    color: #fff; padding: 48px 56px 40px; border-radius: 0 0 14px 14px;
    page-break-after: always;
  }
  .cover h1 { font-size: 36pt; font-weight: 900; letter-spacing: -.5px; }
  .cover h1 span { color: #93c5fd; font-weight: 400; font-size: 24pt; }
  .cover .sub { font-size: 14pt; color: rgba(255,255,255,.72); margin-top: 8px; }
  .cover .ver {
    display: inline-block; background: rgba(255,255,255,.18);
    padding: 5px 16px; border-radius: 20px; font-size: 11pt;
    font-weight: 600; margin-top: 12px; letter-spacing: .5px;
  }
  .cover .meta { margin-top: 14px; font-size: 10pt; color: rgba(255,255,255,.55); }
  .cover .toc { margin-top: 32px; }
  .cover .toc h2 { font-size: 16pt; border-bottom: 2px solid rgba(255,255,255,.25); padding-bottom: 6px; margin-bottom: 14px; color: #93c5fd; }
  .cover .toc-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px 20px; }
  .cover .toc-item {
    font-size: 10.5pt; color: rgba(255,255,255,.85); display: flex; align-items: center; gap: 8px;
    padding: 4px 0;
  }
  .cover .toc-num {
    background: rgba(255,255,255,.15); border-radius: 6px; padding: 2px 8px;
    font-weight: 700; font-size: 9pt; min-width: 28px; text-align: center;
  }

  .content { padding: 28px 36px; }

  .section {
    page-break-inside: avoid;
    page-break-after: always;
    margin-bottom: 20px;
  }
  .section:last-child { page-break-after: auto; }

  .section-hdr {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 18px; border-radius: 10px;
    margin-bottom: 14px; page-break-after: avoid;
  }
  .section-hdr .num {
    font-size: 20pt; font-weight: 900; opacity: .7; min-width: 38px;
  }
  .section-hdr h2 {
    font-size: 16pt; font-weight: 800; letter-spacing: -.3px;
    border: none; margin: 0; padding: 0;
  }
  .section-hdr .badge {
    font-size: 8pt; font-weight: 800; padding: 3px 10px; border-radius: 20px;
    background: #6366f120; color: #6366f1; border: 1px solid #6366f140;
    margin-left: 8px; letter-spacing: .4px;
  }

  .desc {
    font-size: 11pt; color: #475569; margin-bottom: 14px; line-height: 1.7;
    padding: 0 4px;
  }

  .screenshot-wrap {
    border: 2px solid #e2e8f0; border-radius: 10px; overflow: hidden;
    margin-bottom: 14px; box-shadow: 0 2px 12px rgba(0,0,0,.08);
    page-break-inside: avoid;
  }
  .screenshot-wrap img {
    width: 100%; height: auto; display: block;
  }
  .screenshot-label {
    background: #f1f5f9; padding: 6px 14px; font-size: 9pt; color: #64748b;
    font-weight: 600; border-top: 1px solid #e2e8f0;
    display: flex; align-items: center; gap: 6px;
  }

  .features-grid {
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 5px 18px; padding: 0 4px;
  }
  .feat-item {
    display: flex; align-items: flex-start; gap: 7px;
    font-size: 10pt; line-height: 1.65; color: #334155;
  }
  .feat-item .ck {
    color: #10b981; font-weight: 800; flex-shrink: 0; margin-top: 2px;
  }

  .contact-section { page-break-inside: avoid; margin-top: 24px; }
  .contact-grid {
    display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; margin: 14px 0;
  }
  .contact-card {
    border-radius: 10px; padding: 20px 16px; text-align: center;
    page-break-inside: avoid;
  }
  .contact-card .avatar { font-size: 30pt; margin-bottom: 6px; }
  .contact-card .name { font-size: 13pt; font-weight: 800; margin-bottom: 3px; }
  .contact-card .role { font-size: 10pt; font-weight: 600; margin-bottom: 8px; }
  .contact-card .email { font-size: 9.5pt; }
  .contact-card .email a { color: #3b82f6; text-decoration: none; }

  .footer {
    border-top: 2px solid #e2e8f0; padding: 14px 36px;
    font-size: 9pt; color: #94a3b8;
    display: flex; justify-content: space-between;
  }
  .footer strong { color: #475569; }

  @media print {
    .cover { border-radius: 0; }
    .content { padding: 18px 24px; }
  }
</style>
</head>
<body>
""")

# Cover page
html_parts.append("""
<div class="cover">
  <h1>L<span>aaS</span> Dashboard</h1>
  <div class="sub">Features, Capabilities &amp; Screenshots Guide</div>
  <div class="ver">Version 6.2 &nbsp;&middot;&nbsp; March 2026</div>
  <div class="meta">Wipro Limited &nbsp;&middot;&nbsp; SDX Infrastructure &amp; Data Centre Operations &nbsp;&middot;&nbsp; Confidential</div>

  <div class="toc">
    <h2>Contents</h2>
    <div class="toc-grid">
""")
for i, (_, title, _, _) in enumerate(SECTIONS, 1):
    badge = ' <span style="color:#93c5fd;font-size:9pt;">★ NEW</span>' if "NEW" in title else ""
    html_parts.append(f'      <div class="toc-item"><span class="toc-num">{i}</span> {title}{badge}</div>\n')
html_parts.append("""    </div>
  </div>
</div>
""")

# Section colours
SEC_COLORS = {
    "Login": ("#f0f9ff", "#0284c7"),
    "Overview": ("#eff6ff", "#1d4ed8"),
    "VMware": ("#eff6ff", "#2563eb"),
    "OpenShift": ("#fef2f2", "#dc2626"),
    "Nutanix": ("#f0fdf4", "#15803d"),
    "Ansible": ("#fff7ed", "#c2410c"),
    "Amazon": ("#fffbeb", "#b45309"),
    "Hyper-V": ("#eff6ff", "#0284c7"),
    "Active Directory": ("#f5f3ff", "#6d28d9"),
    "IPAM": ("#ecfeff", "#0e7490"),
    "Chargeback": ("#fdf2f8", "#be185d"),
    "Asset": ("#f5f3ff", "#7c3aed"),
    "VM Request": ("#fff7ed", "#ea580c"),
    "Insights": ("#eef2ff", "#4f46e5"),
    "Historical": ("#f0f9ff", "#0369a1"),
    "Capacity Forecasting": ("#ecfeff", "#0891b2"),
    "Audit": ("#f8fafc", "#475569"),
    "About": ("#eff6ff", "#1e40af"),
    "Support": ("#fef3c7", "#92400e"),
}

html_parts.append('<div class="content">\n')

for i, (img_file, title, desc, features) in enumerate(SECTIONS, 1):
    bg, fg = ("#f8fafc", "#334155")
    for key, (b, f) in SEC_COLORS.items():
        if key in title:
            bg, fg = b, f
            break

    is_new = "NEW" in title
    badge_html = '<span class="badge">NEW in v6.2</span>' if is_new else ""

    img_src = b64(img_file)

    html_parts.append(f'''
<div class="section">
  <div class="section-hdr" style="background:{bg}; color:{fg};">
    <span class="num">{i:02d}</span>
    <h2>{title}{badge_html}</h2>
  </div>
  <p class="desc">{desc}</p>
''')

    if img_src:
        html_parts.append(f'''  <div class="screenshot-wrap">
    <img src="{img_src}" alt="{title}"/>
    <div class="screenshot-label">📸 Screenshot: {title}</div>
  </div>
''')

    html_parts.append('  <div class="features-grid">\n')
    for feat in features:
        html_parts.append(f'    <div class="feat-item"><span class="ck">✓</span> {feat}</div>\n')
    html_parts.append('  </div>\n</div>\n')

# Contact section
html_parts.append("""
<div class="section contact-section">
  <div class="section-hdr" style="background:#fef3c7; color:#92400e;">
    <span class="num">📞</span>
    <h2>Contact Details</h2>
  </div>
  <p class="desc">For queries, access requests, demo bookings, or feedback, please contact the team below.</p>
  <div class="contact-grid">
    <div class="contact-card" style="background:#fffbeb; border:2px solid #f59e0b;">
      <div class="avatar">👑</div>
      <div class="name" style="color:#b45309;">Mayur Anilkumar Shah</div>
      <div class="role" style="color:#d97706;">Account Delivery Head (ADH)</div>
      <div class="email">✉️ <a href="mailto:mayur.shah@wipro.com">mayur.shah@wipro.com</a></div>
    </div>
    <div class="contact-card" style="background:#f5f3ff; border:2px solid #8b5cf6;">
      <div class="avatar">🏗️</div>
      <div class="name" style="color:#6d28d9;">Khalid Khan</div>
      <div class="role" style="color:#7c3aed;">Engineering Head</div>
      <div class="email">✉️ <a href="mailto:khalid.khan@wipro.com">khalid.khan@wipro.com</a></div>
    </div>
    <div class="contact-card" style="background:#ecfdf5; border:2px solid #06b6d4;">
      <div class="avatar">🖥️</div>
      <div class="name" style="color:#0e7490;">Sekhar Perumal</div>
      <div class="role" style="color:#0891b2;">Infrastructure Lead — DC &amp; VMware</div>
      <div class="email">✉️ <a href="mailto:sekhar.perumal@wipro.com">sekhar.perumal@wipro.com</a></div>
    </div>
  </div>
  <div style="padding:14px 18px; background:#f0f9ff; border:1px solid #bae6fd; border-radius:10px; font-size:10pt; color:#334155; line-height:1.7;">
    <strong>Distribution:</strong> This document is intended for the SDX Infrastructure &amp; DC team, project stakeholders, and management.<br/>
    <strong>Dashboard URL:</strong> <span style="color:#3b82f6; font-weight:600;">https://&lt;server-ip&gt;</span> (HTTPS, port 443)
  </div>
</div>
""")

html_parts.append('</div><!-- /content -->\n')

# Footer
html_parts.append("""
<div class="footer">
  <div><strong>LaaS Dashboard v6.2</strong> &nbsp;&middot;&nbsp; Wipro SDX INFRA &amp; DC Operations &nbsp;&middot;&nbsp; March 2026</div>
  <div>Confidential &nbsp;&middot;&nbsp; For Internal Use Only</div>
</div>
</body>
</html>
""")

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write("".join(html_parts))

size_mb = os.path.getsize(OUT_HTML) / (1024 * 1024)
print(f"HTML created: {OUT_HTML} ({size_mb:.1f} MB)")
