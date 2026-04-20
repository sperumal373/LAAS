"""fix_ipam_route.py – Remove extra } from IPAM route in App.jsx"""
APP = r"c:\caas-dashboard\frontend\src\App.jsx"
content = open(APP, encoding="utf-8").read()

# Find the IPAM route line with double brace at end
old = (
    '{page==="ipam"      &&<PageErrorBoundary page="IPAM"><Suspense fallback='
    '{<div style={{padding:48,textAlign:"center",color:"#64748b",fontSize:18}}>⏳ Loading IPAM\u2026</div>}>'
    '<IPAMPage currentUser={currentUser} p={p}/></Suspense></PageErrorBoundary>}}'
)
new = (
    '{page==="ipam"      &&<PageErrorBoundary page="IPAM"><Suspense fallback='
    '{<div style={{padding:48,textAlign:"center",color:"#64748b",fontSize:18}}>⏳ Loading IPAM\u2026</div>}>'
    '<IPAMPage currentUser={currentUser} p={p}/></Suspense></PageErrorBoundary>}'
)

if old in content:
    content = content.replace(old, new, 1)
    open(APP, "w", encoding="utf-8").write(content)
    print("FIXED double brace on IPAM route")
else:
    # Try to find it
    idx = content.find('page==="ipam"')
    print("Not found with exact string, showing context:")
    print(repr(content[idx:idx+300]))
