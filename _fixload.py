with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")

# 1. Fix DashboardTab to show "Loading..." while loading, not "Select a site"
t = t.replace(
    'const DashboardTab=()=>{if(!dash)return<div style={{color:s.textMute,padding:40,textAlign:"center"}}>{loading?"Loading...":"Select a site"}</div>;',
    'const DashboardTab=()=>{if(loading)return<div style={{color:s.textMute,padding:40,textAlign:"center"}}>Loading dashboard...</div>;if(!dash)return<div style={{color:s.textMute,padding:40,textAlign:"center"}}>No data  click Refresh</div>;',
    1
)

# 2. Fix loadSites to call loadData after setting the site
# Replace: if(!selSite&&d&&d.length)setSelSite(d[0]);
# With: if(!selSite&&d&&d.length){setSelSite(d[0]);}
# (The useEffect chain handles this automatically - no change needed there)

# 3. The main return had: {!loading&&selSite&&(<div>
# This hides the tabs while loading - change to always show tabs when site selected
t = t.replace(
    "    {!loading&&selSite&&(<div>",
    "    {selSite&&(<div>"
)

# 4. Remove the loading guard at top level so tabs always show when site selected
t = t.replace(
    "    {loading&&<div style={{textAlign:\"center\",padding:32,color:s.textMute,fontSize:13}}>{loadMsg||\"Loading...\"}</div>}\n    {selSite&&(<div>",
    "    {selSite&&(<div>"
)

print("DashboardTab fix:", 'Loading dashboard...' in t)
print("Tabs always visible:", '{selSite&&(<div>' in t)

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(t.encode("utf-8-sig"))
print("Done")