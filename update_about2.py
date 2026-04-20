"""Fix remaining About LaaS items that failed due to emoji encoding."""
with open(r'C:\caas-dashboard\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# ─── Fix 3a: Update IPAM card from SolarWinds to PostgreSQL ─────
old = 'title:"IPAM (SolarWinds)",desc:"IP Address Management \u2014 subnet grid, utilization tracking, IP search, and overview integration."'
new = 'title:"IPAM (PostgreSQL)",desc:"IP Address Management with daily PostgreSQL snapshots \u2014 subnet grid, utilisation gauges, IP search, top subnets chart and historical tracking."'
if old in content:
    content = content.replace(old, new)
    changes += 1
    print("3a. Fixed IPAM card to PostgreSQL")
else:
    print("3a. WARN: Still can't find IPAM card")

# ─── Fix 3b: Add CMDB card after Asset Inventory card ───────────
old = 'title:"Asset Inventory",desc:"Physical and logical asset tracking with search, filters, inline editing and CSV export."'
new_block = 'title:"Asset Inventory",desc:"Physical and logical asset tracking with search, filters, inline editing and CSV export."},\n                  {icon:"\U0001F5C4\uFE0F",color:"#8b5cf6",title:"CMDB",desc:"Configuration Management Database with 1800+ auto-discovered CIs from all platforms. ServiceNow-aligned CI classes, correlation-based dedup and one-click push to ServiceNow CMDB Table API."'
if old in content:
    content = content.replace(old, new_block, 1)
    changes += 1
    print("3b. Added CMDB card to What is LaaS")
else:
    print("3b. WARN: Still can't find Asset Inventory card")

# ─── Fix 7: Update PORTAL_VOICEOVER ─────────────────────────────
# Use a substring that's definitely in the voiceover
old_vo = 'Supporting services include Active Directory and DNS management via LDAP, SolarWinds IPAM for subnet and IP tracking'
new_vo = 'New in version six point three is the CMDB module \u2014 a Configuration Management Database that auto-discovers over eighteen hundred Configuration Items from all eight platforms. CIs are aligned with ServiceNow CMDB classes and can be pushed directly to ServiceNow via the Table API. Admins can edit CI metadata inline and use tab-based filtering and full-text search across the entire registry.\nAlso in version six point three, IPAM has been upgraded from live SolarWinds polling to PostgreSQL daily snapshots, delivering faster page loads and historical utilisation tracking. The Insights and Analytics engine now includes two new tabs \u2014 Backup Analytics showing Rubrik, Cohesity and Veeam job trends, and Storage Analytics showing array capacity trends across Pure, Dell, HPE and NetApp with exhaustion predictions.\nSupporting services include Active Directory and DNS management via LDAP, PostgreSQL-backed IPAM for subnet and IP tracking'
if old_vo in content:
    content = content.replace(old_vo, new_vo)
    changes += 1
    print("7. Updated PORTAL_VOICEOVER with CMDB, IPAM PG, Backup & Storage Analytics")
else:
    print("7. WARN: Can't find voiceover substring")

# ─── Fix: Also update the old What's New IPAM entry (v5.8) ──────
old_ipam_wn = 'IPAM page: subnet grid, utilization bars, IP search, SolarWinds integration'
new_ipam_wn = 'IPAM page: subnet grid, utilisation bars, IP search, PostgreSQL-backed daily snapshots'
if old_ipam_wn in content:
    content = content.replace(old_ipam_wn, new_ipam_wn)
    changes += 1
    print("Extra: Updated v5.8 What's New IPAM reference")

# ─── Fix: Update HowTo step 2 to mention CMDB ──────────────────
old_howto = 'IPAM, Assets, Chargeback, or VM Requests'
new_howto = 'IPAM, CMDB, Assets, Chargeback, or VM Requests'
if old_howto in content:
    content = content.replace(old_howto, new_howto)
    changes += 1
    print("Extra: Added CMDB to HowTo step 2")

# ─── Write ──────────────────────────────────────────────────────
with open(r'C:\caas-dashboard\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nDone! {changes} additional fixes applied.")
