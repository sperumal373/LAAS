with open("C:/caas-dashboard/frontend/src/CISHardening.jsx","rb") as f: t=f.read().decode("utf-8")

# Update CIS_TABS using string find/replace, not regex
import re

# Find and replace CIS_TABS block
tabs_start = t.find("const CIS_TABS = [")
tabs_end = t.find("];", tabs_start) + 2
old_tabs_block = t[tabs_start:tabs_end]
print("Old tabs block found:", len(old_tabs_block), "chars")

new_tabs_block = '''const CIS_TABS = [
  { id: "dashboard",   label: "\U0001F4CA Dashboard" },
  { id: "osgroups",    label: "\U0001F5A5\uFE0F OS Groups" },
  { id: "vmlist",      label: "\U0001F4DD VM List" },
  { id: "scanhistory", label: "\U0001F5C2\uFE0F Scan History" },
  { id: "baselines",   label: "\U0001F4DA Baselines" },
  { id: "exclusions",  label: "\u229A Exclusions" },
  { id: "remlog",      label: "\U0001F4CB Remediation Log" },
  { id: "reports",     label: "\U0001F4C4 Reports" },
];'''

t = t[:tabs_start] + new_tabs_block + t[tabs_end:]
print("Updated CIS_TABS")

# Update render block
old_r = '{tab === "dashboard"  && <CISDashboard onViewVM={handleViewVM} />}'
new_r = '''{tab === "dashboard"   && <CISDashboard onViewVM={handleViewVM} />}
        {tab === "osgroups"    && <CISOsGroups onViewVM={handleViewVM} />}
        {tab === "vmlist"      && <CISVMList onSelectVM={handleViewVM} />}
        {tab === "scanhistory" && <CISScanHistory />}
        {tab === "baselines"   && <CISBaselines />}'''

if old_r in t:
    t = t.replace(old_r, new_r, 1)
    # Remove the old vmlist line (it was below dashboard)
    t = t.replace('\n        {tab === "vmlist"     && <CISVMList onSelectVM={handleViewVM} />}', "", 1)
    print("Updated render block")
else:
    print("render block not found, looking...")
    idx = t.find('tab === "dashboard"')
    print(repr(t[idx:idx+300]))

with open("C:/caas-dashboard/frontend/src/CISHardening.jsx","wb") as f: f.write(t.encode("utf-8"))
print("Done. Lines:", t.count("\n"))
