with open("C:/caas-dashboard/frontend/src/CISHardening.jsx","rb") as f: t=f.read().decode("utf-8-sig")

# Read the new components
with open("C:/caas-dashboard/frontend/_new_cis_comps.txt","rb") as f: new_comps=f.read().decode("utf-8-sig")

# Insert new components before CIS_TABS definition
marker = "const CIS_TABS = ["
idx = t.find(marker)
if idx < 0:
    print("ERROR: CIS_TABS not found")
else:
    t = t[:idx] + new_comps + "\n" + t[idx:]
    print("Inserted components at index", idx)

# Update CIS_TABS to include new tabs
old_tabs = """const CIS_TABS = [
  { id: "dashboard", label: "\\ud83d\\udcca Dashboard" },
  { id: "vmlist",    label: "\\ud83d\\udda5\\ufe0f VM List" },
  { id: "exclusions",label: "\\u229a Exclusions" },
  { id: "remlog",    label: "\\ud83d\\udccb Remediation Log" },
  { id: "reports",   label: "\\ud83d\\udcc4 Reports" },
];"""

new_tabs = """const CIS_TABS = [
  { id: "dashboard",  label: "\\ud83d\\udcca Dashboard" },
  { id: "osgroups",   label: "\\ud83d\\udda5\\ufe0f OS Groups" },
  { id: "vmlist",     label: "\\ud83d\\udcdd VM List" },
  { id: "scanhistory",label: "\\ud83d\\uddc2\\ufe0f Scan History" },
  { id: "baselines",  label: "\\ud83d\\udcda Baselines" },
  { id: "exclusions", label: "\\u229a Exclusions" },
  { id: "remlog",     label: "\\ud83d\\udccb Remediation Log" },
  { id: "reports",    label: "\\ud83d\\udcc4 Reports" },
];"""

if "osgroups" not in t:
    # Find the const CIS_TABS block and replace
    import re
    t = re.sub(r'const CIS_TABS = \[[\s\S]*?\];', new_tabs, t, count=1)
    if "osgroups" in t:
        print("Updated CIS_TABS")
    else:
        print("WARNING: CIS_TABS update failed")
else:
    print("CIS_TABS already has osgroups")

# Update the content rendering to include new tabs
old_render = """        {tab === "dashboard"  && <CISDashboard onViewVM={handleViewVM} />}
        {tab === "vmlist"     && <CISVMList onSelectVM={handleViewVM} />}
        {tab === "vmdetail"   && selVM && <CISVMDetail vm={selVM} onBack={handleBack} />}
        {tab === "exclusions" && <CISExclusions />}
        {tab === "remlog"     && <CISRemLog />}
        {tab === "reports"    && <CISReports />}"""

new_render = """        {tab === "dashboard"   && <CISDashboard onViewVM={handleViewVM} />}
        {tab === "osgroups"    && <CISOsGroups onViewVM={handleViewVM} />}
        {tab === "vmlist"      && <CISVMList onSelectVM={handleViewVM} />}
        {tab === "scanhistory" && <CISScanHistory />}
        {tab === "baselines"   && <CISBaselines />}
        {tab === "vmdetail"    && selVM && <CISVMDetail vm={selVM} onBack={handleBack} />}
        {tab === "exclusions"  && <CISExclusions />}
        {tab === "remlog"      && <CISRemLog />}
        {tab === "reports"     && <CISReports />}"""

if old_render in t:
    t = t.replace(old_render, new_render, 1)
    print("Updated render block")
else:
    print("WARNING: render block not found, trying partial match")
    if 'tab === "osgroups"' not in t:
        # Try to find and patch
        idx2 = t.find('{tab === "dashboard"')
        if idx2 > 0:
            end = t.find("</div>", idx2)
            print(f"Found render at {idx2}, end at {end}")
            print(repr(t[idx2:idx2+500]))

with open("C:/caas-dashboard/frontend/src/CISHardening.jsx","wb") as f: f.write(t.encode("utf-8"))
print("Done. File size:", len(t))
