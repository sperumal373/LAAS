"""Replace the IPAM overview block in App.jsx with a Postgres-IPAM version"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

path = r'c:\caas-dashboard\frontend\src\App.jsx'
content = open(path, encoding='utf-8').read()

# --- 1. Fix the useEffect to use fetchIPAM2Summary ---
old_fetch = "fetchIPAMSubnets().then(d=>setOvIpam(d)).catch(()=>setOvIpam(null));"
new_fetch = "fetchIPAM2Summary().then(d=>setOvIpam(d)).catch(()=>setOvIpam(null));"
if old_fetch in content:
    content = content.replace(old_fetch, new_fetch, 1)
    print("✓ Replaced fetchIPAMSubnets with fetchIPAM2Summary")
else:
    print("⚠ fetchIPAMSubnets not found (may already be replaced)")

# --- 2. Replace the whole IPAM overview section ---
# Find it by its unique anchor comment
start_marker = "{/* ────── IPAM OVERVIEW ────── */}"
# Find the end by looking for the closing of the IPAM div, which ends before "// ─── VMs"
# We'll find start and the section closing

start_idx = content.find(start_marker)
if start_idx == -1:
    print("⚠ IPAM OVERVIEW marker not found")
else:
    # Find the two closing </div> tags that wrap the whole section
    # The section is: <div> ... </div>\n    </div>\n  );\n}
    # We need to find the end of this section — look for the next component after it
    end_marker = "// ─── VMs ───"
    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        print("⚠ End marker not found")
    else:
        # Walk back to find the closing of the wrapping div before the VMs comment
        # The section ends with:   </div>\n  );\n}\n\n// ─── VMs
        # Find the last "})" or "}\n\n" before end_marker
        chunk = content[start_idx:end_idx]
        # Find the last closing of the outer div wrapper
        # The section ends with:  </div>\n    </div>\n  );\n}
        # We want to replace from start_marker to the end of the )} block
        # Let's find "  );\n}" which ends the Overview function just before VMs comment
        close_overview = content.rfind("  );\n}", start_idx, end_idx)
        if close_overview == -1:
            close_overview = content.rfind(");", start_idx, end_idx)
        
        # The replacement section (from start_marker up to and including "  );\n}")
        old_section = content[start_idx:close_overview + len("  );\n}")]
        
        new_section = """{/* ────── IPAM OVERVIEW ────── */}
      <div>
        <div style={{display:"flex",alignItems:"center",gap:10,padding:"6px 0 10px",borderBottom:`2px solid #06b6d420`,marginBottom:14}}>
          <div style={{width:26,height:26,borderRadius:7,background:"linear-gradient(135deg,#06b6d420,#06b6d408)",border:"1px solid #06b6d430",display:"flex",alignItems:"center",justifyContent:"center",fontSize:17}}>🌐</div>
          <div>
            <div style={{fontWeight:900,fontSize:16,letterSpacing:"1.8px",textTransform:"uppercase",color:"#06b6d4"}}>IPAM</div>
            <div style={{fontSize:13,color:p.textMute,marginTop:1}}>IP Address Management · Self-hosted PostgreSQL</div>
          </div>
          <div style={{flex:1}}/>
          {ovIpam&&(
            <span style={{fontSize:13,color:p.textMute,fontWeight:600}}>
              {ovIpam.total_vlans||0} VLANs · {(ovIpam.total_ips||0).toLocaleString()} IPs · <span style={{color:(ovIpam.used_ips||0)/(ovIpam.total_ips||1)*100>=80?"#ef4444":(ovIpam.used_ips||0)/(ovIpam.total_ips||1)*100>=60?"#f59e0b":"#10b981",fontWeight:700}}>{ovIpam.total_ips>0?Math.round((ovIpam.used_ips||0)/ovIpam.total_ips*100):0}% used</span>
            </span>
          )}
        </div>
        {!ovIpam?(
          <div style={{textAlign:"center",padding:"18px 20px",background:p.panelAlt,border:`1px dashed #06b6d428`,borderRadius:10,color:p.textMute,fontSize:14,display:"flex",alignItems:"center",justifyContent:"center",gap:8}}>
            <span style={{fontSize:20}}>⏳</span>Loading IPAM data…
          </div>
        ):(
          <>
            <div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:10,marginBottom:14}}>
              {[
                {icon:"🗂",label:"VLANs",       value:ovIpam.total_vlans||0,                                    color:"#06b6d4"},
                {icon:"🌐",label:"Total IPs",   value:(ovIpam.total_ips||0).toLocaleString(),                   color:"#3b82f6"},
                {icon:"🟡",label:"Used",        value:(ovIpam.used_ips||0).toLocaleString(),                    color:"#f59e0b"},
                {icon:"🟢",label:"Free",        value:((ovIpam.free_ips||ovIpam.available_ips)||0).toLocaleString(), color:"#10b981"},
                {icon:"🔒",label:"Reserved",    value:(ovIpam.reserved_ips||0).toLocaleString(),                color:"#a855f7"},
                {icon:"📶",label:"Ping Up",     value:(ovIpam.up_ips||0).toLocaleString(),                     color:"#22c55e"},
              ].map(k=>(<KPI key={k.label} icon={k.icon} label={k.label} value={k.value} color={k.color}/>))}
            </div>
            {ovIpam.total_ips>0&&(()=>{
              const pct=Math.round((ovIpam.used_ips||0)/ovIpam.total_ips*100);
              const bc=pct>=80?"#ef4444":pct>=60?"#f59e0b":"#10b981";
              return(
                <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:10,padding:"14px 18px"}}>
                  <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:8}}>
                    <span style={{fontSize:14,fontWeight:700,color:p.text}}>Overall IP Utilisation</span>
                    <span style={{fontSize:16,fontWeight:800,color:bc}}>{pct}%</span>
                  </div>
                  <div style={{height:8,borderRadius:4,background:p.panelAlt,overflow:"hidden"}}>
                    <div style={{height:"100%",width:`${pct}%`,background:`linear-gradient(90deg,${bc},${bc}cc)`,borderRadius:4,transition:"width .8s"}}/>
                  </div>
                  <div style={{display:"flex",justifyContent:"space-between",marginTop:6,fontSize:12,color:p.textMute}}>
                    <span>{(ovIpam.used_ips||0).toLocaleString()} used of {(ovIpam.total_ips||0).toLocaleString()}</span>
                    <span>{((ovIpam.free_ips||ovIpam.available_ips)||0).toLocaleString()} free · {(ovIpam.reserved_ips||0).toLocaleString()} reserved</span>
                  </div>
                </div>
              );
            })()}
          </>
        )}
      </div>
    </div>
  );
}"""
        content = content[:start_idx] + new_section + content[close_overview + len("  );\n}"):]
        print(f"✓ Replaced IPAM overview block (old={len(old_section)}, new={len(new_section)})")

open(path, 'w', encoding='utf-8').write(content)
print(f"Done — new length: {len(content.splitlines())} lines")
