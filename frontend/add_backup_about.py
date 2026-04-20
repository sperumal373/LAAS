"""Add Backup & Data Protection section to About LaaS Features tab + voiceover."""

fpath = r"C:\caas-dashboard\frontend\src\App.jsx"
with open(fpath, "r", encoding="utf-8") as f:
    src = f.read()

# ─── 1. Add Backup platform header + feature cards in the Features tab ───
# Insert BEFORE the last ].map((f,i)=><FeatCard...) that closes the general features section
# Find the "Themes, Charts & Audit" card which is the last one before the closing
marker = '"Exportable audit data for compliance"]},'
idx = src.find(marker)
if idx == -1:
    print("ERROR: Cannot find features insertion marker")
else:
    insert_pos = idx + len(marker)
    backup_features = """

              {icon:"💾",title:"Backup & Data Protection",color:"#00AF51",points:["Rubrik Security Cloud, Cohesity DataProtect and Veeam Backup & Replication","SLA domain management with assign, unassign and pause actions","On-demand snapshot and bulk snapshot for multiple VMs","Live mount, instant recovery and file-level restore from Rubrik","Job execution monitoring with retry, cancel and status tracking","Cluster capacity, node health and storage runway visibility","Protected vs unprotected VM counts and compliance status","Automated job scheduling with success, failure and warning alerts"]},
              {icon:"🛡️",title:"Rubrik Security Cloud",color:"#00AF51",points:["Multi-cluster Rubrik CDM connectivity with API token authentication","SLA domains with VM counts, snapshot frequency and retention details","On-demand snapshot and bulk snapshot across multiple VMs","Live mount VMs directly from backup for instant testing","Export VM to vCenter and instant recovery with custom settings","File-level recovery — browse and download individual files","Pause, resume and delete SLA assignments","Job monitoring with retry failed jobs and real-time status"]},
              {icon:"🔵",title:"Cohesity DataProtect",color:"#0072CE",points:["Connect to Cohesity clusters with API key authentication","Protection jobs with run, cancel, pause and resume controls","Protected sources and object-level snapshot browsing","Alert management with resolve and acknowledge actions","Storage capacity, deduplication ratio and data reduction stats","Job run history with success, failure and SLA violation tracking","Clone and recover VMs from any protection run","Search protected objects across all connected clusters"]},
              {icon:"🟢",title:"Veeam Backup & Replication",color:"#00B336",points:["Connect to Veeam Backup servers via Enterprise Manager REST API","Backup jobs with start, stop, enable and disable controls","Job session history with retry and stop session actions","Instant recovery to VMware, Hyper-V or cloud targets","Repository capacity monitoring with free space alerts","Protected VM inventory with last backup status and RPO tracking","Session-level log viewing for troubleshooting","Managed server and proxy infrastructure visibility"]},"""

    src = src[:insert_pos] + backup_features + src[insert_pos:]
    print(f"OK: Inserted Backup feature cards at position {insert_pos}")

# ─── 2. Enhance Backup paragraph in PORTAL_VOICEOVER ───
old_backup_voice = "Backup visibility is provided through Rubrik Security Cloud and Cohesity DataProtect. Every SLA domain, protected and unprotected workload, backup job status, and cluster capacity is surfaced without opening a backup console."

new_backup_voice = """Backup and Data Protection is a major capability of the LaaS Portal, integrating three enterprise platforms: Rubrik Security Cloud, Cohesity DataProtect, and Veeam Backup and Replication. For Rubrik, you get full SLA domain management — assign, unassign, and pause SLA policies. On-demand and bulk snapshots can be triggered for multiple VMs at once. Recovery options include live mount for instant VM testing, export to vCenter, instant recovery, and file-level restore where you can browse and download individual files. Job monitoring shows real-time status with retry for failed jobs. For Cohesity, protection jobs can be run, cancelled, paused, or resumed. You can browse object-level snapshots, manage alerts, and view storage capacity with deduplication stats. For Veeam, backup jobs can be started, stopped, enabled, or disabled. Session history with retry, instant recovery to VMware, Hyper-V, or cloud, and repository capacity monitoring are all available. Across all three platforms, protected versus unprotected VM counts and compliance status are visible at a glance — no need to open any backup console."""

if old_backup_voice in src:
    src = src.replace(old_backup_voice, new_backup_voice, 1)
    print("OK: Updated Backup voiceover paragraph")
else:
    print("WARNING: Could not find old backup voiceover text")

with open(fpath, "w", encoding="utf-8", newline="") as f:
    f.write(src)
print("DONE — file written.")
