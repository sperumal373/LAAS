with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")

# Fix all tab key mismatches in loadData
fixes = [
    ('tab==="dashboard"', 'tab==="dash"'),
    ('tab==="alerts"', 'tab==="alerts"'),   # already correct
]

# Replace the entire loadData body with corrected tab keys
OLD = (
    '      if(tab==="dashboard"){setLoadMsg("Loading...");'
)
NEW = (
    '      if(tab==="dash"){setLoadMsg("Loading...");'
)
t = t.replace(OLD, NEW, 1)

# Also add ops, sites, audit handlers before the closing }finally
OLD2 = '      else if(tab==="events"){setLoadMsg("Loading...");setEvents(await fetchZertoEvents(selSite.id)||[]);setAuditLog(await fetchZertoAuditLog(selSite.id)||[]);}\n    }finally'
NEW2 = '      else if(tab==="events"){setLoadMsg("Loading...");setEvents(await fetchZertoEvents(selSite.id)||[]);}\n      else if(tab==="audit"){setLoadMsg("Loading audit...");setAuditLog(await fetchZertoAuditLog(selSite.id)||[]);}\n      else if(tab==="ops"){setLoadMsg("Loading tasks...");setTasks(await fetchZertoTasks(selSite.id)||[]);}\n      else if(tab==="sites"){setLoadMsg("Loading sites...");const d=await fetchZertoDashboard(selSite.id);setDash(d);}\n    }finally'
t = t.replace(OLD2, NEW2, 1)

print("dash fix:", 'tab==="dash"' in t)
print("dashboard remaining:", 'tab==="dashboard"' in t)
print("audit handler:", 'tab==="audit"' in t)
print("ops handler:", 'tab==="ops"' in t)

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(t.encode("utf-8-sig"))
print("Done")