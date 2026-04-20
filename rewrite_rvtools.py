"""
rewrite_rvtools.py
Rewrites the RVTools tab with:
- Per-vCenter cards (enabled regardless of RVTools install status)
- Detail view when clicking a vCenter
- Export: CSV, Excel, PDF
"""
s = open('C:/caas-dashboard/frontend/src/App.jsx', encoding='utf-8').read()
lines = s.split('\n')
print(f"Loaded {len(lines)} lines")

# ── STEP 1: Add rvtDetailVC state ─────────────────────────────────────────────
vmfilter_idx = next(i for i,l in enumerate(lines) if 'rvtVMFilter, setRvtVMFilter' in l)
# Insert after that line
new_state = [
    '',
    '  const [rvtDetailVC, setRvtDetailVC] = useState(null);',
    '  const [rvtPowerFilter, setRvtPowerFilter] = useState("All");',
    '  const [rvtOSFilter, setRvtOSFilter] = useState("All");',
]
for i, l in enumerate(new_state):
    lines.insert(vmfilter_idx + 1 + i, l + '\r')
print(f"✓ Added rvtDetailVC state after line {vmfilter_idx+1}")

# ── STEP 2: Find and replace the RVTools render block ─────────────────────────
# Find block boundaries
start = next(i for i,l in enumerate(lines) if '{/* RVTools Reports tab */' in l)
# Find end: the closing '      )}' of vmTab==="rvtools"&&(...)
depth = 0
end = -1
in_block = False
for i in range(start, start + 800):
    for ch in (lines[i] if i < len(lines) else ''):
        if ch == '(':
            depth += 1
            in_block = True
        elif ch == ')':
            depth -= 1
            if in_block and depth <= 0:
                end = i
                break
    if end >= 0:
        break

print(f"Replacing lines {start+1} to {end+1}")

NEW_BLOCK = r"""
      {/* ── RVTools Reports tab ── */}
      {vmTab==="rvtools"&&(
        <div style={{display:"flex",flexDirection:"column",gap:16}}>

          {/* ── Detail view (vCenter selected) ── */}
          {rvtDetailVC?(()=>{
            const report = rvtReports.find(r=>r.vcenter_host===rvtDetailVC.host);
            const vmData = report ? rvtVMs[report.file] : null;
            const s = report?.summary||{};
            const vcName = rvtDetailVC.name;

            const filtered = (vmData?.vms||[]).filter(v=>{
              const q=(rvtVMFilter||"").toLowerCase();
              const matchText = !q||(v.name||"").toLowerCase().includes(q)||(v.primary_ip||"").includes(q)||(v.os_tools||"").toLowerCase().includes(q)||(v.cluster||"").toLowerCase().includes(q)||(v.host||"").toLowerCase().includes(q);
              const matchPwr = rvtPowerFilter==="All"||(rvtPowerFilter==="On"&&v.powerstate==="poweredOn")||(rvtPowerFilter==="Off"&&v.powerstate==="poweredOff")||(rvtPowerFilter==="Suspended"&&v.powerstate==="suspended");
              const matchOS = rvtOSFilter==="All"||(v.os_tools||v.os_config||"").toLowerCase().includes(rvtOSFilter.toLowerCase());
              return matchText&&matchPwr&&matchOS;
            });

            function exportCSV(){
              const hdr=["VM Name","Powerstate","CPUs","RAM GB","Primary IP","OS","Cluster","Host","Datacenter","Resource Pool","Folder","Annotation"];
              const rows=(vmData?.vms||[]).map(v=>[v.name,v.powerstate,v.cpus,v.memory_mb?Math.round(v.memory_mb/1024):"",v.primary_ip,v.os_tools||v.os_config,v.cluster,v.host,v.datacenter,v.resource_pool,v.folder,(v.annotation||"").replace(/"/g,"'")]);
              const csv=[hdr,...rows].map(r=>r.map(c=>`"${c||""}"`).join(",")).join("\n");
              const a=document.createElement("a");a.href="data:text/csv;charset=utf-8,"+encodeURIComponent(csv);a.download=vcName+"_VMs.csv";a.click();
            }

            function exportExcel(){
              const hdr=["VM Name","Powerstate","CPUs","RAM GB","Primary IP","OS","Cluster","Host","Datacenter","Resource Pool"];
              const rows=(vmData?.vms||[]).map(v=>[v.name,v.powerstate,v.cpus,v.memory_mb?Math.round(v.memory_mb/1024):"",v.primary_ip,v.os_tools||v.os_config,v.cluster,v.host,v.datacenter,v.resource_pool]);
              let t="<table><tr>"+hdr.map(h=>"<th>"+h+"</th>").join("")+"</tr>";
              rows.forEach(r=>{t+="<tr>"+r.map(c=>"<td>"+(c||"")+"</td>").join("")+"</tr>";});
              t+="</table>";
              const blob=new Blob(["\ufeff"+t],{type:"application/vnd.ms-excel;charset=utf-8"});
              const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=vcName+"_VMs.xls";a.click();
            }

            function exportPDF(){
              const w=window.open("","_blank");
              const hdr=["VM Name","Powerstate","CPUs","RAM GB","IP","OS","Cluster","Host","Datacenter"];
              let t=`<html><head><title>${vcName} VM Report</title><style>body{font-family:Arial,sans-serif;font-size:10px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:3px 6px;text-align:left}th{background:#3b82f6;color:#fff}tr:nth-child(even){background:#f3f4f6}h2{color:#1e293b}@media print{button{display:none}}</style></head><body>`;
              t+=`<h2>&#x1F4CA; ${vcName} — VM Report (${(vmData?.vms||[]).length} VMs)</h2>`;
              t+=`<p>Generated: ${new Date().toLocaleString()} &nbsp;|&nbsp; Powered On: ${s.powered_on||0} &nbsp;|&nbsp; Powered Off: ${s.powered_off||0} &nbsp;|&nbsp; Total vCPU: ${s.total_vcpu||0} &nbsp;|&nbsp; Total RAM: ${s.total_ram_gb||0}GB</p>`;
              t+="<table><tr>"+hdr.map(h=>"<th>"+h+"</th>").join("")+"</tr>";
              (vmData?.vms||[]).forEach(v=>{
                const r=[v.name,v.powerstate==="poweredOn"?"ON":v.powerstate==="poweredOff"?"OFF":"SUSPENDED",v.cpus,v.memory_mb?Math.round(v.memory_mb/1024):"",v.primary_ip,v.os_tools||v.os_config,v.cluster,v.host,v.datacenter];
                t+="<tr>"+r.map(c=>"<td>"+(c||"—")+"</td>").join("")+"</tr>";
              });
              t+="</table><br><button onclick='window.print()' style='padding:6px 16px;background:#3b82f6;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px'>&#x1F5A8; Print / Save as PDF</button></body></html>";
              w.document.write(t); w.document.close();
            }

            if(report&&!vmData){doLoadVMs(report.file);}

            const top5os=Object.entries(s.os_counts||{}).sort((a,b)=>b[1]-a[1]).slice(0,5);
            const osList=["All",...new Set((vmData?.vms||[]).map(v=>{const o=(v.os_tools||v.os_config||"").toLowerCase();return o.includes("windows")?"Windows":o.includes("rhel")||o.includes("red hat")?"RHEL":o.includes("centos")?"CentOS":o.includes("ubuntu")?"Ubuntu":o.includes("linux")?"Linux":"Other";}))];

            return(
              <div style={{display:"flex",flexDirection:"column",gap:14}}>
                {/* Header */}
                <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:10}}>
                  <div style={{display:"flex",alignItems:"center",gap:12}}>
                    <button onClick={()=>{setRvtDetailVC(null);setRvtVMFilter("");setRvtPowerFilter("All");setRvtOSFilter("All");}}
                      style={{background:"none",border:"1px solid "+p.border,color:p.textMute,borderRadius:6,padding:"4px 12px",cursor:"pointer",fontSize:13}}>
                      ← Back
                    </button>
                    <div>
                      <span style={{fontSize:18,fontWeight:700,color:p.text}}>📊 {vcName}</span>
                      <span style={{marginLeft:10,fontSize:12,color:p.textMute}}>{rvtDetailVC.host}</span>
                      {report&&<span style={{marginLeft:10,fontSize:11,color:p.textMute}}>Report: {new Date(report.modified).toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})}</span>}
                    </div>
                  </div>
                  {/* Export buttons */}
                  <div style={{display:"flex",gap:8}}>
                    <button onClick={exportCSV} disabled={!vmData}
                      style={{background:"#10b98122",border:"1px solid #10b981",color:"#10b981",borderRadius:6,padding:"5px 14px",fontSize:12,cursor:"pointer",fontWeight:600}}>
                      ⬇ CSV
                    </button>
                    <button onClick={exportExcel} disabled={!vmData}
                      style={{background:"#3b82f622",border:"1px solid #3b82f6",color:"#3b82f6",borderRadius:6,padding:"5px 14px",fontSize:12,cursor:"pointer",fontWeight:600}}>
                      ⬇ Excel
                    </button>
                    <button onClick={exportPDF} disabled={!vmData}
                      style={{background:"#ef444422",border:"1px solid #ef4444",color:"#ef4444",borderRadius:6,padding:"5px 14px",fontSize:12,cursor:"pointer",fontWeight:600}}>
                      🖨 PDF
                    </button>
                    {rvtStatus?.installed&&<button onClick={()=>doRunRVTools(rvtDetailVC.host)} disabled={!!rvtRunning[rvtDetailVC.host]}
                      style={{background:"#f9741622",border:"1px solid #f97316",color:"#f97316",borderRadius:6,padding:"5px 14px",fontSize:12,cursor:"pointer",fontWeight:600}}>
                      {rvtRunning[rvtDetailVC.host]?"⟳ Running…":"⟳ Refresh Data"}
                    </button>}
                  </div>
                </div>

                {/* KPI row */}
                {report?(
                  <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(110px,1fr))",gap:8}}>
                    {[
                      {label:"Total VMs",    value:s.total_vms||0,    color:"#3b82f6"},
                      {label:"Powered On",   value:s.powered_on||0,   color:"#10b981"},
                      {label:"Powered Off",  value:s.powered_off||0,  color:"#ef4444"},
                      {label:"Templates",    value:s.templates||0,    color:"#8b5cf6"},
                      {label:"Total vCPU",   value:s.total_vcpu||0,   color:"#f59e0b"},
                      {label:"RAM GB (on)",  value:s.total_ram_gb||0, color:"#06b6d4"},
                      {label:"Prov. TB",     value:s.total_provisioned_tb||0, color:"#a78bfa"},
                      {label:"ESXi Hosts",   value:s.total_hosts||0,  color:"#64748b"},
                    ].map(k=>(
                      <div key={k.label} style={{background:p.card,border:"1px solid "+p.border,borderRadius:8,padding:"8px 10px",textAlign:"center"}}>
                        <div style={{fontSize:19,fontWeight:700,color:k.color}}>{k.value}</div>
                        <div style={{fontSize:10,color:p.textMute,marginTop:2}}>{k.label}</div>
                      </div>
                    ))}
                  </div>
                ):null}

                {/* OS + Top consumers */}
                {report&&(
                  <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
                    {top5os.length>0&&(
                      <div className="card">
                        <div style={{fontSize:12,fontWeight:600,color:p.textMute,marginBottom:8}}>OS Distribution</div>
                        {top5os.map(([os,cnt])=>{
                          const pct=s.total_vms>0?Math.round((cnt/s.total_vms)*100):0;
                          return(<div key={os} style={{marginBottom:5}}>
                            <div style={{display:"flex",justifyContent:"space-between",fontSize:11,marginBottom:2}}>
                              <span style={{color:p.text,maxWidth:160,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{os}</span>
                              <span style={{color:p.textMute}}>{cnt} ({pct}%)</span>
                            </div>
                            <div style={{height:5,borderRadius:3,background:p.border}}><div style={{height:"100%",borderRadius:3,background:"#3b82f6",width:pct+"%"}}/></div>
                          </div>);
                        })}
                      </div>
                    )}
                    {(s.top10_by_ram||[]).length>0&&(
                      <div className="card">
                        <div style={{fontSize:12,fontWeight:600,color:p.textMute,marginBottom:8}}>Top VMs by RAM</div>
                        {(s.top10_by_ram||[]).slice(0,8).map(v=>(
                          <div key={v.name} style={{display:"flex",justifyContent:"space-between",fontSize:11,marginBottom:4}}>
                            <span style={{color:p.text,maxWidth:170,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.name}</span>
                            <span style={{color:p.textMute,whiteSpace:"nowrap"}}>{v.ram_gb}GB · {v.cpus}vCPU</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Filters + VM table */}
                <div className="card" style={{padding:0,overflow:"hidden"}}>
                  <div style={{padding:"10px 14px",borderBottom:"1px solid "+p.border,display:"flex",gap:8,flexWrap:"wrap",alignItems:"center"}}>
                    <input value={rvtVMFilter} onChange={e=>setRvtVMFilter(e.target.value)}
                      placeholder="Search VM, IP, OS, cluster, host…"
                      style={{flex:1,minWidth:180,padding:"5px 10px",borderRadius:6,border:"1px solid "+p.border,background:p.card,color:p.text,fontSize:12}}/>
                    {["All","On","Off","Suspended"].map(f=>(
                      <button key={f} onClick={()=>setRvtPowerFilter(f)}
                        style={{padding:"4px 10px",borderRadius:6,border:"1px solid "+(rvtPowerFilter===f?"#3b82f6":p.border),
                          background:rvtPowerFilter===f?"#3b82f622":"transparent",
                          color:rvtPowerFilter===f?"#3b82f6":p.textMute,fontSize:11,cursor:"pointer"}}>
                        {f==="All"?"⚡ All":f==="On"?"🟢 On":f==="Off"?"🔴 Off":"🟡 Suspended"}
                      </button>
                    ))}
                    <select value={rvtOSFilter} onChange={e=>setRvtOSFilter(e.target.value)}
                      style={{padding:"4px 8px",borderRadius:6,border:"1px solid "+p.border,background:p.card,color:p.text,fontSize:11}}>
                      {osList.map(o=><option key={o}>{o}</option>)}
                    </select>
                    <span style={{fontSize:11,color:p.textMute,whiteSpace:"nowrap"}}>
                      {filtered.length} / {(vmData?.vms||[]).length} VMs
                    </span>
                  </div>
                  {!report?(
                    <div style={{textAlign:"center",padding:40,color:p.textMute}}>
                      <div style={{fontSize:32,marginBottom:8}}>📂</div>
                      <div style={{fontSize:13}}>No report available for <b>{vcName}</b></div>
                      {rvtStatus?.installed
                        ?<div style={{marginTop:10}}><button onClick={()=>doRunRVTools(rvtDetailVC.host)} disabled={!!rvtRunning[rvtDetailVC.host]}
                          style={{background:"#f9741622",border:"1px solid #f97316",color:"#f97316",borderRadius:6,padding:"6px 16px",fontSize:12,cursor:"pointer"}}>
                          ▶ Run RVTools for {vcName}
                        </button></div>
                        :<div style={{fontSize:12,color:p.textMute,marginTop:8}}>Install RVTools or place an XLSX export on the Desktop / in C:\caas-dashboard\rvtools_exports\</div>}
                    </div>
                  ):!vmData?(
                    <div style={{textAlign:"center",padding:40,color:p.textMute}}>⟳ Loading VM data…</div>
                  ):(
                    <div style={{overflowX:"auto",maxHeight:520,overflowY:"auto"}}>
                      <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                        <thead><tr style={{background:p.border,position:"sticky",top:0,zIndex:1}}>
                          {["#","VM Name","Power","CPUs","RAM GB","Primary IP","OS","Cluster","Host","Datacenter","Resource Pool"].map(h=>(
                            <th key={h} style={{padding:"5px 8px",textAlign:"left",color:p.textMute,fontWeight:600,whiteSpace:"nowrap"}}>{h}</th>
                          ))}
                        </tr></thead>
                        <tbody>
                          {filtered.slice(0,500).map((v,i)=>{
                            const pwrClr=v.powerstate==="poweredOn"?"#10b981":v.powerstate==="suspended"?"#f59e0b":"#ef4444";
                            const pwrLabel=v.powerstate==="poweredOn"?"ON":v.powerstate==="poweredOff"?"OFF":"SUSP";
                            return(<tr key={i} style={{borderBottom:"1px solid "+p.border}}>
                              <td style={{padding:"4px 8px",color:p.textMute,textAlign:"center"}}>{i+1}</td>
                              <td style={{padding:"4px 8px",color:p.text,maxWidth:180,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap",fontWeight:500}}>{v.name}</td>
                              <td style={{padding:"4px 8px"}}><span style={{color:pwrClr,fontWeight:700,fontSize:10,background:pwrClr+"22",padding:"1px 5px",borderRadius:3}}>{pwrLabel}</span></td>
                              <td style={{padding:"4px 8px",color:p.textMute,textAlign:"center"}}>{v.cpus||"—"}</td>
                              <td style={{padding:"4px 8px",color:p.textMute,textAlign:"center"}}>{v.memory_mb?Math.round(v.memory_mb/1024):"—"}</td>
                              <td style={{padding:"4px 8px",color:"#60a5fa",fontFamily:"monospace",fontSize:10}}>{v.primary_ip||"—"}</td>
                              <td style={{padding:"4px 8px",color:p.textMute,maxWidth:160,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.os_tools||v.os_config||"—"}</td>
                              <td style={{padding:"4px 8px",color:p.textMute,maxWidth:120,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.cluster||"—"}</td>
                              <td style={{padding:"4px 8px",color:p.textMute,maxWidth:130,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.host||"—"}</td>
                              <td style={{padding:"4px 8px",color:p.textMute}}>{v.datacenter||"—"}</td>
                              <td style={{padding:"4px 8px",color:p.textMute,maxWidth:130,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{v.resource_pool||"—"}</td>
                            </tr>);
                          })}
                        </tbody>
                      </table>
                      {filtered.length>500&&<div style={{textAlign:"center",padding:8,color:p.textMute,fontSize:11}}>Showing 500 of {filtered.length} — use filters to narrow down</div>}
                    </div>
                  )}
                </div>
              </div>
            );
          })():(
            /* ── vCenter list view ── */
            <div style={{display:"flex",flexDirection:"column",gap:14}}>
              {/* Header */}
              <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",flexWrap:"wrap",gap:8}}>
                <div>
                  <span style={{fontSize:20,fontWeight:700,color:p.text}}>📊 RVTools Reports</span>
                  <span style={{marginLeft:12,fontSize:12,color:p.textMute}}>
                    {rvtStatus?.installed
                      ?<span style={{color:"#10b981"}}> ● RVTools installed</span>
                      :<span style={{color:"#f59e0b"}}> ⚠ RVTools not installed — showing existing reports</span>}
                  </span>
                </div>
                <div style={{display:"flex",gap:8}}>
                  <button className="btn btn-primary btn-sm" onClick={loadRVToolsReports} disabled={rvtLoading}>
                    {rvtLoading?"⟳ Scanning…":"⟳ Refresh"}
                  </button>
                  {rvtStatus?.installed&&(
                    <button className="btn btn-success btn-sm" onClick={doRunAllRVTools} disabled={rvtRunAll}>
                      {rvtRunAll?"⟳ Running all…":"▶ Run All vCenters"}
                    </button>
                  )}
                </div>
              </div>

              {rvtMsg&&<div style={{padding:"10px 14px",borderRadius:8,background:rvtMsg.ok?"#10b98122":"#ef444422",border:"1px solid "+(rvtMsg.ok?"#10b98166":"#ef444466"),color:rvtMsg.ok?"#10b981":"#ef4444",fontSize:13}}>{rvtMsg.ok?"✓":"✗"} {rvtMsg.text}</div>}

              {rvtLoading&&<div style={{textAlign:"center",padding:40,color:p.textMute}}>⟳ Scanning for reports…</div>}

              {/* Per-vCenter cards */}
              {!rvtLoading&&(
                <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(300px,1fr))",gap:14}}>
                  {(rvtStatus?.vcenters||[]).map(vc=>{
                    const report=rvtReports.find(r=>r.vcenter_host===vc.host);
                    const s=report?.summary||{};
                    const hasData=!!report;
                    return(
                      <div key={vc.host} className="card" style={{border:"1px solid "+(hasData?"#3b82f655":p.border),cursor:"pointer",transition:"border 0.15s"}}
                        onClick={()=>{setRvtDetailVC(vc);if(report&&!rvtVMs[report.file])doLoadVMs(report.file);}}>
                        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:10}}>
                          <div>
                            <div style={{fontSize:15,fontWeight:700,color:p.text}}>{vc.name}</div>
                            <div style={{fontSize:11,color:p.textMute,marginTop:2}}>{vc.host}</div>
                          </div>
                          <div style={{textAlign:"right"}}>
                            {hasData
                              ?<span style={{fontSize:10,color:"#10b981",background:"#10b98122",padding:"2px 8px",borderRadius:4,fontWeight:600}}>● REPORT AVAILABLE</span>
                              :<span style={{fontSize:10,color:"#94a3b8",background:p.border+"44",padding:"2px 8px",borderRadius:4}}>NO REPORT</span>}
                          </div>
                        </div>
                        {hasData?(
                          <>
                            <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:6,marginBottom:10}}>
                              {[
                                {l:"Total VMs",v:s.total_vms||0,c:"#3b82f6"},
                                {l:"Powered On",v:s.powered_on||0,c:"#10b981"},
                                {l:"vCPU",v:s.total_vcpu||0,c:"#f59e0b"},
                                {l:"RAM GB",v:s.total_ram_gb||0,c:"#06b6d4"},
                              ].map(k=>(
                                <div key={k.l} style={{background:p.border+"44",borderRadius:6,padding:"5px 6px",textAlign:"center"}}>
                                  <div style={{fontSize:16,fontWeight:700,color:k.c}}>{k.v}</div>
                                  <div style={{fontSize:9,color:p.textMute}}>{k.l}</div>
                                </div>
                              ))}
                            </div>
                            <div style={{fontSize:11,color:p.textMute}}>
                              🗓 {new Date(report.modified).toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})}
                              &nbsp;·&nbsp;{report.size_kb}KB
                              {(s.clusters||[]).length>0&&<span>&nbsp;·&nbsp;{(s.clusters||[]).length} cluster{(s.clusters||[]).length!==1?"s":""}</span>}
                            </div>
                          </>
                        ):(
                          <div style={{fontSize:12,color:p.textMute,marginTop:4}}>
                            {rvtStatus?.installed
                              ?<span>Click to run RVTools and generate a report</span>
                              :<span>Place an XLSX export for this vCenter in <code>C:\caas-dashboard\rvtools_exports\</code></span>}
                          </div>
                        )}
                        <div style={{marginTop:10,display:"flex",justifyContent:"flex-end",gap:8,alignItems:"center"}} onClick={e=>e.stopPropagation()}>
                          {rvtStatus?.installed&&(
                            <button disabled={!!rvtRunning[vc.host]} onClick={e=>{e.stopPropagation();doRunRVTools(vc.host);}}
                              style={{background:"#f9741622",border:"1px solid #f97316",color:"#f97316",borderRadius:6,padding:"3px 10px",fontSize:11,cursor:rvtRunning[vc.host]?"not-allowed":"pointer"}}>
                              {rvtRunning[vc.host]?"⟳ Running…":"⟳ Run"}
                            </button>
                          )}
                          <button onClick={e=>{e.stopPropagation();setRvtDetailVC(vc);if(report&&!rvtVMs[report.file])doLoadVMs(report.file);}}
                            style={{background:hasData?"#3b82f622":"#94a3b822",border:"1px solid "+(hasData?"#3b82f6":p.border),color:hasData?"#3b82f6":p.textMute,borderRadius:6,padding:"3px 12px",fontSize:11,cursor:"pointer",fontWeight:600}}>
                            {hasData?"▶ View VMs →":"Open →"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}"""

new_block_lines = NEW_BLOCK.split('\n')

# Replace old block
del lines[start:end+1]
for i, l in enumerate(new_block_lines):
    lines.insert(start + i, (l + '\r') if not l.endswith('\r') else l)

print(f"✓ Replaced render block with {len(new_block_lines)} lines")
print(f"  File now: {len(lines)} lines")

# Verify
new_start = next((i for i,l in enumerate(lines) if 'RVTools Reports tab' in l), -1)
new_vmsp  = next((i for i,l in enumerate(lines) if 'function VMsPage(' in l and 'vms,' in l), -1)
print(f"  RVTools block at line {new_start+1}")
print(f"  VMsPage at line {new_vmsp+1}")

out = '\n'.join(lines)
with open('C:/caas-dashboard/frontend/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(out)
print("\n✅ Done — App.jsx saved")
