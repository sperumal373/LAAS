// add_rvtools_tab.js — Adds RVTools tab to VMwarePage in App.jsx (line-based, CRLF-safe)
const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
let src = fs.readFileSync(path, 'utf8');

// ── 1. Add RVTools to api imports ─────────────────────────────────────────────
const OLD_IMPORT = '  createRubrikConnection, deleteRubrikConnection, fetchRubrikData,\n} from "./api";';
const NEW_IMPORT = `  createRubrikConnection, deleteRubrikConnection, fetchRubrikData,
  fetchRVToolsStatus, fetchRVToolsReports, fetchRVToolsVMs,
  runRVToolsForVCenter, runRVToolsAll, installRVTools,
} from "./api";`;

if (!src.includes(OLD_IMPORT)) {
  console.error('ERROR: api import block not found'); process.exit(1);
}
src = src.replace(OLD_IMPORT, NEW_IMPORT);
console.log('✓ Added RVTools api imports');

// ── 2. Add state hooks after thresholdOpen ────────────────────────────────────
const OLD_STATE = '  const [thresholdOpen, setThresholdOpen] = useState(false);\n  const canAct=';
const NEW_STATE = `  const [thresholdOpen, setThresholdOpen] = useState(false);

  // RVTools state
  const [rvtReports, setRvtReports] = useState([]);
  const [rvtStatus, setRvtStatus] = useState(null);
  const [rvtLoading, setRvtLoading] = useState(false);
  const [rvtRunning, setRvtRunning] = useState({});  // vcenter_host -> bool
  const [rvtRunAll, setRvtRunAll] = useState(false);
  const [rvtExpanded, setRvtExpanded] = useState(null);  // file path
  const [rvtVMs, setRvtVMs] = useState({});  // file -> vm list
  const [rvtMsg, setRvtMsg] = useState(null);
  const [rvtVMFilter, setRvtVMFilter] = useState("");

  async function loadRVToolsReports() {
    setRvtLoading(true); setRvtMsg(null);
    try {
      const [rep, st] = await Promise.all([fetchRVToolsReports(), fetchRVToolsStatus()]);
      setRvtReports(rep.reports || []);
      setRvtStatus(st);
    } catch(e) { setRvtMsg({ok:false,text:e.message}); }
    setRvtLoading(false);
  }

  async function doRunRVTools(vcenter_id) {
    setRvtRunning(s=>({...s,[vcenter_id]:true})); setRvtMsg(null);
    try {
      const res = await runRVToolsForVCenter(vcenter_id);
      setRvtMsg({ok:res.success, text:res.message});
      if(res.success) await loadRVToolsReports();
    } catch(e) { setRvtMsg({ok:false,text:e.message}); }
    setRvtRunning(s=>({...s,[vcenter_id]:false}));
  }

  async function doRunAllRVTools() {
    setRvtRunAll(true); setRvtMsg(null);
    try {
      const res = await runRVToolsAll();
      const ok = (res.results||[]).filter(r=>r.success).length;
      const fail = (res.results||[]).filter(r=>!r.success).length;
      setRvtMsg({ok:fail===0, text:\`Ran \${ok} OK, \${fail} failed\`});
      await loadRVToolsReports();
    } catch(e) { setRvtMsg({ok:false,text:e.message}); }
    setRvtRunAll(false);
  }

  async function doLoadVMs(file) {
    if(rvtVMs[file]) { setRvtExpanded(rvtExpanded===file?null:file); return; }
    try {
      const res = await fetchRVToolsVMs(file);
      setRvtVMs(s=>({...s,[file]:res}));
      setRvtExpanded(file);
    } catch(e) { setRvtMsg({ok:false,text:e.message}); }
  }

  const canAct=`;

if (!src.includes(OLD_STATE)) {
  console.error('ERROR: state hook anchor not found'); process.exit(1);
}
src = src.replace(OLD_STATE, NEW_STATE);
console.log('✓ Added RVTools state hooks');

// ── 3. Add useEffect to load reports when tab is rvtools ──────────────────────
const OLD_TABS = `  const tabs=[`;
const NEW_TABS = `  // Load RVTools reports when tab is selected
  React.useEffect(()=>{
    if(vmTab==="rvtools"&&rvtReports.length===0&&!rvtLoading) loadRVToolsReports();
  },[vmTab]);

  const tabs=[`;

if (!src.includes(OLD_TABS)) {
  console.error('ERROR: tabs array anchor not found'); process.exit(1);
}
src = src.replace(OLD_TABS, NEW_TABS);
console.log('✓ Added RVTools useEffect');

// ── 4. Add rvtools tab to tabs array (after manage entry) ────────────────────
const OLD_MANAGE_TAB = `    ...(isAdmin?[{id:"manage", label:"Manage vCenters", icon:"⚙️", color:"#a78bfa",
     sub:\`\${vcenters.length} vCenter\${vcenters.length!==1?"s":""} configured\`}]:[]),
  ];`;
const NEW_MANAGE_TAB = `    ...(isAdmin?[{id:"manage", label:"Manage vCenters", icon:"⚙️", color:"#a78bfa",
     sub:\`\${vcenters.length} vCenter\${vcenters.length!==1?"s":""} configured\`}]:[]),
    {id:"rvtools", label:"RVTools Reports", icon:"📊", color:"#f97316",
     sub:rvtReports.length?
       \`\${rvtReports.length} report\${rvtReports.length!==1?"s":""} · \${rvtReports.reduce((s,r)=>s+(r.summary?.total_vms||0),0)} VMs\`:
       (rvtStatus?.installed?"Ready to run":"Not installed")},
  ];`;

if (!src.includes(OLD_MANAGE_TAB)) {
  // Try alternate whitespace
  console.error('ERROR: manage tab entry not found (check whitespace)');
  // print surrounding context for debug
  const idx = src.indexOf('id:"manage"');
  if(idx>=0) console.log('Context:', JSON.stringify(src.slice(idx-10,idx+120)));
  process.exit(1);
}
src = src.replace(OLD_MANAGE_TAB, NEW_MANAGE_TAB);
console.log('✓ Added rvtools tab entry');

// ── 5. Add RVTools render block before closing </div> of VMwarePage ───────────
const OLD_DS_CLOSE = `      )}
    </div>
  );
}

function VMsPage(`;

const RVTOOLS_BLOCK = `      )}

      {/* ── RVTools Reports tab ── */}
      {vmTab==="rvtools"&&(
        <div style={{display:"flex",flexDirection:"column",gap:16}}>
          {/* Header row */}
          <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8}}>
            <div>
              <span style={{fontSize:20,fontWeight:700,color:p.text}}>📊 RVTools Reports</span>
              <span style={{marginLeft:12,fontSize:12,color:p.textMute}}>
                Import VMware inventory via RVTools XLSX exports
                {rvtStatus&&(
                  rvtStatus.installed
                    ? <span style={{marginLeft:8,color:"#10b981"}}>● RVTools installed</span>
                    : <span style={{marginLeft:8,color:"#f59e0b"}}>⚠ RVTools not installed</span>
                )}
              </span>
            </div>
            <div style={{display:"flex",gap:8}}>
              <button className="btn btn-primary btn-sm" onClick={loadRVToolsReports} disabled={rvtLoading}>
                {rvtLoading?"⟳ Scanning…":"⟳ Refresh"}
              </button>
              <button className="btn btn-success btn-sm" onClick={doRunAllRVTools} disabled={rvtRunAll||!rvtStatus?.installed}>
                {rvtRunAll?"⟳ Running all…":"▶ Run All vCenters"}
              </button>
            </div>
          </div>

          {rvtMsg&&(
            <div style={{padding:"10px 14px",borderRadius:8,background:rvtMsg.ok?"#10b98122":"#ef444422",
              border:\`1px solid \${rvtMsg.ok?"#10b98166":"#ef444466"}\`,color:rvtMsg.ok?"#10b981":"#ef4444",fontSize:13}}>
              {rvtMsg.ok?"✓":"✗"} {rvtMsg.text}
            </div>
          )}

          {rvtLoading&&<div style={{textAlign:"center",padding:40,color:p.textMute}}>⟳ Loading reports…</div>}

          {!rvtLoading&&rvtReports.length===0&&(
            <div className="card" style={{textAlign:"center",padding:40}}>
              <div style={{fontSize:48,marginBottom:12}}>📋</div>
              <div style={{fontSize:16,fontWeight:600,color:p.text,marginBottom:6}}>No RVTools Reports Found</div>
              <div style={{fontSize:13,color:p.textMute,marginBottom:16}}>
                {rvtStatus?.installed
                  ? "Click 'Run All vCenters' to generate fresh reports from all configured vCenters."
                  : "RVTools is not installed. Place .xlsx exports in C:\\caas-dashboard\\rvtools_exports\\ or on the Desktop."}
              </div>
              {!rvtStatus?.installed&&(
                <div style={{fontSize:12,color:p.textMute}}>
                  Or download RVTools from{" "}
                  <a href="https://www.robware.net" target="_blank" rel="noreferrer" style={{color:"#f97316"}}>robware.net</a>
                </div>
              )}
            </div>
          )}

          {/* Per-vCenter run buttons (even if no report yet) */}
          {!rvtLoading&&rvtStatus&&(
            <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
              {(rvtStatus.vcenters||[]).map(vc=>(
                <button key={vc.host} className="btn btn-sm" disabled={rvtRunning[vc.host]||!rvtStatus.installed}
                  onClick={()=>doRunRVTools(vc.host)}
                  style={{background:"#f9741622",border:"1px solid #f97316",color:"#f97316",borderRadius:6,padding:"4px 12px",fontSize:12,cursor:"pointer"}}>
                  {rvtRunning[vc.host]?<>⟳ Running {vc.name}…</>:<>▶ {vc.name}</>}
                </button>
              ))}
            </div>
          )}

          {/* Report cards */}
          {rvtReports.map(rep=>{
            const s=rep.summary||{};
            const isExp=rvtExpanded===rep.file;
            const vmData=rvtVMs[rep.file];
            const fmtDate=dt=>dt?new Date(dt).toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"}):"—";
            const top5os=Object.entries(s.os_counts||{}).sort((a,b)=>b[1]-a[1]).slice(0,5);
            const vcName=rep.vcenter_name||rep.filename;
            return(
              <div key={rep.file} className="card" style={{border:\`1px solid \${p.border}\`}}>
                {/* Card header */}
                <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8,marginBottom:12}}>
                  <div>
                    <span style={{fontSize:16,fontWeight:700,color:p.text}}>
                      📊 {vcName}
                    </span>
                    {rep.vcenter_host&&rep.vcenter_host!==vcName&&
                      <span style={{marginLeft:8,fontSize:12,color:p.textMute}}>{rep.vcenter_host}</span>}
                    <span style={{marginLeft:12,fontSize:11,color:p.textMute}}>
                      {fmtDate(rep.modified)} · {rep.size_kb}KB
                    </span>
                  </div>
                  <div style={{display:"flex",gap:8}}>
                    <button className="btn btn-primary btn-sm" onClick={()=>doLoadVMs(rep.file)}>
                      {isExp?"▲ Hide VMs":"▼ View VMs"}
                    </button>
                    <button className="btn btn-sm" disabled={rvtRunning[rep.vcenter_host]||!rvtStatus?.installed}
                      onClick={()=>doRunRVTools(rep.vcenter_host||"unknown")}
                      style={{background:"#f9741622",border:"1px solid #f97316",color:"#f97316",borderRadius:6,padding:"4px 10px",fontSize:12}}>
                      {rvtRunning[rep.vcenter_host]?"⟳ Running…":"⟳ Refresh"}
                    </button>
                  </div>
                </div>

                {/* KPI row */}
                <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(130px,1fr))",gap:10,marginBottom:12}}>
                  {[
                    {label:"Total VMs",    value:s.total_vms||0,     color:"#3b82f6"},
                    {label:"Powered On",   value:s.powered_on||0,    color:"#10b981"},
                    {label:"Powered Off",  value:s.powered_off||0,   color:"#ef4444"},
                    {label:"Templates",    value:s.templates||0,     color:"#8b5cf6"},
                    {label:"vCPU (on)",    value:s.total_vcpu||0,    color:"#f59e0b"},
                    {label:"RAM GB (on)",  value:s.total_ram_gb||0,  color:"#06b6d4"},
                    {label:"Prov. TB",     value:s.total_provisioned_tb||0, color:"#a78bfa"},
                    {label:"ESXi Hosts",   value:s.total_hosts||0,   color:"#64748b"},
                  ].map(k=>(
                    <div key={k.label} style={{background:p.card,border:\`1px solid \${p.border}\`,borderRadius:8,padding:"10px 12px",textAlign:"center"}}>
                      <div style={{fontSize:20,fontWeight:700,color:k.color}}>{k.value}</div>
                      <div style={{fontSize:11,color:p.textMute,marginTop:2}}>{k.label}</div>
                    </div>
                  ))}
                </div>

                {/* OS breakdown + top consumers row */}
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:4}}>
                  {/* OS */}
                  {top5os.length>0&&(
                    <div>
                      <div style={{fontSize:12,fontWeight:600,color:p.textMute,marginBottom:6}}>OS Distribution (top 5)</div>
                      {top5os.map(([os,cnt])=>{
                        const pct=s.total_vms>0?Math.round((cnt/s.total_vms)*100):0;
                        return(
                          <div key={os} style={{marginBottom:4}}>
                            <div style={{display:"flex",justifyContent:"space-between",fontSize:11,marginBottom:2}}>
                              <span style={{color:p.text,maxWidth:160,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{os}</span>
                              <span style={{color:p.textMute}}>{cnt} ({pct}%)</span>
                            </div>
                            <div style={{height:4,borderRadius:2,background:p.border}}>
                              <div style={{height:"100%",borderRadius:2,background:"#3b82f6",width:\`\${pct}%\`}}/>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {/* Top consumers */}
                  {(s.top10_by_ram||[]).length>0&&(
                    <div>
                      <div style={{fontSize:12,fontWeight:600,color:p.textMute,marginBottom:6}}>Top VMs by RAM</div>
                      {(s.top10_by_ram||[]).slice(0,5).map(v=>(
                        <div key={v.name} style={{display:"flex",justifyContent:"space-between",fontSize:11,marginBottom:4,color:p.text}}>
                          <span style={{maxWidth:160,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.name}</span>
                          <span style={{color:p.textMute,whiteSpace:"nowrap"}}>{v.ram_gb}GB · {v.cpus}vCPU</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Clusters */}
                {(s.clusters||[]).length>0&&(
                  <div style={{marginTop:8}}>
                    <span style={{fontSize:11,color:p.textMute}}>Clusters: </span>
                    {(s.clusters||[]).map(c=>(
                      <span key={c} style={{display:"inline-block",background:p.border,borderRadius:4,padding:"1px 6px",fontSize:11,color:p.text,margin:"1px 3px"}}>{c}</span>
                    ))}
                  </div>
                )}

                {/* Expanded VM table */}
                {isExp&&(
                  <div style={{marginTop:14,borderTop:\`1px solid \${p.border}\`,paddingTop:12}}>
                    <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:10}}>
                      <input value={rvtVMFilter} onChange={e=>setRvtVMFilter(e.target.value)}
                        placeholder="Search VMs…"
                        style={{flex:1,padding:"5px 10px",borderRadius:6,border:\`1px solid \${p.border}\`,background:p.card,color:p.text,fontSize:12}}/>
                      <span style={{fontSize:12,color:p.textMute,whiteSpace:"nowrap"}}>
                        {vmData?.vms?.length||0} VMs
                      </span>
                    </div>
                    {vmData?(
                      <div style={{overflowX:"auto",maxHeight:400,overflowY:"auto"}}>
                        <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                          <thead>
                            <tr style={{background:p.border}}>
                              {["VM Name","Power","CPUs","RAM (GB)","IP","OS","Cluster","Host","Datacenter"].map(h=>(
                                <th key={h} style={{padding:"5px 8px",textAlign:"left",color:p.textMute,fontWeight:600,whiteSpace:"nowrap"}}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {(vmData.vms||[])
                              .filter(v=>!rvtVMFilter||
                                v.name?.toLowerCase().includes(rvtVMFilter.toLowerCase())||
                                v.primary_ip?.includes(rvtVMFilter)||
                                v.os_tools?.toLowerCase().includes(rvtVMFilter.toLowerCase())||
                                v.cluster?.toLowerCase().includes(rvtVMFilter.toLowerCase()))
                              .slice(0,200)
                              .map((v,i)=>{
                                const pwrColor=v.powerstate==="poweredOn"?"#10b981":v.powerstate==="suspended"?"#f59e0b":"#ef4444";
                                return(
                                  <tr key={i} style={{borderBottom:\`1px solid \${p.border}\`}}>
                                    <td style={{padding:"4px 8px",color:p.text,maxWidth:200,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.name}</td>
                                    <td style={{padding:"4px 8px"}}><span style={{color:pwrColor,fontWeight:600,fontSize:10}}>{v.powerstate==="poweredOn"?"ON":v.powerstate==="poweredOff"?"OFF":v.powerstate||"?"}</span></td>
                                    <td style={{padding:"4px 8px",color:p.textMute}}>{v.cpus||"—"}</td>
                                    <td style={{padding:"4px 8px",color:p.textMute}}>{v.memory_mb?Math.round(v.memory_mb/1024):"—"}</td>
                                    <td style={{padding:"4px 8px",color:p.accent,fontFamily:"monospace"}}>{v.primary_ip||"—"}</td>
                                    <td style={{padding:"4px 8px",color:p.textMute,maxWidth:180,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.os_tools||v.os_config||"—"}</td>
                                    <td style={{padding:"4px 8px",color:p.textMute}}>{v.cluster||"—"}</td>
                                    <td style={{padding:"4px 8px",color:p.textMute,maxWidth:140,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.host||"—"}</td>
                                    <td style={{padding:"4px 8px",color:p.textMute}}>{v.datacenter||"—"}</td>
                                  </tr>
                                );
                              })}
                          </tbody>
                        </table>
                        {(vmData.vms||[]).filter(v=>!rvtVMFilter||v.name?.toLowerCase().includes(rvtVMFilter.toLowerCase())||v.primary_ip?.includes(rvtVMFilter)||v.os_tools?.toLowerCase().includes(rvtVMFilter.toLowerCase())||v.cluster?.toLowerCase().includes(rvtVMFilter.toLowerCase())).length>200&&(
                          <div style={{textAlign:"center",padding:8,color:p.textMute,fontSize:11}}>Showing first 200 results. Use search to filter.</div>
                        )}
                      </div>
                    ):<div style={{textAlign:"center",padding:20,color:p.textMute}}>⟳ Loading VM list…</div>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
`;

const NEW_DS_CLOSE = RVTOOLS_BLOCK + `      )}
    </div>
  );
}

function VMsPage(`;

if (!src.includes(OLD_DS_CLOSE)) {
  console.error('ERROR: datastores closing block not found');
  const idx = src.indexOf('function VMsPage(');
  if(idx>=0) console.log('VMsPage ctx:', JSON.stringify(src.slice(idx-80,idx+10)));
  process.exit(1);
}
src = src.replace(OLD_DS_CLOSE, NEW_DS_CLOSE);
console.log('✓ Added RVTools render block');

// Write final file
fs.writeFileSync(path, src, 'utf8');
console.log('✓ App.jsx updated successfully');
