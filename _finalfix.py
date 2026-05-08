import sys
sys.stdout.reconfigure(encoding="utf-8")

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")

# 1. Remove duplicate OperationProgressDrawer - keep the LAST one
first = t.find("  const OperationProgressDrawer=()=>{")
second = t.find("  const OperationProgressDrawer=()=>{", first+1)
if second > 0:
    # Find end of first occurrence
    end_first = t.find("\n  };\n", first) + len("\n  };\n")
    t = t[:first] + t[end_first:]
    print("Removed duplicate OperationProgressDrawer")
else:
    print("No duplicate found")

# 2. Replace AuditTab with a simple inline component (not defined)
# Change tab render to skip AuditTab or define it
AUDIT_REF = '{tab==="audit"&&<AuditTab/>}'
AUDIT_INLINE = """{tab==="audit"&&(<div style={{overflowX:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}><thead><tr>{["Time","User","Action","Entity","Result","Details"].map(h=>(<th key={h} style={{padding:"8px 10px",borderBottom:"1px solid "+s.border,color:s.textMute,fontWeight:700,textAlign:"left",textTransform:"uppercase",fontSize:10,letterSpacing:".5px"}}>{h}</th>))}</tr></thead><tbody>{(auditLog||[]).map((a,i)=>(<tr key={i} style={{borderBottom:"1px solid "+s.border+"30"}}><td style={{padding:"7px 10px",color:s.textMute,whiteSpace:"nowrap"}}>{a.timestamp?(new Date(a.timestamp).toLocaleString()):""}</td><td style={{padding:"7px 10px",color:s.text}}>{a.user||a.initiated_by||""}</td><td style={{padding:"7px 10px",color:s.cyan,fontWeight:600}}>{a.action||""}</td><td style={{padding:"7px 10px",color:s.text}}>{a.entity||a.vpg_name||""}</td><td style={{padding:"7px 10px"}}><span style={{color:a.result==="Success"?s.green:s.red,fontWeight:600}}>{a.result||""}</span></td><td style={{padding:"7px 10px",color:s.textMute,maxWidth:200,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{a.details||""}</td></tr>))}{!auditLog?.length&&<tr><td colSpan={6} style={{padding:24,textAlign:"center",color:s.textMute}}>No audit records</td></tr>}</tbody></table></div>)}"""
t = t.replace(AUDIT_REF, AUDIT_INLINE)
print("AuditTab replaced:", AUDIT_REF not in t)

# 3. Fix initial tab state: "dashboard" -> "dash"
t = t.replace('const[tab,setTab]=useState("dashboard");', 'const[tab,setTab]=useState("dash");')

# 4. Fix tab nav - add Audit tab (if missing from nav)
# Already present in the MAIN_RETURN

# Check final state
import re
comps = re.findall(r"const (\w+Tab|\w+Modal|\w+Drawer)=", t)
print("Components:", comps)
dups = [c for c in set(comps) if comps.count(c)>1]
print("Duplicates:", dups)

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(t.encode("utf-8-sig"))
print("Done. Size:", len(t))