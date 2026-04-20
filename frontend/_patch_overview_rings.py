"""
Patch EnvironmentChartsPanel in App.jsx:
1. Add awsData + hvData props
2. Side-by-side layout: Heatmap (left 50%) | VMware Gauges (right 50%)
3. 5 platform rings in one horizontal row: VMware | OpenShift | Nutanix | AWS | Hyper-V
4. Wire new props at the call site (line 1227)
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

APP = 'frontend/src/App.jsx'
content = open(APP, encoding='utf-8').read()

if 'awsEC2Running' in content:
    print("Already patched — skipping")
    exit(0)

# ── 1. Update call site to pass awsData + hvData ──────────────────────────
OLD_CALL = '<EnvironmentChartsPanel summary={summary} ocpData={ocpData} nutData={nutData} p={p}/>'
NEW_CALL = '<EnvironmentChartsPanel summary={summary} ocpData={ocpData} nutData={nutData} liveHealth={liveHealth} p={p}/>'

if OLD_CALL not in content:
    print("ERROR: call site not found")
    exit(1)
content = content.replace(OLD_CALL, NEW_CALL, 1)
print("Step 1: call site updated")

# ── 2. Replace function signature ─────────────────────────────────────────
OLD_SIG = 'function EnvironmentChartsPanel({summary, ocpData, nutData, p}){'
NEW_SIG = 'function EnvironmentChartsPanel({summary, ocpData, nutData, liveHealth, p}){'

if OLD_SIG not in content:
    print("ERROR: function signature not found")
    exit(1)
content = content.replace(OLD_SIG, NEW_SIG, 1)
print("Step 2: function signature updated")

# ── 3. Find the block to replace ──────────────────────────────────────────
# We need to replace everything from the grid div (line 663) through the heatmap closing div (line 798 closing </div> of the component return)
# Use clear anchors

OLD_RINGS_HEATMAP_START = '      <div style={{padding:"18px 20px",display:"grid",gridTemplateColumns:"1fr 1fr 1fr 2fr",gap:24,alignItems:"start"}}>'
OLD_HEATMAP_END = '''      </div>
    </div>
  );
}

// ─── OVERVIEW ──────────────────────────────────────────────────'''

if OLD_RINGS_HEATMAP_START not in content:
    print("ERROR: rings/heatmap start not found")
    exit(1)

# Find the chunk between OLD_RINGS_HEATMAP_START and OLD_HEATMAP_END
start_idx = content.find(OLD_RINGS_HEATMAP_START)
end_marker = '      </div>\n    </div>\n  );\n}\n\n// ─── OVERVIEW'
end_idx = content.find(end_marker)
if end_idx == -1:
    print("ERROR: end marker not found")
    exit(1)

NEW_CONTENT = '''      {/* ── AWS + HyperV derived values ── */}
      {(()=>{
        const awsEC2Total   = liveHealth?.awsEC2Total   || 0;
        const awsEC2Running = liveHealth?.awsEC2Running || 0;
        const awsEC2Stopped = Math.max(0, awsEC2Total - awsEC2Running);
        const awsConn       = liveHealth?.awsConnected  || false;
        const awsAcct       = liveHealth?.awsAccount    || "";
        const awsRegion     = liveHealth?.awsRegion     || "ap-south-1";
        const hvHostCt      = liveHealth?.hvHosts       || 0;
        const hvVMsTot      = liveHealth?.hvVMs         || 0;
        const hvVMsRun      = liveHealth?.hvVMsRunning  || 0;
        const hvVMsOff      = Math.max(0, hvVMsTot - hvVMsRun);

        // ── OCP derived ──
        const ocpClusters = (ocpData?.clusters||[]).length;
        const ocpPodsRun  = Object.values(ocpData?.overviews||{}).reduce((a,ov)=>a+(ov?.pods_summary?.running||0),0);
        const ocpPodsTot  = Object.values(ocpData?.overviews||{}).reduce((a,ov)=>a+(ov?.pods_summary?.total||0),0);
        const ocpNodesTot = Object.values(ocpData?.overviews||{}).reduce((a,ov)=>a+(ov?.nodes_summary?.total||0),0);
        const ocpNodesRdy = Object.values(ocpData?.overviews||{}).reduce((a,ov)=>a+(ov?.nodes_summary?.ready||0),0);
        // ── Nutanix derived ──
        const nutPCs    = (nutData?.pcs||[]).length;
        const nutVMsRun = Object.values(nutData?.overviews||{}).reduce((a,ov)=>a+(ov?.vms?.running||0),0);
        const nutVMsTot = Object.values(nutData?.overviews||{}).reduce((a,ov)=>a+(ov?.vms?.total||0),0);
        const nutHosts  = Object.values(nutData?.overviews||{}).reduce((a,ov)=>a+(ov?.hosts||0),0);
        // ── VMware derived ──
        const vmRunning = summary?.running_vms || 0;
        const vmStopped = summary?.stopped_vms || 0;
        const vmTotal   = summary?.total_vms   || 0;
        const cpuPct  = summary?.cpu?.total_mhz   > 0 ? Math.round((summary.cpu.used_mhz   / summary.cpu.total_mhz)   * 100) : 0;
        const ramPct  = summary?.ram?.total_gb    > 0 ? Math.round((summary.ram.used_gb    / summary.ram.total_gb)    * 100) : 0;
        const diskPct = summary?.storage?.total_gb > 0 ? Math.round((summary.storage.used_gb / summary.storage.total_gb) * 100) : 0;

        // ── Reusable not-configured placeholder ──
        function NotCfg({icon, label}){
          return(
            <div style={{height:130,display:"flex",alignItems:"center",justifyContent:"center",
              flexDirection:"column",gap:8,color:p.textMute,fontSize:11,textAlign:"center",opacity:.5}}>
              <div style={{fontSize:32}}>{icon}</div>
              <div style={{fontWeight:600}}>{label}</div>
            </div>
          );
        }

        // ── Reusable legend dot ──
        function LegDot({color,label}){
          return(
            <div style={{display:"flex",alignItems:"center",gap:4,color:p.textSub,fontSize:10}}>
              <div style={{width:8,height:8,borderRadius:2,background:color,flexShrink:0}}/>
              <span>{label}</span>
            </div>
          );
        }

        // ── Reusable stat row ──
        function StatRow({label,val,color}){
          return(
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",
              padding:"3px 0",borderBottom:`1px solid ${p.border}40`}}>
              <span style={{fontSize:10,color:p.textMute}}>{label}</span>
              <span style={{fontSize:11,fontWeight:700,color:color||p.text}}>{val}</span>
            </div>
          );
        }

        return(<>
          {/* ════ ROW 1: Heatmap (left 50%) | VMware Gauges (right 50%) ════ */}
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:0,borderTop:`1px solid ${p.border}`}}>

            {/* LEFT — Cross-Platform Resource Heatmap */}
            <div style={{padding:"14px 20px 16px",borderRight:`1px solid ${p.border}`,
              background:`linear-gradient(90deg,${p.accent}06,${p.cyan}04,transparent)`}}>
              <div style={{fontSize:10,fontWeight:800,letterSpacing:"1.4px",textTransform:"uppercase",
                color:p.textMute,marginBottom:10,display:"flex",alignItems:"center",gap:6}}>
                <span>📊</span> Cross-Platform Resource Heatmap
              </div>
              <div style={{display:"flex",flexDirection:"column",gap:7}}>
                {(()=>{
                  const rows=[
                    {label:"VMware • CPU",     pct:cpuPct,  color:"#3b82f6",detail:`${Math.round((summary?.cpu?.used_mhz||0)/1000)}/${Math.round((summary?.cpu?.total_mhz||0)/1000)} GHz`},
                    {label:"VMware • RAM",     pct:ramPct,  color:"#8b5cf6",detail:`${fmtGB(summary?.ram?.used_gb||0)} / ${fmtGB(summary?.ram?.total_gb||0)}`},
                    {label:"VMware • Storage", pct:diskPct, color:"#06b6d4",detail:`${fmtGB(summary?.storage?.used_gb||0)} / ${fmtGB(summary?.storage?.total_gb||0)}`},
                    ...(ocpClusters>0&&ocpPodsTot>0?[{label:"OCP • Pods",  pct:Math.round(ocpPodsRun/ocpPodsTot*100),  color:"#ef4444",detail:`${ocpPodsRun}/${ocpPodsTot} running`}]:[]),
                    ...(ocpNodesTot>0?[{label:"OCP • Nodes", pct:Math.round(ocpNodesRdy/ocpNodesTot*100), color:"#f97316",detail:`${ocpNodesRdy}/${ocpNodesTot} ready`,inv:true}]:[]),
                    ...(nutPCs>0&&nutVMsTot>0?[{label:"Nutanix • VMs",pct:Math.round(nutVMsRun/nutVMsTot*100), color:"#22c55e",detail:`${nutVMsRun}/${nutVMsTot} running`,inv:true}]:[]),
                    ...(awsConn&&awsEC2Total>0?[{label:"AWS • EC2", pct:Math.round(awsEC2Running/awsEC2Total*100), color:"#FF9900",detail:`${awsEC2Running}/${awsEC2Total} running`,inv:true}]:[]),
                    ...(hvHostCt>0&&hvVMsTot>0?[{label:"Hyper-V • VMs", pct:Math.round(hvVMsRun/hvVMsTot*100), color:"#00ADEF",detail:`${hvVMsRun}/${hvVMsTot} running`,inv:true}]:[]),
                  ];
                  return rows.map(({label,pct,color,detail,inv})=>{
                    const sp=Math.min(100,Math.max(0,pct||0));
                    const bc=inv?(sp>=80?"#10b981":sp>=50?"#f59e0b":"#ef4444"):(sp>=85?"#ef4444":sp>=65?"#f59e0b":color);
                    return(
                      <div key={label} style={{display:"flex",alignItems:"center",gap:8}}>
                        <div style={{minWidth:130,fontSize:10,fontWeight:600,color:p.textSub,textAlign:"right"}}>{label}</div>
                        <div style={{flex:1,height:9,borderRadius:5,background:`${p.border}70`,overflow:"hidden"}}>
                          <div style={{width:`${sp}%`,height:"100%",borderRadius:5,
                            background:`linear-gradient(90deg,${bc}99,${bc})`,
                            boxShadow:`0 0 5px ${bc}50`,transition:"width .6s ease"}}/>
                        </div>
                        <div style={{minWidth:34,fontSize:10,fontWeight:800,color:bc,fontFamily:"monospace",textAlign:"right"}}>{sp}%</div>
                        <div style={{minWidth:130,fontSize:9,color:p.textMute,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{detail}</div>
                      </div>
                    );
                  });
                })()}
              </div>
            </div>

            {/* RIGHT — VMware Capacity Utilization */}
            <div style={{padding:"14px 20px 16px",background:`linear-gradient(90deg,${p.accent}04,transparent)`}}>
              <div style={{fontSize:10,fontWeight:800,letterSpacing:"1.4px",textTransform:"uppercase",
                color:"#3b82f6",marginBottom:12,display:"flex",alignItems:"center",gap:6}}>
                <span style={{padding:"2px 8px",borderRadius:16,background:"#3b82f615",border:"1px solid #3b82f625"}}>
                  🖥️ VMware Capacity Utilization
                </span>
              </div>
              <div style={{display:"flex",flexDirection:"column",gap:16}}>
                <UtilizationGauge p={p} label="CPU" icon="⚡" usedPct={cpuPct}
                  usedLabel={`${Math.round((summary?.cpu?.used_mhz||0)/1000)} GHz`}
                  freeLabel={`${Math.round((summary?.cpu?.free_mhz||0)/1000)} GHz`}
                  totalLabel={`${Math.round((summary?.cpu?.total_mhz||0)/1000)} GHz`}
                  color="#3b82f6"
                  extraRows={[["Hosts",`${summary?.connected_hosts||0} / ${summary?.total_hosts||0} online`]]}/>
                <UtilizationGauge p={p} label="Memory" icon="🧠" usedPct={ramPct}
                  usedLabel={fmtGB(summary?.ram?.used_gb||0)}
                  freeLabel={fmtGB(summary?.ram?.free_gb||0)}
                  totalLabel={fmtGB(summary?.ram?.total_gb||0)}
                  color="#8b5cf6"
                  extraRows={[["Running VMs",`${vmRunning} of ${vmTotal}`]]}/>
                <UtilizationGauge p={p} label="Storage" icon="💾" usedPct={diskPct}
                  usedLabel={fmtGB(summary?.storage?.used_gb||0)}
                  freeLabel={fmtGB(summary?.storage?.free_gb||0)}
                  totalLabel={fmtGB(summary?.storage?.total_gb||0)}
                  color="#06b6d4"
                  extraRows={[["Datastores","Aggregated across all"]]}/>
              </div>
            </div>
          </div>

          {/* ════ ROW 2: 5 Platform Rings ════ */}
          <div style={{borderTop:`1px solid ${p.border}`,
            display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:0}}>

            {/* ── 1. VMware ── */}
            <div style={{padding:"16px 14px",display:"flex",flexDirection:"column",alignItems:"center",gap:10,
              borderRight:`1px solid ${p.border}`}}>
              <div style={{fontSize:10,fontWeight:800,letterSpacing:"1.1px",textTransform:"uppercase",color:"#3b82f6",
                padding:"2px 10px",borderRadius:16,background:"#3b82f615",border:"1px solid #3b82f625"}}>🖥️ VMware</div>
              <RingChart p={p} size={120} stroke={14}
                centerVal={vmTotal} centerSub="VMs"
                label={`${summary?.total_hosts||0} Hosts`} sublabel={`${summary?.connected_hosts||0} connected`}
                segments={[
                  {label:"Running",value:vmRunning||1,color:"#10b981",detail:`${vmRunning} VMs powered on`},
                  {label:"Stopped",value:vmStopped||0,color:"#ef444450",detail:`${vmStopped} VMs off`},
                ]}/>
              <div style={{width:"100%",display:"flex",flexDirection:"column",gap:2,marginTop:2}}>
                <StatRow label="Running VMs" val={vmRunning} color="#10b981"/>
                <StatRow label="Stopped VMs" val={vmStopped} color="#ef4444"/>
                <StatRow label="Total Hosts"  val={summary?.total_hosts||0} color="#3b82f6"/>
                <StatRow label="CPU Used"     val={`${cpuPct}%`} color={cpuPct>85?"#ef4444":cpuPct>65?"#f59e0b":"#10b981"}/>
                <StatRow label="RAM Used"     val={`${ramPct}%`} color={ramPct>85?"#ef4444":ramPct>65?"#f59e0b":"#10b981"}/>
              </div>
              <div style={{display:"flex",gap:8,flexWrap:"wrap",justifyContent:"center"}}>
                <LegDot color="#10b981" label={`${vmRunning} Running`}/>
                <LegDot color="#ef4444" label={`${vmStopped} Off`}/>
              </div>
            </div>

            {/* ── 2. OpenShift ── */}
            <div style={{padding:"16px 14px",display:"flex",flexDirection:"column",alignItems:"center",gap:10,
              borderRight:`1px solid ${p.border}`}}>
              <div style={{fontSize:10,fontWeight:800,letterSpacing:"1.1px",textTransform:"uppercase",color:"#ef4444",
                padding:"2px 10px",borderRadius:16,background:"#ef444415",border:"1px solid #ef444425"}}>🔴 OpenShift</div>
              {ocpClusters===0
                ? <NotCfg icon="🔴" label="Not configured"/>
                : <RingChart p={p} size={120} stroke={14}
                    centerVal={ocpPodsRun} centerSub="Running"
                    label={`${ocpClusters} Cluster${ocpClusters!==1?"s":""}`} sublabel={`${ocpNodesTot} nodes`}
                    segments={[
                      {label:"Running Pods",value:ocpPodsRun||1,color:"#ef4444",detail:`${ocpPodsRun} pods running`},
                      {label:"Other Pods",value:Math.max(0,ocpPodsTot-ocpPodsRun)||0,color:"#f8717120",detail:`${ocpPodsTot-ocpPodsRun} other`},
                      {label:"Ready Nodes",value:ocpNodesRdy||0,color:"#fb923c",detail:`${ocpNodesRdy}/${ocpNodesTot} ready`},
                    ]}/>
              }
              {ocpClusters>0 && (
                <div style={{width:"100%",display:"flex",flexDirection:"column",gap:2,marginTop:2}}>
                  <StatRow label="Clusters"     val={ocpClusters}   color="#ef4444"/>
                  <StatRow label="Nodes Total"  val={ocpNodesTot}   color="#fb923c"/>
                  <StatRow label="Nodes Ready"  val={ocpNodesRdy}   color="#10b981"/>
                  <StatRow label="Pods Running" val={ocpPodsRun}    color="#ef4444"/>
                  <StatRow label="Pods Total"   val={ocpPodsTot}    color={p.text}/>
                </div>
              )}
              {ocpClusters>0&&<div style={{display:"flex",gap:8,flexWrap:"wrap",justifyContent:"center"}}>
                <LegDot color="#ef4444" label={`${ocpPodsRun} Pods`}/>
                <LegDot color="#fb923c" label={`${ocpNodesRdy} Nodes`}/>
              </div>}
            </div>

            {/* ── 3. Nutanix ── */}
            <div style={{padding:"16px 14px",display:"flex",flexDirection:"column",alignItems:"center",gap:10,
              borderRight:`1px solid ${p.border}`}}>
              <div style={{fontSize:10,fontWeight:800,letterSpacing:"1.1px",textTransform:"uppercase",color:"#22c55e",
                padding:"2px 10px",borderRadius:16,background:"#22c55e15",border:"1px solid #22c55e25"}}>🟩 Nutanix</div>
              {nutPCs===0
                ? <NotCfg icon="🟩" label="Not configured"/>
                : <RingChart p={p} size={120} stroke={14}
                    centerVal={nutVMsTot} centerSub="AHV VMs"
                    label={`${nutPCs} Prism Central${nutPCs!==1?"s":""}`} sublabel={`${nutHosts} hosts`}
                    segments={[
                      {label:"Running",value:nutVMsRun||1,color:"#22c55e",detail:`${nutVMsRun} VMs on`},
                      {label:"Stopped",value:Math.max(0,nutVMsTot-nutVMsRun)||0,color:"#22c55e30",detail:`${nutVMsTot-nutVMsRun} off`},
                    ]}/>
              }
              {nutPCs>0&&(
                <div style={{width:"100%",display:"flex",flexDirection:"column",gap:2,marginTop:2}}>
                  <StatRow label="Prism Centrals" val={nutPCs}                         color="#22c55e"/>
                  <StatRow label="AHV Hosts"      val={nutHosts}                       color="#4ade80"/>
                  <StatRow label="Running VMs"    val={nutVMsRun}                      color="#10b981"/>
                  <StatRow label="Stopped VMs"    val={Math.max(0,nutVMsTot-nutVMsRun)} color="#ef444480"/>
                  <StatRow label="Total VMs"      val={nutVMsTot}                      color={p.text}/>
                </div>
              )}
              {nutPCs>0&&<div style={{display:"flex",gap:8,flexWrap:"wrap",justifyContent:"center"}}>
                <LegDot color="#22c55e" label={`${nutVMsRun} Running`}/>
                <LegDot color="#4ade8050" label={`${nutVMsTot-nutVMsRun} Off`}/>
              </div>}
            </div>

            {/* ── 4. AWS ── */}
            <div style={{padding:"16px 14px",display:"flex",flexDirection:"column",alignItems:"center",gap:10,
              borderRight:`1px solid ${p.border}`}}>
              <div style={{fontSize:10,fontWeight:800,letterSpacing:"1.1px",textTransform:"uppercase",color:"#FF9900",
                padding:"2px 10px",borderRadius:16,background:"#FF990015",border:"1px solid #FF990025"}}>☁️ AWS</div>
              {!awsConn
                ? <NotCfg icon="☁️" label="Not configured"/>
                : <RingChart p={p} size={120} stroke={14}
                    centerVal={awsEC2Total} centerSub="EC2"
                    label={awsAcct||"Connected"} sublabel={awsRegion}
                    segments={[
                      {label:"Running",value:awsEC2Running||1,color:"#FF9900",detail:`${awsEC2Running} instances running`},
                      {label:"Stopped",value:awsEC2Stopped||0,color:"#FF990030",detail:`${awsEC2Stopped} stopped`},
                    ]}/>
              }
              {awsConn&&(
                <div style={{width:"100%",display:"flex",flexDirection:"column",gap:2,marginTop:2}}>
                  <StatRow label="EC2 Running"  val={awsEC2Running} color="#FF9900"/>
                  <StatRow label="EC2 Stopped"  val={awsEC2Stopped} color="#ef444480"/>
                  <StatRow label="Total EC2"    val={awsEC2Total}   color={p.text}/>
                  <StatRow label="Account"      val={awsAcct||"—"}  color="#FF9900"/>
                  <StatRow label="Region"       val={awsRegion||"—"} color={p.textSub}/>
                </div>
              )}
              {awsConn&&<div style={{display:"flex",gap:8,flexWrap:"wrap",justifyContent:"center"}}>
                <LegDot color="#FF9900" label={`${awsEC2Running} Running`}/>
                <LegDot color="#ef4444" label={`${awsEC2Stopped} Stopped`}/>
              </div>}
            </div>

            {/* ── 5. Hyper-V ── */}
            <div style={{padding:"16px 14px",display:"flex",flexDirection:"column",alignItems:"center",gap:10}}>
              <div style={{fontSize:10,fontWeight:800,letterSpacing:"1.1px",textTransform:"uppercase",color:"#00ADEF",
                padding:"2px 10px",borderRadius:16,background:"#00ADEF15",border:"1px solid #00ADEF25"}}>🪟 Hyper-V</div>
              {hvHostCt===0
                ? <NotCfg icon="🪟" label="Not configured"/>
                : <RingChart p={p} size={120} stroke={14}
                    centerVal={hvVMsTot} centerSub="VMs"
                    label={`${hvHostCt} Host${hvHostCt!==1?"s":""}`} sublabel={`${hvVMsRun} running`}
                    segments={[
                      {label:"Running",value:hvVMsRun||1,color:"#00ADEF",detail:`${hvVMsRun} VMs running`},
                      {label:"Off",value:hvVMsOff||0,color:"#00ADEF30",detail:`${hvVMsOff} VMs off`},
                    ]}/>
              }
              {hvHostCt>0&&(
                <div style={{width:"100%",display:"flex",flexDirection:"column",gap:2,marginTop:2}}>
                  <StatRow label="Hosts"       val={hvHostCt}  color="#00ADEF"/>
                  <StatRow label="Running VMs" val={hvVMsRun}  color="#10b981"/>
                  <StatRow label="Off VMs"     val={hvVMsOff}  color="#ef444480"/>
                  <StatRow label="Total VMs"   val={hvVMsTot}  color={p.text}/>
                  <StatRow label="Status"      val="Connected" color="#10b981"/>
                </div>
              )}
              {hvHostCt>0&&<div style={{display:"flex",gap:8,flexWrap:"wrap",justifyContent:"center"}}>
                <LegDot color="#00ADEF" label={`${hvVMsRun} Running`}/>
                <LegDot color="#00ADEF50" label={`${hvVMsOff} Off`}/>
              </div>}
            </div>

          </div>{/* end 5-rings row */}
        </>);
      })()}
    </div>
  );
}

// ─── OVERVIEW ──────────────────────────────────────────────────'''

# Splice it in
new_content = content[:start_idx] + NEW_CONTENT + content[end_idx + len(end_marker):]
open(APP, 'w', encoding='utf-8').write(new_content)
print("Step 3: rings + heatmap layout replaced")

# Verify
check = open(APP, encoding='utf-8').read()
for key in ['awsEC2Running','awsEC2Stopped','hvVMsTot','hvVMsRun','NotCfg','LegDot','StatRow',
            'gridTemplateColumns:"repeat(5,1fr)"','liveHealth?.awsEC2Total']:
    print(f"  {key}: {'OK' if key in check else 'MISSING'}")
