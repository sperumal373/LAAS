const fs=require('fs');
const p='C:/caas-dashboard/frontend/src/App.jsx';
let src=fs.readFileSync(p,'utf8');
const lines=src.split('\n');
const EOL='\r\n';

//  STEP 1: api imports 
const impLine=lines.findIndex(l=>l.includes('createRubrikConnection')&&l.includes('deleteRubrikConnection')&&l.includes('fetchRubrikData'));
if(impLine<0){console.error('STEP1 fail: import line not found');process.exit(1);}
lines.splice(impLine+1,0,'  fetchRVToolsStatus, fetchRVToolsReports, fetchRVToolsVMs,\r','  runRVToolsForVCenter, runRVToolsAll, installRVTools,\r');
console.log('ok: api imports at line '+(impLine+1));

//  STEP 2: state hooks after thresholdOpen 
const thoLine=lines.findIndex(l=>l.includes('const [thresholdOpen')&&l.includes('setThresholdOpen'));
if(thoLine<0){console.error('STEP2 fail: thresholdOpen not found');process.exit(1);}
const stateLines=[
  "  // RVTools state\r",
  "  const [rvtReports, setRvtReports] = useState([]);\r",
  "  const [rvtStatus, setRvtStatus] = useState(null);\r",
  "  const [rvtLoading, setRvtLoading] = useState(false);\r",
  "  const [rvtRunning, setRvtRunning] = useState({});\r",
  "  const [rvtRunAll, setRvtRunAll] = useState(false);\r",
  "  const [rvtExpanded, setRvtExpanded] = useState(null);\r",
  "  const [rvtVMs, setRvtVMs] = useState({});\r",
  "  const [rvtMsg, setRvtMsg] = useState(null);\r",
  "  const [rvtVMFilter, setRvtVMFilter] = useState('');\r",
  "\r",
  "  async function loadRVToolsReports(){\r",
  "    setRvtLoading(true); setRvtMsg(null);\r",
  "    try{\r",
  "      const [rep,st]=await Promise.all([fetchRVToolsReports(),fetchRVToolsStatus()]);\r",
  "      setRvtReports(rep.reports||[]);\r",
  "      setRvtStatus(st);\r",
  "    }catch(e){setRvtMsg({ok:false,text:e.message});}\r",
  "    setRvtLoading(false);\r",
  "  }\r",
  "\r",
  "  async function doRunRVTools(vcenter_id){\r",
  "    setRvtRunning(s=>({...s,[vcenter_id]:true})); setRvtMsg(null);\r",
  "    try{\r",
  "      const res=await runRVToolsForVCenter(vcenter_id);\r",
  "      setRvtMsg({ok:res.success,text:res.message});\r",
  "      if(res.success) await loadRVToolsReports();\r",
  "    }catch(e){setRvtMsg({ok:false,text:e.message});}\r",
  "    setRvtRunning(s=>({...s,[vcenter_id]:false}));\r",
  "  }\r",
  "\r",
  "  async function doRunAllRVTools(){\r",
  "    setRvtRunAll(true); setRvtMsg(null);\r",
  "    try{\r",
  "      const res=await runRVToolsAll();\r",
  "      const ok=(res.results||[]).filter(r=>r.success).length;\r",
  "      const fail=(res.results||[]).filter(r=>!r.success).length;\r",
  "      setRvtMsg({ok:fail===0,text:'Ran '+ok+' OK, '+fail+' failed'});\r",
  "      await loadRVToolsReports();\r",
  "    }catch(e){setRvtMsg({ok:false,text:e.message});}\r",
  "    setRvtRunAll(false);\r",
  "  }\r",
  "\r",
  "  async function doLoadVMs(file){\r",
  "    if(rvtVMs[file]){setRvtExpanded(rvtExpanded===file?null:file); return;}\r",
  "    try{\r",
  "      const res=await fetchRVToolsVMs(file);\r",
  "      setRvtVMs(s=>({...s,[file]:res}));\r",
  "      setRvtExpanded(file);\r",
  "    }catch(e){setRvtMsg({ok:false,text:e.message});}\r",
  "  }\r",
  "\r",
];
lines.splice(thoLine+1,0,...stateLines);
console.log('ok: state hooks at line '+(thoLine+1));

//  STEP 3: useEffect before tabs= array 
const tabsLine=lines.findIndex(l=>l.trim()==='const tabs=[');
if(tabsLine<0){console.error('STEP3 fail: const tabs=[ not found');process.exit(1);}
const effectLines=[
  "  React.useEffect(()=>{\r",
  "    if(vmTab===\"rvtools\"&&rvtReports.length===0&&!rvtLoading) loadRVToolsReports();\r",
  "  },[vmTab]);\r",
  "\r",
];
lines.splice(tabsLine,0,...effectLines);
console.log('ok: useEffect at line '+(tabsLine));

//  STEP 4: rvtools tab entry after manage entry 
const manageLine=lines.findIndex(l=>l.includes('id:"manage"')&&l.includes('Manage vCenters'));
if(manageLine<0){console.error('STEP4 fail: manage tab not found');process.exit(1);}
// manage entry spans 2 lines (manageLine and manageLine+1 has the sub+}]:[]),)
const manageEnd=lines.findIndex((l,i)=>i>manageLine&&l.includes('}]:[]),'));
if(manageEnd<0){console.error('STEP4 fail: manage end not found');process.exit(1);}
const rvtTab=[
  "    {id:\"rvtools\", label:\"RVTools Reports\", icon:\"\", color:\"#f97316\",\r",
  "     sub:rvtReports.length?rvtReports.length+' report'+(rvtReports.length!==1?'s':'')+' \u00b7 '+rvtReports.reduce((s,r)=>s+(r.summary?.total_vms||0),0)+' VMs':(rvtStatus?.installed?'Ready to run':'Not installed')},\r",
];
lines.splice(manageEnd+1,0,...rvtTab);
console.log('ok: rvtools tab entry at line '+(manageEnd+1));

//  STEP 5: RVTools render block before VMwarePage closing 
// Find the last )} before </div>; );  }  before function VMsPage(
const vmspageIdx=lines.findIndex(l=>l.includes('function VMsPage(')&&l.includes('vms,'));
if(vmspageIdx<0){console.error('STEP5 fail: VMsPage not found');process.exit(1);}
// VMwarePage ends at vmspageIdx-2 (the } line), closing is vmspageIdx-3 (the );)
// Structure: 
//   line vmspageIdx-5: "      )}"   -- last tab close
//   line vmspageIdx-4: "    </div>"
//   line vmspageIdx-3: "  );"
//   line vmspageIdx-2: "}"
//   line vmspageIdx-1: ""           -- blank line
//   line vmspageIdx  : "function VMsPage(..."
// We insert the block BEFORE line (vmspageIdx-5) which is the last ")}"
// Actually insert AFTER the "      )}" and before "    </div>"
const closeDivLine=lines.findIndex((l,i)=>i>vmspageIdx-10&&i<vmspageIdx&&l.trim()==='</div>');
const insertBefore=closeDivLine>=0?closeDivLine:(vmspageIdx-4);
console.log('insert render block before line',insertBefore,'content:',lines[insertBefore]);

const renderBlock=
      {/* RVTools Reports tab */}
      {vmTab==="rvtools"&&(
        <div style={{display:"flex",flexDirection:"column",gap:16}}>
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8}}>
            <div>
              <span style={{fontSize:20,fontWeight:700,color:p.text}}> RVTools Reports</span>
              <span style={{marginLeft:12,fontSize:12,color:p.textMute}}>
                VMware inventory via RVTools XLSX exports
                {rvtStatus&&(rvtStatus.installed?<span style={{marginLeft:8,color:"#10b981"}}>  Installed</span>:<span style={{marginLeft:8,color:"#f59e0b"}}>  Not installed</span>)}
              </span>
            </div>
            <div style={{display:"flex",gap:8}}>
              <button className="btn btn-primary btn-sm" onClick={loadRVToolsReports} disabled={rvtLoading}>{rvtLoading?" Scanning":" Refresh"}</button>
              <button className="btn btn-success btn-sm" onClick={doRunAllRVTools} disabled={rvtRunAll||!rvtStatus?.installed}>{rvtRunAll?" Running":" Run All vCenters"}</button>
            </div>
          </div>
          {rvtMsg&&<div style={{padding:"10px 14px",borderRadius:8,background:rvtMsg.ok?"#10b98122":"#ef444422",border:"1px solid "+(rvtMsg.ok?"#10b98166":"#ef444466"),color:rvtMsg.ok?"#10b981":"#ef4444",fontSize:13}}>{rvtMsg.ok?"":""} {rvtMsg.text}</div>}
          {rvtLoading&&<div style={{textAlign:"center",padding:40,color:p.textMute}}> Loading reports</div>}
          {!rvtLoading&&rvtReports.length===0&&(
            <div className="card" style={{textAlign:"center",padding:40}}>
              <div style={{fontSize:48,marginBottom:12}}></div>
              <div style={{fontSize:16,fontWeight:600,color:p.text,marginBottom:6}}>No RVTools Reports Found</div>
              <div style={{fontSize:13,color:p.textMute,marginBottom:16}}>
                {rvtStatus?.installed?"Click Run All vCenters to generate fresh reports.":"RVTools not installed. Place XLSX exports in C:\\\\caas-dashboard\\\\rvtools_exports\\\\ or Desktop."}
              </div>
            </div>
          )}
          {!rvtLoading&&rvtStatus&&(
            <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
              {(rvtStatus.vcenters||[]).map(vc=>(
                <button key={vc.host} disabled={rvtRunning[vc.host]||!rvtStatus.installed}
                  onClick={()=>doRunRVTools(vc.host)}
                  style={{background:"#f9741622",border:"1px solid #f97316",color:"#f97316",borderRadius:6,padding:"4px 12px",fontSize:12,cursor:rvtRunning[vc.host]||!rvtStatus.installed?"not-allowed":"pointer"}}>
                  {rvtRunning[vc.host]?" "+vc.name+"":" "+vc.name}
                </button>
              ))}
            </div>
          )}
          {rvtReports.map((rep,ri)=>{
            const s=rep.summary||{};
            const isExp=rvtExpanded===rep.file;
            const vmData=rvtVMs[rep.file];
            const fmtDt=dt=>dt?new Date(dt).toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"}):"";
            const top5os=Object.entries(s.os_counts||{}).sort((a,b)=>b[1]-a[1]).slice(0,5);
            const vcName=rep.vcenter_name||rep.filename;
            return(
              <div key={rep.file} className="card" style={{border:"1px solid "+p.border}}>
                <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8,marginBottom:12}}>
                  <div>
                    <span style={{fontSize:15,fontWeight:700,color:p.text}}> {vcName}</span>
                    {rep.vcenter_host&&rep.vcenter_host!==vcName&&<span style={{marginLeft:8,fontSize:11,color:p.textMute}}>{rep.vcenter_host}</span>}
                    <span style={{marginLeft:12,fontSize:11,color:p.textMute}}>{fmtDt(rep.modified)}  {rep.size_kb}KB</span>
                  </div>
                  <div style={{display:"flex",gap:8}}>
                    <button className="btn btn-primary btn-sm" onClick={()=>doLoadVMs(rep.file)}>{isExp?" Hide VMs":" View VMs"}</button>
                    {rvtStatus?.installed&&<button disabled={!!rvtRunning[rep.vcenter_host]}
                      onClick={()=>doRunRVTools(rep.vcenter_host||"")}
                      style={{background:"#f9741622",border:"1px solid #f97316",color:"#f97316",borderRadius:6,padding:"4px 10px",fontSize:12,cursor:"pointer"}}>
                      {rvtRunning[rep.vcenter_host]?" Running":" Refresh"}
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
                          <span style={{color:p.textMute,whiteSpace:"nowrap"}}>{v.ram_gb}GB  {v.cpus}vCPU</span>
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
                        placeholder="Search VMs, IP, OS, cluster"
                        style={{flex:1,padding:"5px 10px",borderRadius:6,border:"1px solid "+p.border,background:p.card,color:p.text,fontSize:12}}/>
                      <span style={{fontSize:12,color:p.textMute,whiteSpace:"nowrap"}}>{vmData?.vms?.length||0} VMs</span>
                    </div>
                    {vmData?(
                      <div style={{overflowX:"auto",maxHeight:400,overflowY:"auto"}}>
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
                                <td style={{padding:"4px 8px",color:p.textMute,textAlign:"center"}}>{v.cpus||""}</td>
                                <td style={{padding:"4px 8px",color:p.textMute,textAlign:"center"}}>{v.memory_mb?Math.round(v.memory_mb/1024):""}</td>
                                <td style={{padding:"4px 8px",color:"#60a5fa",fontFamily:"monospace",fontSize:10}}>{v.primary_ip||""}</td>
                                <td style={{padding:"4px 8px",color:p.textMute,maxWidth:160,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.os_tools||v.os_config||""}</td>
                                <td style={{padding:"4px 8px",color:p.textMute}}>{v.cluster||""}</td>
                                <td style={{padding:"4px 8px",color:p.textMute,maxWidth:130,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.host||""}</td>
                                <td style={{padding:"4px 8px",color:p.textMute}}>{v.datacenter||""}</td>
                              </tr>);
                            })}
                          </tbody>
                        </table>
                      </div>
                    ):<div style={{textAlign:"center",padding:20,color:p.textMute}}> Loading</div>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
.split('\n').map(l=>(l.endsWith('\r')?l:l+'\r'));

lines.splice(insertBefore,0,...renderBlock);
console.log('ok: render block inserted ('+renderBlock.length+' lines)');

//  WRITE 
fs.writeFileSync(p,lines.join('\n'),'utf8');
console.log('\n=== App.jsx updated successfully ===');
