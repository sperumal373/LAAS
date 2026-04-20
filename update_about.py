"""
Update About LaaS modal:
1. Version v6.2 -> v6.3
2. Add CMDB to What's New
3. Add CMDB, IPAM PG, Storage Analytics, Backup Analytics to features
4. Update PORTAL_VOICEOVER to mention CMDB, IPAM PG, Backup & Storage Analytics
5. Add CMDB + Storage tiles to header OEM_LOGOS row
6. Add Storage Analytics / Backup Analytics to What's New
"""
import re

with open(r'C:\caas-dashboard\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

print(f"File length: {len(content)} chars")
changes = 0

# ─── 1. Version bump v6.2 -> v6.3 ──────────────────────────────
content = content.replace('LaaS Dashboard v6.2', 'LaaS Dashboard v6.3')
content = content.replace(">v6.2</span>", ">v6.3</span>")
changes += content.count('v6.3')
print(f"1. Version bumped to v6.3")

# ─── 2. Add CMDB, IPAM PostgreSQL, Backup & Storage Analytics to What's New ─
# Insert at the top of the What's New list (after the opening array bracket)
new_entries = '''{v:"v6.3",date:"Apr 2026",color:"#8b5cf6",icon:"\\u{1F5C4}\\uFE0F",title:"CMDB — Configuration Management Database",
                  items:["New CMDB page with ServiceNow-aligned CI classes and correlation IDs","Collects CIs from all eight platforms: VMware, Hyper-V, Nutanix, AWS, Storage, OpenShift, Physical Assets and IPAM","1800+ Configuration Items auto-discovered and stored in PostgreSQL","ServiceNow integration — push CIs to CMDB table API with dry-run mode","Inline CI editing for admins — update name, department, environment, serial number","Tab-based filtering by CI class: VMs, ESXi, Hyper-V, Nutanix, AWS, Storage, OCP, Physical, Networks","Full-text search across name, IP, OS, department, location and serial number","Correlation ID deduplication ensures no duplicate CIs across collections"]},
                {v:"v6.3",date:"Apr 2026",color:"#06b6d4",icon:"\\uD83D\\uDCE1",title:"IPAM Upgraded to PostgreSQL with Daily Collection",
                  items:["IPAM data migrated from SolarWinds polling to PostgreSQL daily snapshots","IPAM Overview page with subnet utilisation gauges, top subnets chart and site breakdown","Daily collector captures all VLANs and subnets with IP counts from PostgreSQL source","Faster page load — no more live SolarWinds API calls on every request","Historical IPAM utilisation tracked alongside all other platform metrics"]},
                {v:"v6.3",date:"Apr 2026",color:"#00AF51",icon:"\\uD83D\\uDEE1\\uFE0F",title:"Backup Analytics in Insights Engine",
                  items:["New Backup Analytics tab in Insights & Analytics page","Rubrik, Cohesity and Veeam job success/failure trends over time","Protected vs unprotected VM compliance tracking","SLA domain coverage and backup frequency metrics","Job duration and data transfer trends"]},
                {v:"v6.3",date:"Apr 2026",color:"#a855f7",icon:"\\uD83D\\uDDC4\\uFE0F",title:"Storage Analytics in Insights Engine",
                  items:["New Storage Analytics tab in Insights & Analytics page","Pure, Dell, HPE and NetApp array capacity trends","Volume and LUN growth tracking over thirty-day windows","Storage exhaustion predictions using linear regression","Per-array and per-vendor capacity breakdown charts"]},
                '''

old_whats_new_start = 'Recent additions and improvements to the LaaS Dashboard — v6.2, March 2026'
new_whats_new_start = 'Recent additions and improvements to the LaaS Dashboard — v6.3, April 2026'
content = content.replace(old_whats_new_start, new_whats_new_start)

# Find the start of the What's New items array
marker = '              {[\n'
# We need to find the one right after "whats_new" tab content
wn_idx = content.find('tab==="whats_new"')
if wn_idx == -1:
    print("ERROR: Could not find whats_new tab")
else:
    # Find the array of entries after the marker text
    arr_start = content.find('{v:"v6.2"', wn_idx)
    if arr_start == -1:
        arr_start = content.find("{v:\"v6.", wn_idx)
    if arr_start > 0:
        content = content[:arr_start] + new_entries + content[arr_start:]
        print("2. Added CMDB, IPAM PG, Backup/Storage Analytics to What's New")
    else:
        print("ERROR: Could not find What's New array entries")

# ─── 3. Add CMDB and IPAM PG platform cards to "What is LaaS" tab ──────────
# Find the grid after "What is LaaS" tab
old_ipam_card = '{icon:"\\uD83D\\uDCE1",color:"#06b6d4",title:"IPAM (SolarWinds)",desc:"IP Address Management — subnet grid, utilization tracking, IP search, and overview integration."}'
new_ipam_card = '{icon:"\\uD83D\\uDCE1",color:"#06b6d4",title:"IPAM (PostgreSQL)",desc:"IP Address Management with daily PostgreSQL snapshots — subnet grid, utilisation gauges, IP search, top subnets chart and historical tracking."}'
if old_ipam_card in content:
    content = content.replace(old_ipam_card, new_ipam_card)
    print("3a. Updated IPAM card from SolarWinds to PostgreSQL")
else:
    print("3a. WARN: IPAM card text not found for update")

# Add CMDB card after Asset Inventory card
old_asset_card = '{icon:"\\uD83C\\uDFF7\\uFE0F",color:"#14b8a6",title:"Asset Inventory",desc:"Physical and logical asset tracking with search, filters, inline editing and CSV export."}'
new_asset_card_block = old_asset_card + ',\n                  {icon:"\\uD83D\\uDDC4\\uFE0F",color:"#8b5cf6",title:"CMDB",desc:"Configuration Management Database with 1800+ auto-discovered CIs from all platforms. ServiceNow-aligned CI classes, correlation-based dedup and one-click push to ServiceNow CMDB table API."}'
if old_asset_card in content:
    content = content.replace(old_asset_card, new_asset_card_block)
    print("3b. Added CMDB card to What is LaaS")
else:
    print("3b. WARN: Asset Inventory card not found for CMDB injection")

# ─── 4. Add CMDB feature card to Features tab ──────────────────
# Add after the last Platform-Wide capability entry (before the final .map)
# Find the Insights entry in features and add CMDB after backup cards
old_insights_feature = '{icon:"\\uD83D\\uDD0D",title:"Universal Global Search"'
# Actually let's add a CMDB section after the Platform-Wide section
# Find "Platform-Wide Capabilities" section and add CMDB FeatCards
old_platform_header = 'label="Platform-Wide Capabilities" color="#94a3b8"/>'
new_platform_header = 'label="Platform-Wide Capabilities" color="#94a3b8"/>\n              {[{icon:"\\uD83D\\uDDC4\\uFE0F",title:"CMDB — Configuration Management Database",color:"#8b5cf6",points:["ServiceNow-aligned CI classes: vm_instance, esx_server, win_server, nutanix_node, ec2_instance, storage_device, ocp_cluster, ocp_node, ip_network, server","Auto-discovers 1800+ CIs from VMware, Hyper-V, Nutanix, AWS, Storage, OpenShift, Physical Assets and IPAM","Correlation ID deduplication prevents duplicate CIs across repeated collections","One-click push to ServiceNow CMDB Table API with dry-run preview","Inline CI editing for admins — name, department, environment, serial number","Tab-based filtering and full-text search across all CI fields","Daily collection via automated scheduler integrated with the Insights engine","Export-ready CI registry for IT asset compliance and auditing"]}].map((f,i)=><FeatCard key={"cmdb"+i} {...f}/>)}'
if old_platform_header in content:
    content = content.replace(old_platform_header, new_platform_header, 1)
    print("4. Added CMDB feature card to Features tab")
else:
    print("4. WARN: Platform-Wide header not found")

# ─── 5. Update the Insights description to mention Backup & Storage Analytics ─
old_insights_desc = '"Health Scorecard, Change Detection, Capacity & Cost forecasting and Executive Summary — all powered by PostgreSQL daily snapshots across eight platforms."'
new_insights_desc = '"Health Scorecard, Change Detection, Capacity & Cost forecasting, Executive Summary, Backup Analytics and Storage Analytics — all powered by PostgreSQL daily snapshots across eight platforms."'
content = content.replace(old_insights_desc, new_insights_desc)
print("5. Updated Insights description to mention Backup & Storage Analytics")

# ─── 6. Update version in footer ────────────────────────────────
content = content.replace("LaaS Dashboard v6.2", "LaaS Dashboard v6.3")
print("6. Footer version updated")

# ─── 7. Update PORTAL_VOICEOVER ─────────────────────────────────
old_voiceover_end = """Supporting services include Active Directory and DNS management via LDAP, SolarWinds IPAM for subnet and IP tracking, a VM request and approval workflow for self-service provisioning, and a chargeback engine that calculates monthly costs per project across all three virtualisation platforms.
The portal includes a Universal Search that finds VMs, hosts, OCP clusters, Nutanix PCs, Ansible jobs, alerts, and team contacts instantly. There is also an AI Assistant for natural-language infrastructure queries.
Access is controlled by four roles — Admin, Operator, Viewer, and Requester — with a full audit log of every action. This portal replaces over six separate management consoles, reducing access risk, improving governance, and accelerating operations across the entire Wipro lab environment."""

new_voiceover_end = """New in version six point three is the CMDB module — a Configuration Management Database that auto-discovers over eighteen hundred Configuration Items from all eight platforms. CIs are aligned with ServiceNow CMDB classes and can be pushed directly to ServiceNow via the Table API. Admins can edit CI metadata inline and use tab-based filtering and full-text search across the entire registry.
Also in version six point three, IPAM has been upgraded from live SolarWinds polling to PostgreSQL daily snapshots, delivering faster page loads and historical utilisation tracking. The Insights and Analytics engine now includes two new tabs — Backup Analytics showing Rubrik, Cohesity and Veeam job trends, and Storage Analytics showing array capacity trends across Pure, Dell, HPE and NetApp with exhaustion predictions.
Supporting services include Active Directory and DNS management via LDAP, IPAM for subnet and IP tracking, a VM request and approval workflow for self-service provisioning, and a chargeback engine that calculates monthly costs per project across all three virtualisation platforms.
The portal includes a Universal Search that finds VMs, hosts, OCP clusters, Nutanix PCs, Ansible jobs, alerts, and team contacts instantly. There is also an AI Assistant for natural-language infrastructure queries.
Access is controlled by four roles — Admin, Operator, Viewer, and Requester — with a full audit log of every action. This portal replaces over six separate management consoles, reducing access risk, improving governance, and accelerating operations across the entire Wipro lab environment."""

if old_voiceover_end in content:
    content = content.replace(old_voiceover_end, new_voiceover_end)
    print("7. Updated PORTAL_VOICEOVER with CMDB, IPAM PG, Backup & Storage Analytics")
else:
    print("7. WARN: Could not find voiceover end text for update")

# Also update "six enterprise platforms" to mention eight
content = content.replace(
    "brings together six enterprise platforms",
    "brings together eight enterprise platforms plus supporting services"
)

# ─── 8. Update OEM logos to add Storage + CMDB tiles in header ────────────
# In the About header, after the Assets tile, add a CMDB tile
old_assets_tile_end = """<span style={{fontSize:13,fontWeight:700,color:"rgba(255,255,255,.75)",letterSpacing:".1px"}}>Assets</span>
                  </div>
            </div>"""
new_assets_tile_end = """<span style={{fontSize:13,fontWeight:700,color:"rgba(255,255,255,.75)",letterSpacing:".1px"}}>Assets</span>
                  </div>
              {/* CMDB tile */}
              <div title="CMDB — Configuration Management Database" style={{display:"flex",flexDirection:"column",
                alignItems:"center",gap:3,background:"rgba(0,0,0,.35)",
                border:"1px solid #8b5cf640",borderRadius:9,padding:"5px 8px",minWidth:56}}>
                    <div style={{width:28,height:28,borderRadius:5,background:"#8b5cf620",
                      display:"flex",alignItems:"center",justifyContent:"center",fontSize:20}}>\\uD83D\\uDDC4\\uFE0F</div>
                    <span style={{fontSize:13,fontWeight:700,color:"rgba(255,255,255,.75)",letterSpacing:".1px"}}>CMDB</span>
                  </div>
            </div>"""
if old_assets_tile_end in content:
    content = content.replace(old_assets_tile_end, new_assets_tile_end)
    print("8. Added CMDB tile to About header")
else:
    print("8. WARN: Assets tile end not found for CMDB tile injection")

# ─── Write ──────────────────────────────────────────────────────
with open(r'C:\caas-dashboard\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nDone! All About LaaS updates applied.")
