"""
add_rvtools_tab.py
Injects RVTools tab into App.jsx (VMwarePage) - handles CRLF Windows files
"""
import re

PATH = r'C:\caas-dashboard\frontend\src\App.jsx'

with open(PATH, 'r', encoding='utf-8') as f:
    src = f.read()

lines = src.split('\n')   # keeps \r at end of each line (CRLF file)
print(f"Loaded {len(lines)} lines")

def find_line(predicate, start=0, error=None):
    for i, l in enumerate(lines):
        if i >= start and predicate(l):
            return i
    if error:
        raise RuntimeError(error)
    return -1

def insert_after(idx, new_lines):
    for i, l in enumerate(new_lines):
        lines.insert(idx + 1 + i, l if l.endswith('\r') or l == '\r' or l == '' else l + '\r')

def insert_before(idx, new_lines):
    for i, l in enumerate(new_lines):
        lines.insert(idx + i, l if l.endswith('\r') or l == '\r' or l == '' else l + '\r')

# ── STEP 1: Add RVTools imports ───────────────────────────────────────────────
imp_idx = find_line(
    lambda l: 'createRubrikConnection' in l and 'deleteRubrikConnection' in l and 'fetchRubrikData' in l,
    error="STEP1: import line"
)
insert_after(imp_idx, [
    '  fetchRVToolsStatus, fetchRVToolsReports, fetchRVToolsVMs,',
    '  runRVToolsForVCenter, runRVToolsAll, installRVTools,',
])
print(f"✓ STEP1: imports injected after line {imp_idx+1}")

# ── STEP 2: Add state hooks after thresholdOpen ───────────────────────────────
tho_idx = find_line(
    lambda l: 'const [thresholdOpen' in l and 'setThresholdOpen' in l,
    error="STEP2: thresholdOpen"
)
state_lines = [
    '',
    '  // RVTools state',
    '  const [rvtReports, setRvtReports] = useState([]);',
    '  const [rvtStatus, setRvtStatus] = useState(null);',
    '  const [rvtLoading, setRvtLoading] = useState(false);',
    '  const [rvtRunning, setRvtRunning] = useState({});',
    '  const [rvtRunAll, setRvtRunAll] = useState(false);',
    '  const [rvtExpanded, setRvtExpanded] = useState(null);',
    '  const [rvtVMs, setRvtVMs] = useState({});',
    '  const [rvtMsg, setRvtMsg] = useState(null);',
    '  const [rvtVMFilter, setRvtVMFilter] = useState("");',
    '',
    '  async function loadRVToolsReports(){',
    '    setRvtLoading(true); setRvtMsg(null);',
    '    try{',
    '      const [rep,st]=await Promise.all([fetchRVToolsReports(),fetchRVToolsStatus()]);',
    '      setRvtReports(rep.reports||[]);',
    '      setRvtStatus(st);',
    '    }catch(e){setRvtMsg({ok:false,text:e.message});}',
    '    setRvtLoading(false);',
    '  }',
    '',
    '  async function doRunRVTools(vcenter_id){',
    '    setRvtRunning(s=>({...s,[vcenter_id]:true})); setRvtMsg(null);',
    '    try{',
    '      const res=await runRVToolsForVCenter(vcenter_id);',
    '      setRvtMsg({ok:res.success,text:res.message});',
    '      if(res.success) await loadRVToolsReports();',
    '    }catch(e){setRvtMsg({ok:false,text:e.message});}',
    '    setRvtRunning(s=>({...s,[vcenter_id]:false}));',
    '  }',
    '',
    '  async function doRunAllRVTools(){',
    '    setRvtRunAll(true); setRvtMsg(null);',
    '    try{',
    '      const res=await runRVToolsAll();',
    '      const ok=(res.results||[]).filter(r=>r.success).length;',
    '      const fail=(res.results||[]).filter(r=>!r.success).length;',
    '      setRvtMsg({ok:fail===0,text:`Ran ${ok} OK, ${fail} failed`});',
    '      await loadRVToolsReports();',
    '    }catch(e){setRvtMsg({ok:false,text:e.message});}',
    '    setRvtRunAll(false);',
    '  }',
    '',
    '  async function doLoadVMs(file){',
    '    if(rvtVMs[file]){setRvtExpanded(rvtExpanded===file?null:file);return;}',
    '    try{',
    '      const res=await fetchRVToolsVMs(file);',
    '      setRvtVMs(s=>({...s,[file]:res}));',
    '      setRvtExpanded(file);',
    '    }catch(e){setRvtMsg({ok:false,text:e.message});}',
    '  }',
]
insert_after(tho_idx, state_lines)
print(f"✓ STEP2: state hooks injected after line {tho_idx+1}")

# ── STEP 3: useEffect before const tabs= ─────────────────────────────────────
tabs_idx = find_line(
    lambda l: l.strip() == 'const tabs=[',
    error="STEP3: const tabs=["
)
effect_lines = [
    '  React.useEffect(()=>{',
    '    if(vmTab==="rvtools"&&rvtReports.length===0&&!rvtLoading) loadRVToolsReports();',
    '  },[vmTab]);',
    '',
]
insert_before(tabs_idx, effect_lines)
print(f"✓ STEP3: useEffect injected before line {tabs_idx+1}")

# ── STEP 4: rvtools tab entry after manage entry ──────────────────────────────
manage_idx = find_line(lambda l: 'id:"manage"' in l and 'Manage vCenters' in l,
    error="STEP4: manage tab")
# manage entry spans 2 lines: manageLine + manageLine+1 (the sub line ending in }]:[]),)
manage_end = find_line(lambda l: '}]:[]),' in l, start=manage_idx+1,
    error="STEP4: manage end")
rvt_tab_lines = [
    '    {id:"rvtools", label:"RVTools Reports", icon:"\U0001f4ca", color:"#f97316",',
    '     sub:rvtReports.length?rvtReports.length+" report"+(rvtReports.length!==1?"s":"")+" \u00b7 "+rvtReports.reduce((s,r)=>s+(r.summary?.total_vms||0),0)+" VMs":(rvtStatus?.installed?"Ready to run":"Not installed")},',
]
insert_after(manage_end, rvt_tab_lines)
print(f"✓ STEP4: rvtools tab entry injected after line {manage_end+1}")

# ── STEP 5: RVTools render block before VMwarePage closing ────────────────────
vmpage_idx = find_line(lambda l: 'function VMsPage(' in l and 'vms,' in l,
    error="STEP5: VMsPage function")
# Find the  </div> that closes VMwarePage return (just before VMsPage)
close_div_idx = find_line(lambda l: l.strip() == '</div>', start=vmpage_idx - 10,
    error="STEP5: closing div")
# This should be around vmpage_idx - 4

render_block = r"""
      {/* RVTools Reports tab */}
      {vmTab==="rvtools"&&(
        <div style={{display:"flex",flexDirection:"column",gap:16}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8}}>
            <div>
              <span style={{fontSize:20,fontWeight:700,color:p.text}}>""" + "\U0001f4ca" + r""" RVTools Reports</span>
              <span style={{marginLeft:12,fontSize:12,color:p.textMute}}>VMware inventory via RVTools XLSX exports
                {rvtStatus&&(rvtStatus.installed?<span style={{marginLeft:8,color:"#10b981"}}> \u25cf Installed</span>:<span style={{marginLeft:8,color:"#f59e0b"}}> \u26a0 Not installed</span>)}
              </span>
            </div>
            <div style={{display:"flex",gap:8}}>
              <button className="btn btn-primary btn-sm" onClick={loadRVToolsReports} disabled={rvtLoading}>{rvtLoading?"\u27f3 Scanning\u2026":"\u27f3 Refresh"}</button>
              <button className="btn btn-success btn-sm" onClick={doRunAllRVTools} disabled={rvtRunAll||!rvtStatus?.installed}>{rvtRunAll?"\u27f3 Running\u2026":"\u25b6 Run All vCenters"}</button>
            </div>
          </div>
          {rvtMsg&&<div style={{padding:"10px 14px",borderRadius:8,background:rvtMsg.ok?"#10b98122":"#ef444422",border:"1px solid "+(rvtMsg.ok?"#10b98166":"#ef444466"),color:rvtMsg.ok?"#10b981":"#ef4444",fontSize:13}}>{rvtMsg.ok?"\u2713":"\u2717"} {rvtMsg.text}</div>}
          {rvtLoading&&<div style={{textAlign:"center",padding:40,color:p.textMute}}>\u27f3 Loading reports\u2026</div>}
          {!rvtLoading&&rvtReports.length===0&&(
            <div className="card" style={{textAlign:"center",padding:40}}>
              <div style={{fontSize:48,marginBottom:12}}>""" + "\U0001f4cb" + r"""</div>
              <div style={{fontSize:16,fontWeight:600,color:p.text,marginBottom:6}}>No RVTools Reports Found</div>
              <div style={{fontSize:13,color:p.textMute,marginBottom:8}}>
                {rvtStatus?.installed?"Click Run All vCenters to generate reports.":"RVTools not installed. Place XLSX exports in C:\\caas-dashboard\\rvtools_exports\\ or Desktop."}
              </div>
            </div>
          )}
          {!rvtLoading&&rvtStatus&&(rvtStatus.vcenters||[]).length>0&&(
            <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
              {(rvtStatus.vcenters||[]).map(vc=>(
                <button key={vc.host} disabled={!!rvtRunning[vc.host]||!rvtStatus.installed}
                  onClick={()=>doRunRVTools(vc.host)}
                  style={{background:"#f9741622",border:"1px solid #f97316",color:"#f97316",borderRadius:6,padding:"4px 12px",fontSize:12,cursor:rvtRunning[vc.host]||!rvtStatus.installed?"not-allowed":"pointer"}}>
                  {rvtRunning[vc.host]?"\u27f3 "+vc.name+"\u2026":"\u25b6 "+vc.name}
                </button>
              ))}
            </div>
          )}
          {rvtReports.map((rep,ri)=>{
            const s=rep.summary||{};
            const isExp=rvtExpanded===rep.file;
            const vmData=rvtVMs[rep.file];
            const fmtDt=dt=>dt?new Date(dt).toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"}):"—";
            const top5os=Object.entries(s.os_counts||{}).sort((a,b)=>b[1]-a[1]).slice(0,5);
            const vcName=rep.vcenter_name||rep.filename;
            return(
              <div key={rep.file} className="card" style={{border:"1px solid "+p.border}}>
                <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8,marginBottom:12}}>
                  <div>
                    <span style={{fontSize:15,fontWeight:700,color:p.text}}>""" + "\U0001f4ca" + r""" {vcName}</span>
                    {rep.vcenter_host&&rep.vcenter_host!==vcName&&<span style={{marginLeft:8,fontSize:11,color:p.textMute}}>{rep.vcenter_host}</span>}
                    <span style={{marginLeft:12,fontSize:11,color:p.textMute}}>{fmtDt(rep.modified)} · {rep.size_kb}KB</span>
                  </div>
                  <div style={{display:"flex",gap:8}}>
                    <button className="btn btn-primary btn-sm" onClick={()=>doLoadVMs(rep.file)}>{isExp?"\u25b2 Hide VMs":"\u25bc View VMs"}</button>
                    {rvtStatus?.installed&&<button disabled={!!rvtRunning[rep.vcenter_host]} onClick={()=>doRunRVTools(rep.vcenter_host||"")}
                      style={{background:"#f9741622",border:"1px solid #f97316",color:"#f97316",borderRadius:6,padding:"4px 10px",fontSize:12,cursor:"pointer"}}>
                      {rvtRunning[rep.vcenter_host]?"\u27f3 Running\u2026":"\u27f3 Refresh"}
                    </button>}
                  </div>
                </div>
                <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(110px,1fr))",gap:8,marginBottom:12}}>
                  {[
                    {label:"Total VMs",value:s.total_vms||0,color:"#3b82f6"},
                    {label:"Powered On",value:s.powered_on||0,color:"#10b981"},
                    {label:"Powered Off",value:s.powered_off||0,color:"#ef4444"},
                    {label:"Templates",value:s.templates||0,color:"#8b5cf6"},
                    {label:"vCPU (on)",value:s.total_vcpu||0,color:"#f59e0b"},
                    {label:"RAM GB (on)",value:s.total_ram_gb||0,color:"#06b6d4"},
                    {label:"Prov. TB",value:s.total_provisioned_tb||0,color:"#a78bfa"},
                    {label:"ESXi Hosts",value:s.total_hosts||0,color:"#64748b"},
                  ].map(k=>(
                    <div key={k.label} style={{background:p.card,border:"1px solid "+p.border,borderRadius:8,padding:"8px 10px",textAlign:"center"}}>
                      <div style={{fontSize:19,fontWeight:700,color:k.color}}>{k.value}</div>
                      <div style={{fontSize:10,color:p.textMute,marginTop:2}}>{k.label}</div>
                    </div>
                  ))}
                </div>
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
                  {top5os.length>0&&(
                    <div>
                      <div style={{fontSize:12,fontWeight:600,color:p.textMute,marginBottom:6}}>OS Distribution</div>
                      {top5os.map(([os,cnt])=>{
                        const pct=s.total_vms>0?Math.round((cnt/s.total_vms)*100):0;
                        return(<div key={os} style={{marginBottom:4}}>
                          <div style={{display:"flex",justifyContent:"space-between",fontSize:11,marginBottom:2}}>
                            <span style={{color:p.text,maxWidth:155,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{os}</span>
                            <span style={{color:p.textMute}}>{cnt} ({pct}%)</span>
                          </div>
                          <div style={{height:4,borderRadius:2,background:p.border}}><div style={{height:"100%",borderRadius:2,background:"#3b82f6",width:pct+"%"}}/></div>
                        </div>);
                      })}
                    </div>
                  )}
                  {(s.top10_by_ram||[]).length>0&&(
                    <div>
                      <div style={{fontSize:12,fontWeight:600,color:p.textMute,marginBottom:6}}>Top VMs by RAM</div>
                      {(s.top10_by_ram||[]).slice(0,5).map(v=>(
                        <div key={v.name} style={{display:"flex",justifyContent:"space-between",fontSize:11,marginBottom:4}}>
                          <span style={{color:p.text,maxWidth:155,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.name}</span>
                          <span style={{color:p.textMute,whiteSpace:"nowrap"}}>{v.ram_gb}GB · {v.cpus}vCPU</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                {(s.clusters||[]).length>0&&(
                  <div style={{marginTop:8}}>
                    <span style={{fontSize:11,color:p.textMute}}>Clusters: </span>
                    {(s.clusters||[]).map(c=><span key={c} style={{display:"inline-block",background:p.border,borderRadius:4,padding:"1px 6px",fontSize:11,color:p.text,margin:"1px 3px"}}>{c}</span>)}
                  </div>
                )}
                {isExp&&(
                  <div style={{marginTop:14,borderTop:"1px solid "+p.border,paddingTop:12}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                      <input value={rvtVMFilter} onChange={e=>setRvtVMFilter(e.target.value)}
                        placeholder="Search VMs, IP, OS, cluster\u2026"
                        style={{flex:1,padding:"5px 10px",borderRadius:6,border:"1px solid "+p.border,background:p.card,color:p.text,fontSize:12}}/>
                      <span style={{fontSize:12,color:p.textMute,whiteSpace:"nowrap"}}>{vmData?.vms?.length||0} VMs</span>
                    </div>
                    {vmData?(
                      <div style={{overflowX:"auto",maxHeight:420,overflowY:"auto"}}>
                        <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                          <thead><tr style={{background:p.border,position:"sticky",top:0}}>
                            {["VM Name","Power","CPUs","RAM GB","Primary IP","OS","Cluster","Host","Datacenter"].map(h=>(
                              <th key={h} style={{padding:"5px 8px",textAlign:"left",color:p.textMute,fontWeight:600,whiteSpace:"nowrap"}}>{h}</th>
                            ))}
                          </tr></thead>
                          <tbody>
                            {(vmData.vms||[]).filter(v=>{
                              if(!rvtVMFilter) return true;
                              const q=rvtVMFilter.toLowerCase();
                              return (v.name||"").toLowerCase().includes(q)||(v.primary_ip||"").includes(q)||(v.os_tools||"").toLowerCase().includes(q)||(v.cluster||"").toLowerCase().includes(q)||(v.datacenter||"").toLowerCase().includes(q);
                            }).slice(0,300).map((v,i)=>{
                              const pwrClr=v.powerstate==="poweredOn"?"#10b981":v.powerstate==="suspended"?"#f59e0b":"#ef4444";
                              return(<tr key={i} style={{borderBottom:"1px solid "+p.border}}>
                                <td style={{padding:"4px 8px",color:p.text,maxWidth:180,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.name}</td>
                                <td style={{padding:"4px 8px"}}><span style={{color:pwrClr,fontWeight:600,fontSize:10}}>{v.powerstate==="poweredOn"?"ON":v.powerstate==="poweredOff"?"OFF":v.powerstate||"?"}</span></td>
                                <td style={{padding:"4px 8px",color:p.textMute,textAlign:"center"}}>{v.cpus||"—"}</td>
                                <td style={{padding:"4px 8px",color:p.textMute,textAlign:"center"}}>{v.memory_mb?Math.round(v.memory_mb/1024):"—"}</td>
                                <td style={{padding:"4px 8px",color:"#60a5fa",fontFamily:"monospace",fontSize:10}}>{v.primary_ip||"—"}</td>
                                <td style={{padding:"4px 8px",color:p.textMute,maxWidth:160,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.os_tools||v.os_config||"—"}</td>
                                <td style={{padding:"4px 8px",color:p.textMute}}>{v.cluster||"—"}</td>
                                <td style={{padding:"4px 8px",color:p.textMute,maxWidth:130,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.host||"—"}</td>
                                <td style={{padding:"4px 8px",color:p.textMute}}>{v.datacenter||"—"}</td>
                              </tr>);
                            })}
                          </tbody>
                        </table>
                      </div>
                    ):<div style={{textAlign:"center",padding:20,color:p.textMute}}>\u27f3 Loading VM list\u2026</div>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}"""

render_lines = render_block.split('\n')
insert_before(close_div_idx, render_lines)
print(f"✓ STEP5: render block injected ({len(render_lines)} lines) before line {close_div_idx+1}")

# ── WRITE ─────────────────────────────────────────────────────────────────────
out = '\n'.join(lines)
with open(PATH, 'w', encoding='utf-8') as f:
    f.write(out)
print(f"\n✅ App.jsx updated ({len(lines)} lines total)")
