import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NEW_PAGE = r'''
function CapacityPage({hosts,datastores,vcenters,selectedVC,currentUser,onRefresh,loading,error,onRetry,ocpData,nutData,summaries,p}){
  const [platTab,setPlatTab]=useState("vmware");
  const canAct=currentUser?.role==="admin"||currentUser?.role==="operator";

  // ── IPAM ──
  const [ipamData,setIpamData]=useState(null);
  const [ipamLoading,setIpamLoading]=useState(false);

  // ── AWS ──
  const [awsStat,setAwsStat]=useState(null);
  const [awsDisc,setAwsDisc]=useState(null);
  const [awsCosts,setAwsCosts]=useState(null);
  const [awsS3,setAwsS3]=useState(null);
  const [awsLoading,setAwsLoading]=useState(false);

  // ── Hyper-V ──
  const [hvHosts,setHvHosts]=useState(null);
  const [hvVMsData,setHvVMsData]=useState(null);
  const [hvLoading,setHvLoading]=useState(false);

  // ── Storage ──
  const [storArrays,setStorArrays]=useState([]);
  const [storData,setStorData]=useState({});
  const [storLoading,setStorLoading]=useState(false);

  // ── Veeam/Backup ──
  const [veeamConns,setVeeamConns]=useState([]);
  const [veeamData,setVeeamData]=useState({});
  const [veeamLoading,setVeeamLoading]=useState(false);

  // ── Topology ──
  const [topoTarget,setTopoTarget]=useState(null);

  useEffect(()=>{
    setIpamLoading(true);
    fetchIPAMSubnets().then(d=>setIpamData(d)).catch(()=>setIpamData(null)).finally(()=>setIpamLoading(false));
  },[]);

  useEffect(()=>{
    if(platTab!=="aws") return;
    setAwsLoading(true);
    Promise.all([
      fetchAWSStatus().catch(()=>null),
      fetchAWSDiscovery("",false).catch(()=>null),
      fetchAWSCosts().catch(()=>null),
      fetchAWSS3().catch(()=>null),
    ]).then(([st,disc,costs,s3])=>{
      setAwsStat(st); setAwsDisc(disc); setAwsCosts(costs); setAwsS3(s3);
    }).finally(()=>setAwsLoading(false));
  },[platTab]);

  useEffect(()=>{
    if(platTab!=="hyperv") return;
    setHvLoading(true);
    Promise.all([
      fetchHVHosts().catch(()=>null),
      fetchHVVMs(null).catch(()=>null),
    ]).then(([hh,vms])=>{ setHvHosts(hh); setHvVMsData(vms); })
    .finally(()=>setHvLoading(false));
  },[platTab]);

  useEffect(()=>{
    if(platTab!=="storage") return;
    setStorLoading(true);
    fetchStorageArrays().then(async arrs=>{
      setStorArrays(arrs||[]);
      const entries = await Promise.all((arrs||[]).map(a=>
        fetchStorageArrayData(a.id).then(d=>([a.id,d])).catch(()=>([a.id,null]))
      ));
      setStorData(Object.fromEntries(entries));
    }).catch(()=>setStorArrays([])).finally(()=>setStorLoading(false));
  },[platTab]);

  useEffect(()=>{
    if(platTab!=="backup") return;
    setVeeamLoading(true);
    fetchVeeamConnections().then(async conns=>{
      setVeeamConns(conns||[]);
      const entries = await Promise.all((conns||[]).map(c=>
        fetchVeeamData(c.id).then(d=>([c.id,d])).catch(()=>([c.id,null]))
      ));
      setVeeamData(Object.fromEntries(entries));
    }).catch(()=>setVeeamConns([])).finally(()=>setVeeamLoading(false));
  },[platTab]);

  if(loading) return <LoadState msg="Loading capacity data…"/>;
  if(error)   return <ErrState msg={error} onRetry={onRetry}/>;

  // ── VMware aggregates ──
  const tR=hosts.reduce((s,h)=>s+h.ram_total_gb,0);
  const fR=hosts.reduce((s,h)=>s+h.ram_free_gb,0);
  const tD=datastores.reduce((s,d)=>s+d.total_gb,0);
  const fD=datastores.reduce((s,d)=>s+d.free_gb,0);
  const totalCPU=hosts.reduce((s,h)=>s+(h.cpu_total_mhz||0),0);
  const usedCPU=hosts.reduce((s,h)=>s+(h.cpu_used_mhz||0),0);
  const cpuPct=totalCPU>0?Math.round((usedCPU/totalCPU)*100):0;
  const ramPct=tR>0?Math.round(((tR-fR)/tR)*100):0;
  const dskPct=tD>0?Math.round(((tD-fD)/tD)*100):0;
  const totalVMs=summaries?summaries.reduce((s,v)=>s+(v.total_vms||0),0):0;
  const runVMs=summaries?summaries.reduce((s,v)=>s+(v.running_vms||0),0):0;

  // ── helpers ──
  const pctColor = pct => pct>=85?"#ef4444":pct>=65?"#f59e0b":"#10b981";
  const freeColor = pct => pct<=15?"#ef4444":pct<=35?"#f59e0b":"#10b981";

  function GaugeBar({pct,color,label,used,total,h=10}){
    const c=color||pctColor(pct);
    return(
      <div style={{marginBottom:12}}>
        <div style={{display:"flex",justifyContent:"space-between",marginBottom:4}}>
          <span style={{fontSize:15,fontWeight:600,color:p.textSub}}>{label}</span>
          <span style={{fontSize:15,fontWeight:800,color:c,fontFamily:"monospace"}}>{pct}%</span>
        </div>
        <div style={{height:h,borderRadius:h/2,background:`${p.border}60`,overflow:"hidden",position:"relative"}}>
          <div style={{position:"absolute",left:0,top:0,height:"100%",width:`${Math.min(100,pct)}%`,
            background:`linear-gradient(90deg,${c}99,${c})`,borderRadius:h/2,
            boxShadow:`0 0 8px ${c}60`,transition:"width 1s cubic-bezier(.4,0,.2,1)"}}/>
        </div>
        {(used||total)&&<div style={{display:"flex",justifyContent:"space-between",marginTop:3}}>
          <span style={{fontSize:14,color:p.textMute}}>Used: {used}</span>
          <span style={{fontSize:14,color:p.textMute}}>Total: {total}</span>
        </div>}
      </div>
    );
  }

  function StatCard({icon,label,value,sub,color,onClick}){
    return(
      <div onClick={onClick} style={{background:`${color||p.accent}08`,border:`1px solid ${color||p.accent}25`,
        borderRadius:12,padding:"14px 16px",cursor:onClick?"pointer":"default",transition:"all .15s",
        position:"relative",overflow:"hidden"}}
        onMouseEnter={e=>{if(onClick)e.currentTarget.style.background=`${color||p.accent}14`}}
        onMouseLeave={e=>{if(onClick)e.currentTarget.style.background=`${color||p.accent}08`}}>
        <div style={{position:"absolute",top:0,left:0,right:0,height:3,
          background:`linear-gradient(90deg,${color||p.accent}60,${color||p.accent})`}}/>
        <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:6}}>
          <span style={{fontSize:24}}>{icon}</span>
          <span style={{fontSize:14,fontWeight:700,color:p.textMute,textTransform:"uppercase",letterSpacing:".6px"}}>{label}</span>
        </div>
        <div style={{fontSize:28,fontWeight:900,color:color||p.accent,fontFamily:"monospace",lineHeight:1}}>{value}</div>
        {sub&&<div style={{fontSize:14,color:p.textMute,marginTop:4}}>{sub}</div>}
      </div>
    );
  }

  function SectionHeader({icon,title,color,badge}){
    return(
      <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:16,paddingBottom:10,
        borderBottom:`1px solid ${color||p.accent}30`}}>
        <div style={{width:36,height:36,borderRadius:10,background:`linear-gradient(135deg,${color||p.accent}30,${color||p.accent}10)`,
          border:`1px solid ${color||p.accent}30`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:20}}>{icon}</div>
        <div style={{flex:1}}>
          <div style={{fontWeight:800,fontSize:18,color:color||p.text,letterSpacing:"-.2px"}}>{title}</div>
        </div>
        {badge&&<span style={{fontSize:14,fontWeight:700,padding:"4px 12px",borderRadius:20,
          background:`${color||p.accent}15`,color:color||p.accent,border:`1px solid ${color||p.accent}30`}}>{badge}</span>}
      </div>
    );
  }

  function NotCfgBlock({icon,platform,msg}){
    return(
      <div style={{textAlign:"center",padding:"52px 20px",background:p.panelAlt,
        border:`1px dashed ${p.border}`,borderRadius:14,color:p.textMute}}>
        <div style={{fontSize:48,marginBottom:12,opacity:.35}}>{icon}</div>
        <div style={{fontWeight:700,fontSize:20,marginBottom:8,color:p.textSub}}>{platform} Not Configured</div>
        <div style={{fontSize:16}}>{msg||`Navigate to the ${platform} page to configure connections.`}</div>
      </div>
    );
  }

  const tabs=[
    {id:"vmware",   label:"VMware",     icon:"🖥️",  color:"#3b82f6",  badge:`${hosts.length} Hosts`},
    {id:"openshift",label:"OpenShift",  icon:"🔴",  color:"#ef4444",  badge:`${(ocpData?.clusters||[]).length} Clusters`},
    {id:"nutanix",  label:"Nutanix",    icon:"🟩",  color:"#22c55e",  badge:`${(nutData?.pcs||[]).length} Prism Centrals`},
    {id:"aws",      label:"AWS",        icon:"☁️",  color:"#FF9900",  badge:"EC2 · S3 · RDS"},
    {id:"hyperv",   label:"Hyper-V",    icon:"🪟",  color:"#00ADEF",  badge:"VMs · Hosts"},
    {id:"storage",  label:"Storage",    icon:"💾",  color:"#a855f7",  badge:"Arrays · Volumes"},
    {id:"backup",   label:"Backup",     icon:"🛡️",  color:"#10b981",  badge:"Veeam Jobs"},
    {id:"ipam",     label:"IPAM",       icon:"📡",  color:"#06b6d4",  badge:ipamData?`${ipamData.summary?.total_subnets||0} Subnets`:"—"},
  ];

  return(
    <div className="g-gap">
      {topoTarget&&<TopologyModal target={topoTarget} onClose={()=>setTopoTarget(null)} p={p}/>}

      {/* ══ HEADER BANNER ══ */}
      <div style={{background:`linear-gradient(135deg,${p.panel},${p.panelAlt})`,
        border:`1px solid ${p.border}`,borderRadius:14,padding:"16px 22px",
        display:"flex",alignItems:"center",gap:14,
        boxShadow:`0 4px 24px ${p.accent}08`}}>
        <div style={{width:48,height:48,borderRadius:14,flexShrink:0,
          background:`linear-gradient(135deg,${p.accent},${p.cyan})`,
          display:"flex",alignItems:"center",justifyContent:"center",fontSize:26,
          boxShadow:`0 4px 16px ${p.accent}40`}}>📊</div>
        <div style={{flex:1}}>
          <div style={{fontWeight:900,fontSize:22,color:p.text,letterSpacing:"-.3px"}}>Infrastructure Capacity</div>
          <div style={{fontSize:15,color:p.textMute,marginTop:2}}>All Platforms · Real-time Resource Utilisation Overview</div>
        </div>
        <div style={{display:"flex",gap:8}}>
          {[
            {label:"VMware Hosts",value:hosts.length,color:"#3b82f6"},
            {label:"OCP Clusters",value:(ocpData?.clusters||[]).length,color:"#ef4444"},
            {label:"Nutanix PCs",value:(nutData?.pcs||[]).length,color:"#22c55e"},
            {label:"Storage Arrays",value:storArrays.length||"—",color:"#a855f7"},
          ].map(b=>(
            <div key={b.label} style={{textAlign:"center",padding:"8px 14px",borderRadius:10,
              background:`${b.color}10`,border:`1px solid ${b.color}25`}}>
              <div style={{fontSize:20,fontWeight:900,color:b.color,fontFamily:"monospace"}}>{b.value}</div>
              <div style={{fontSize:13,color:p.textMute,whiteSpace:"nowrap"}}>{b.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ══ PLATFORM TAB STRIP ══ */}
      <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,overflow:"hidden"}}>
        <div style={{display:"grid",gridTemplateColumns:"repeat(8,1fr)"}}>
          {tabs.map((t,i)=>{
            const active=platTab===t.id;
            return(
              <button key={t.id} onClick={()=>setPlatTab(t.id)}
                style={{padding:"14px 8px",border:"none",
                  borderRight:i<7?`1px solid ${p.border}`:"none",
                  background:active?`${t.color}14`:"transparent",
                  cursor:"pointer",transition:"all .15s",
                  borderBottom:active?`3px solid ${t.color}`:`3px solid transparent`,
                  textAlign:"center",position:"relative"}}>
                {active&&<div style={{position:"absolute",top:0,left:0,right:0,height:2,
                  background:`linear-gradient(90deg,${t.color}40,${t.color},${t.color}40)`}}/>}
                <div style={{fontSize:22,marginBottom:4}}>{t.icon}</div>
                <div style={{fontWeight:700,fontSize:14,color:active?t.color:p.textSub,marginBottom:2}}>{t.label}</div>
                <div style={{fontSize:12,color:p.textMute,lineHeight:1.2}}>{t.badge}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════
          VMWARE TAB
      ══════════════════════════════════════════════════════════ */}
      {platTab==="vmware"&&(
        <div style={{display:"flex",flexDirection:"column",gap:16}}>
          <SectionHeader icon="🖥️" title="VMware vCenter — Capacity Overview" color="#3b82f6"
            badge={`${vcenters?.length||0} vCenter${vcenters?.length!==1?"s":""}`}/>

          {/* KPI tiles */}
          <div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:10}}>
            <StatCard icon="🖥️" label="ESXi Hosts"    value={hosts.length}             color="#3b82f6" sub={`${hosts.filter(h=>(h.status||"").toLowerCase()==="connected").length} connected`}/>
            <StatCard icon="💻" label="VMs Running"   value={`${runVMs}/${totalVMs}`}  color="#10b981" sub={`${totalVMs-runVMs} powered off`}/>
            <StatCard icon="⚡" label="CPU Used"      value={`${cpuPct}%`}             color={pctColor(cpuPct)} sub={`${Math.round(usedCPU/1000)} / ${Math.round(totalCPU/1000)} GHz`}/>
            <StatCard icon="🧠" label="RAM Used"      value={`${ramPct}%`}             color={pctColor(ramPct)} sub={`${fmtGB(tR-fR)} of ${fmtGB(tR)}`}/>
            <StatCard icon="💾" label="Datastores"    value={datastores.length}         color="#a855f7" sub={`${datastores.filter(d=>d.free_gb/d.total_gb<0.15).length} critical`}/>
            <StatCard icon="📦" label="Storage Used"  value={`${dskPct}%`}             color={pctColor(dskPct)} sub={`${fmtGB(tD-fD)} of ${fmtGB(tD)}`}/>
          </div>

          {/* Gauge bars */}
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
            <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,padding:"18px 20px"}}>
              <div style={{fontWeight:700,fontSize:16,color:"#3b82f6",marginBottom:14,display:"flex",alignItems:"center",gap:8}}>
                <span>📈</span> Resource Utilisation
              </div>
              <GaugeBar pct={cpuPct} label="CPU" used={`${Math.round(usedCPU/1000)} GHz`} total={`${Math.round(totalCPU/1000)} GHz`}/>
              <GaugeBar pct={ramPct} label="Memory (RAM)" used={fmtGB(tR-fR)} total={fmtGB(tR)}/>
              <GaugeBar pct={dskPct} label="Datastore Storage" used={fmtGB(tD-fD)} total={fmtGB(tD)}/>
            </div>
            <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,padding:"18px 20px"}}>
              <div style={{fontWeight:700,fontSize:16,color:"#3b82f6",marginBottom:14,display:"flex",alignItems:"center",gap:8}}>
                <span>🏥</span> Health by vCenter
              </div>
              {(vcenters||[]).length===0
                ?<div style={{color:p.textMute,fontSize:15,padding:"20px 0",textAlign:"center"}}>No vCenters configured</div>
                :(summaries||[]).map((s,idx)=>{
                  const vc=vcenters.find(v=>v.id===s.vcenter_id)||{};
                  const hostPct=s.total_hosts>0?Math.round((s.connected_hosts/s.total_hosts)*100):100;
                  const hc=hostPct<50?"#ef4444":hostPct<80?"#f59e0b":"#10b981";
                  return(
                    <div key={idx} style={{marginBottom:10,padding:"10px 12px",borderRadius:9,
                      background:`${hc}08`,border:`1px solid ${hc}20`,borderLeft:`3px solid ${hc}`}}>
                      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:6}}>
                        <span style={{fontWeight:700,fontSize:15,color:p.text}}>{vc.host||s.vcenter_id||"vCenter"}</span>
                        <span style={{fontSize:14,fontWeight:700,color:hc}}>{s.connected_hosts}/{s.total_hosts} hosts</span>
                      </div>
                      <div style={{display:"flex",gap:10,fontSize:14,color:p.textMute}}>
                        <span>🖥️ {s.running_vms||0}/{s.total_vms||0} VMs</span>
                        <span>⚡ {Math.round((s.cpu?.used_mhz||0)/1000)}/{Math.round((s.cpu?.total_mhz||0)/1000)} GHz</span>
                        <span>🧠 {fmtGB(s.ram?.used_gb||0)}/{fmtGB(s.ram?.total_gb||0)}</span>
                      </div>
                    </div>
                  );
                })
              }
            </div>
          </div>

          {/* Datastore health table */}
          <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,overflow:"hidden"}}>
            <div style={{padding:"12px 18px",borderBottom:`1px solid ${p.border}`,background:p.panelAlt,
              display:"flex",justifyContent:"space-between",alignItems:"center"}}>
              <span style={{fontWeight:700,fontSize:16,color:p.text}}>💾 Datastore Capacity</span>
              <span style={{fontSize:15,color:p.textMute}}>{datastores.length} datastores</span>
            </div>
            <div className="tbl-wrap" style={{maxHeight:280}}>
              <table><thead><tr>
                <th>DATASTORE</th><th>TYPE</th><th>USAGE</th>
                <th>USED</th><th>FREE</th><th>TOTAL</th><th>STATUS</th>
              </tr></thead>
              <tbody>{datastores.sort((a,b)=>((b.total_gb-b.free_gb)/b.total_gb)-((a.total_gb-a.free_gb)/a.total_gb)).map((d,i)=>{
                const usedPct=d.total_gb>0?Math.round(((d.total_gb-d.free_gb)/d.total_gb)*100):0;
                const bc=pctColor(usedPct);
                const status=usedPct>=90?"CRITICAL":usedPct>=75?"WARNING":"OK";
                return(<tr key={i}>
                  <td><span style={{fontWeight:600,color:p.text}}>{d.name||"—"}</span></td>
                  <td><span style={{fontSize:14,color:"#a855f7",fontFamily:"monospace"}}>{d.type||"—"}</span></td>
                  <td><div style={{display:"flex",alignItems:"center",gap:6,minWidth:100}}>
                    <div style={{flex:1,height:7,borderRadius:4,background:`${p.border}60`,overflow:"hidden"}}>
                      <div style={{width:`${usedPct}%`,height:"100%",background:bc,borderRadius:4,transition:"width .8s"}}/>
                    </div>
                    <span style={{fontSize:13,fontWeight:700,color:bc,fontFamily:"monospace",minWidth:34}}>{usedPct}%</span>
                  </div></td>
                  <td><span style={{color:"#ef4444",fontFamily:"monospace",fontSize:14}}>{fmtGB(d.total_gb-d.free_gb)}</span></td>
                  <td><span style={{color:"#10b981",fontFamily:"monospace",fontSize:14}}>{fmtGB(d.free_gb)}</span></td>
                  <td><span style={{fontFamily:"monospace",fontSize:14}}>{fmtGB(d.total_gb)}</span></td>
                  <td><span style={{fontSize:13,fontWeight:700,padding:"2px 9px",borderRadius:6,
                    color:status==="CRITICAL"?"#ef4444":status==="WARNING"?"#f59e0b":"#10b981",
                    background:status==="CRITICAL"?"#ef444415":status==="WARNING"?"#f59e0b15":"#10b98115",
                    border:`1px solid ${status==="CRITICAL"?"#ef444430":status==="WARNING"?"#f59e0b30":"#10b98130"}`}}>{status}</span></td>
                </tr>);
              })}</tbody></table>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════
          OPENSHIFT TAB
      ══════════════════════════════════════════════════════════ */}
      {platTab==="openshift"&&(()=>{
        const clusters=ocpData?.clusters||[];
        const ovs=Object.values(ocpData?.overviews||{});
        const totNodes=ovs.reduce((a,ov)=>a+(ov?.nodes_summary?.total||0),0);
        const rdyNodes=ovs.reduce((a,ov)=>a+(ov?.nodes_summary?.ready||0),0);
        const totPods=ovs.reduce((a,ov)=>a+(ov?.pods_summary?.total||0),0);
        const runPods=ovs.reduce((a,ov)=>a+(ov?.pods_summary?.running||0),0);
        const totOps=ovs.reduce((a,ov)=>a+(ov?.operators_summary?.total||0),0);
        const okOps=ovs.reduce((a,ov)=>a+(ov?.operators_summary?.available||0),0);
        const totWarn=ovs.reduce((a,ov)=>a+(ov?.warnings||0),0);
        return(
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <SectionHeader icon="🔴" title="Red Hat OpenShift — Cluster Capacity" color="#ef4444" badge={`${clusters.length} Cluster${clusters.length!==1?"s":""}`}/>
            {clusters.length===0
              ?<NotCfgBlock icon="🔴" platform="OpenShift" msg="Navigate to the OpenShift page and add a cluster."/>
              :<>
                <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:10}}>
                  <StatCard icon="🔴" label="Clusters"    value={clusters.length}          color="#ef4444"/>
                  <StatCard icon="🖥️" label="Nodes Ready" value={`${rdyNodes}/${totNodes}`} color={rdyNodes<totNodes?"#ef4444":"#10b981"} sub={`${totNodes-rdyNodes} not ready`}/>
                  <StatCard icon="📦" label="Pods Running" value={`${runPods}/${totPods}`}  color="#06b6d4" sub={`${totPods-runPods} other`}/>
                  <StatCard icon="⚙️" label="Operators OK" value={`${okOps}/${totOps}`}    color={okOps<totOps?"#f97316":"#10b981"} sub={`${totOps-okOps} degraded`}/>
                  <StatCard icon="⚠️" label="Warnings"     value={totWarn}                  color={totWarn>0?"#f59e0b":"#10b981"} sub="across all clusters"/>
                </div>
                <div style={{display:"flex",flexDirection:"column",gap:10}}>
                  {clusters.map(cl=>{
                    const ov=ocpData?.overviews?.[cl.id];
                    const nReady=ov?.nodes_summary?.ready||0, nTotal=ov?.nodes_summary?.total||0, nNR=ov?.nodes_summary?.not_ready||0;
                    const pRun=ov?.pods_summary?.running||0, pTot=ov?.pods_summary?.total||0, pFail=ov?.pods_summary?.failed||0;
                    const oAvail=ov?.operators_summary?.available||0, oTot=ov?.operators_summary?.total||0, oDeg=ov?.operators_summary?.degraded||0;
                    const health=!ov?"unknown":nNR>0||oDeg>0?"degraded":(ov?.warnings||0)>5?"warning":"healthy";
                    const hc=health==="healthy"?"#10b981":health==="degraded"?"#ef4444":"#f59e0b";
                    const nodePct=nTotal>0?Math.round((nReady/nTotal)*100):0;
                    const podPct=pTot>0?Math.round((pRun/pTot)*100):0;
                    const opPct=oTot>0?Math.round((oAvail/oTot)*100):0;
                    return(
                      <div key={cl.id} style={{background:p.panelAlt,borderRadius:12,overflow:"hidden",
                        border:`1px solid ${hc}25`,borderLeft:`4px solid ${hc}`}}>
                        <div style={{padding:"12px 18px",borderBottom:`1px solid ${p.border}`,
                          display:"flex",alignItems:"center",gap:12,background:`${hc}05`}}>
                          <div style={{width:10,height:10,borderRadius:"50%",background:hc,boxShadow:`0 0 8px ${hc}80`,flexShrink:0}}/>
                          <div style={{flex:1}}>
                            <div style={{fontWeight:800,fontSize:17,color:"#ef4444"}}>{cl.name}</div>
                            <div style={{fontSize:14,color:p.textMute}}>{cl.api_url||"—"}
                              {ov?.version?.version&&<span style={{marginLeft:8,color:p.cyan,fontWeight:600}}>{ov.version.version}</span>}
                            </div>
                          </div>
                          <span style={{fontSize:14,fontWeight:700,padding:"3px 12px",borderRadius:20,
                            background:`${hc}15`,color:hc,border:`1px solid ${hc}35`}}>{health.toUpperCase()}</span>
                        </div>
                        <div style={{padding:"14px 18px",display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
                          {[
                            {label:"Node Readiness",pct:nodePct,color:nNR>0?"#ef4444":"#10b981",sub:`${nReady} ready · ${nNR} not ready`,total:nTotal},
                            {label:"Pod Health",    pct:podPct, color:pFail>0?"#ef4444":"#10b981",sub:`${pRun} running · ${pFail} failed`,total:pTot},
                            {label:"Operator Health",pct:opPct, color:oDeg>0?"#f97316":"#10b981",sub:`${oAvail} ok · ${oDeg} degraded`,total:oTot},
                          ].map(({label,pct,color,sub,total})=>(
                            <div key={label} style={{padding:"10px 14px",borderRadius:9,background:`${color}08`,border:`1px solid ${color}20`}}>
                              <div style={{fontSize:14,fontWeight:700,color:p.textMute,textTransform:"uppercase",letterSpacing:".5px",marginBottom:8}}>{label}</div>
                              <div style={{height:6,borderRadius:3,background:`${p.border}`,overflow:"hidden",marginBottom:6}}>
                                <div style={{height:"100%",width:`${pct}%`,background:color,borderRadius:3,transition:"width .8s"}}/>
                              </div>
                              <div style={{display:"flex",justifyContent:"space-between"}}>
                                <span style={{fontSize:14,color:p.textMute}}>{sub}</span>
                                <span style={{fontSize:18,fontWeight:800,color,fontFamily:"monospace"}}>{total}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                        {(ov?.warnings||0)>0&&(
                          <div style={{margin:"0 18px 12px",display:"flex",alignItems:"center",gap:8,padding:"6px 12px",
                            borderRadius:8,background:`${p.yellow}10`,border:`1px solid ${p.yellow}25`}}>
                            <span>⚠️</span>
                            <span style={{fontSize:15,color:p.yellow,fontWeight:600}}>{ov.warnings} warning event{ov.warnings!==1?"s":""} active</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            }
          </div>
        );
      })()}

      {/* ══════════════════════════════════════════════════════════
          NUTANIX TAB
      ══════════════════════════════════════════════════════════ */}
      {platTab==="nutanix"&&(()=>{
        const pcs=nutData?.pcs||[];
        const ovs=Object.values(nutData?.overviews||{});
        const totVMs=ovs.reduce((a,ov)=>a+(ov?.vms?.total||0),0);
        const runVMs=ovs.reduce((a,ov)=>a+(ov?.vms?.running||0),0);
        const totHosts=ovs.reduce((a,ov)=>a+(ov?.hosts||0),0);
        const totMem=ovs.reduce((a,ov)=>a+(ov?.total_memory_gib||0),0);
        const critAlerts=ovs.reduce((a,ov)=>a+(ov?.alerts?.critical||0),0);
        const warnAlerts=ovs.reduce((a,ov)=>a+(ov?.alerts?.warning||0),0);
        return(
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <SectionHeader icon="🟩" title="Nutanix AHV — Cluster Capacity" color="#22c55e" badge={`${pcs.length} Prism Central${pcs.length!==1?"s":""}`}/>
            {pcs.length===0
              ?<NotCfgBlock icon="🟩" platform="Nutanix" msg="Navigate to the Nutanix page and add a Prism Central."/>
              :<>
                <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:10}}>
                  <StatCard icon="🟩" label="Prism Centrals" value={pcs.length}                            color="#22c55e"/>
                  <StatCard icon="💻" label="VMs Running"    value={`${runVMs}/${totVMs}`}                 color="#10b981" sub={`${totVMs-runVMs} powered off`}/>
                  <StatCard icon="🖥️" label="AHV Hosts"      value={totHosts}                              color="#06b6d4"/>
                  <StatCard icon="🧠" label="Total Memory"   value={`${Math.round(totMem)} GiB`}           color="#a855f7"/>
                  <StatCard icon="🚨" label="Alerts"         value={critAlerts>0?`${critAlerts} critical`:`${warnAlerts} warning`} color={critAlerts>0?"#ef4444":"#f59e0b"} sub={critAlerts>0?`+ ${warnAlerts} warnings`:"no critical"}/>
                </div>
                <div style={{display:"flex",flexDirection:"column",gap:10}}>
                  {pcs.map(pc=>{
                    const ov=nutData?.overviews?.[pc.id];
                    const vmRun=ov?.vms?.running||0, vmTot=ov?.vms?.total||0;
                    const crit=ov?.alerts?.critical||0, warn=ov?.alerts?.warning||0;
                    const memGiB=Math.round(ov?.total_memory_gib||0);
                    const health=!ov?"unknown":crit>0?"critical":warn>3?"warning":"healthy";
                    const hc=health==="healthy"?"#10b981":health==="critical"?"#ef4444":"#f59e0b";
                    const vmPct=vmTot>0?Math.round((vmRun/vmTot)*100):0;
                    return(
                      <div key={pc.id} style={{background:p.panelAlt,borderRadius:12,border:`1px solid #22c55e20`,borderLeft:`4px solid ${hc}`,overflow:"hidden"}}>
                        <div style={{padding:"12px 18px",borderBottom:`1px solid ${p.border}`,
                          display:"flex",alignItems:"center",gap:12,background:`${hc}05`}}>
                          <div style={{width:10,height:10,borderRadius:"50%",background:hc,boxShadow:`0 0 8px ${hc}80`,flexShrink:0}}/>
                          <div style={{flex:1}}>
                            <div style={{fontWeight:800,fontSize:17,color:"#22c55e"}}>{pc.name}</div>
                            <div style={{fontSize:14,color:p.textMute}}>{pc.host||"—"}
                              {pc.site_group&&<span style={{marginLeft:8,color:"#06b6d4",fontWeight:600}}>{pc.site_group}</span>}
                            </div>
                          </div>
                          <span style={{fontSize:14,fontWeight:700,padding:"3px 12px",borderRadius:20,background:`${hc}15`,color:hc,border:`1px solid ${hc}35`}}>{health.toUpperCase()}</span>
                        </div>
                        <div style={{padding:"14px 18px",display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12}}>
                          {[
                            {label:"VM Running %",pct:vmPct,color:vmPct>80?"#10b981":vmPct>40?"#f59e0b":"#64748b",sub:`${vmRun} on · ${vmTot-vmRun} off`,total:vmTot},
                            {label:"AHV Hosts",pct:0,color:"#06b6d4",sub:`${ov?.total_vcpus||0} vCPUs`,total:ov?.hosts||0,noBar:true},
                            {label:"AHV Clusters",pct:0,color:"#22c55e",sub:`${memGiB} GiB total mem`,total:ov?.clusters||0,noBar:true},
                            {label:"Alerts",pct:0,color:crit>0?"#ef4444":"#f59e0b",sub:`${crit} critical · ${warn} warn`,total:crit+warn,noBar:true},
                          ].map(({label,pct,color,sub,total,noBar})=>(
                            <div key={label} style={{padding:"10px 14px",borderRadius:9,background:`${color}08`,border:`1px solid ${color}20`}}>
                              <div style={{fontSize:14,fontWeight:700,color:p.textMute,textTransform:"uppercase",letterSpacing:".5px",marginBottom:8}}>{label}</div>
                              {!noBar&&<div style={{height:6,borderRadius:3,background:`${p.border}`,overflow:"hidden",marginBottom:6}}>
                                <div style={{height:"100%",width:`${pct}%`,background:color,borderRadius:3,transition:"width .8s"}}/>
                              </div>}
                              <div style={{display:"flex",justifyContent:"space-between",marginTop:noBar?4:0}}>
                                <span style={{fontSize:14,color:p.textMute}}>{sub}</span>
                                <span style={{fontSize:22,fontWeight:900,color,fontFamily:"monospace"}}>{total}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                        {(crit>0||warn>0)&&(
                          <div style={{margin:"0 18px 12px",display:"flex",alignItems:"center",gap:8,padding:"6px 12px",
                            borderRadius:8,background:crit>0?`${p.red}10`:`${p.yellow}10`,border:`1px solid ${crit>0?p.red:p.yellow}25`}}>
                            <span>⚠️</span>
                            <span style={{fontSize:15,color:crit>0?p.red:p.yellow,fontWeight:600}}>
                              {crit>0?`${crit} critical alert${crit!==1?"s":""}`:""}{crit>0&&warn>0?" · ":""}{warn>0?`${warn} warning${warn!==1?"s":""}`:""} active
                            </span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </>
            }
          </div>
        );
      })()}

      {/* ══════════════════════════════════════════════════════════
          AWS TAB
      ══════════════════════════════════════════════════════════ */}
      {platTab==="aws"&&(()=>{
        if(awsLoading) return <LoadState msg="Loading AWS capacity…"/>;
        const connected=awsStat?.connected||false;
        if(!connected) return <NotCfgBlock icon="☁️" platform="AWS" msg="Navigate to the AWS page and configure credentials or SSO."/>;
        const ec2=awsDisc?.ec2||{};
        const ec2Running=ec2.running||0, ec2Total=ec2.total||0, ec2Stopped=ec2Total-ec2Running;
        const ec2Pct=ec2Total>0?Math.round((ec2Running/ec2Total)*100):0;
        const buckets=(awsS3?.buckets||[]);
        const costs=awsCosts||{};
        const rdsList=awsDisc?.rds||[];
        const vpcList=awsDisc?.vpcs||[];
        const subnetList=awsDisc?.subnets||[];
        return(
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <SectionHeader icon="☁️" title="Amazon Web Services — Cloud Capacity" color="#FF9900"
              badge={`${awsStat?.account_alias||awsStat?.account_id||"Connected"} · ${awsStat?.region||""}`}/>
            {/* KPI row */}
            <div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:10}}>
              <StatCard icon="🖥️" label="EC2 Running"  value={ec2Running}             color="#FF9900" sub={`${ec2Stopped} stopped · ${ec2Total} total`}/>
              <StatCard icon="📊" label="EC2 Used %"   value={`${ec2Pct}%`}           color={ec2Pct>85?"#ef4444":ec2Pct>60?"#f59e0b":"#10b981"} sub="instances running"/>
              <StatCard icon="🗄️" label="RDS Instances" value={rdsList.length}         color="#a855f7" sub="databases"/>
              <StatCard icon="🪣" label="S3 Buckets"   value={buckets.length}          color="#06b6d4" sub="storage buckets"/>
              <StatCard icon="🌐" label="VPCs"         value={vpcList.length}          color="#3b82f6" sub={`${subnetList.length} subnets`}/>
              <StatCard icon="💰" label="Monthly Cost" value={costs.current_month_cost!=null?`$${Number(costs.current_month_cost).toFixed(0)}`:"—"} color="#10b981" sub={costs.currency||"USD"}/>
            </div>
            {/* EC2 + cost side by side */}
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
              <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,padding:"18px 20px"}}>
                <div style={{fontWeight:700,fontSize:16,color:"#FF9900",marginBottom:14}}>🖥️ EC2 Instance State</div>
                <GaugeBar pct={ec2Pct} color="#FF9900" label="Running instances" used={`${ec2Running} running`} total={`${ec2Total} total`} h={12}/>
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginTop:6}}>
                  {[
                    {label:"Running",  val:ec2Running,  color:"#FF9900"},
                    {label:"Stopped",  val:ec2Stopped,  color:"#ef4444"},
                    {label:"Total EC2",val:ec2Total,     color:p.text},
                    {label:"Account",  val:awsStat?.account_alias||awsStat?.account_id||"—", color:"#FF9900"},
                  ].map(r=>(
                    <div key={r.label} style={{display:"flex",justifyContent:"space-between",padding:"7px 10px",
                      borderRadius:7,background:p.panelAlt}}>
                      <span style={{fontSize:14,color:p.textMute}}>{r.label}</span>
                      <span style={{fontSize:14,fontWeight:700,color:r.color}}>{r.val}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,padding:"18px 20px"}}>
                <div style={{fontWeight:700,fontSize:16,color:"#10b981",marginBottom:14}}>💰 Cost & Usage</div>
                {costs.current_month_cost!=null
                  ?<>
                    <div style={{fontSize:36,fontWeight:900,color:"#10b981",fontFamily:"monospace",marginBottom:4}}>
                      ${Number(costs.current_month_cost).toFixed(2)}
                    </div>
                    <div style={{fontSize:15,color:p.textMute,marginBottom:14}}>Current month to date</div>
                    {(costs.services||[]).slice(0,5).map((svc,i)=>(
                      <div key={i} style={{display:"flex",justifyContent:"space-between",padding:"5px 0",
                        borderBottom:`1px solid ${p.border}30`}}>
                        <span style={{fontSize:14,color:p.textSub}}>{svc.service||"—"}</span>
                        <span style={{fontSize:14,fontWeight:700,color:"#10b981",fontFamily:"monospace"}}>${Number(svc.cost||0).toFixed(2)}</span>
                      </div>
                    ))}
                  </>
                  :<div style={{color:p.textMute,fontSize:15,padding:"20px 0",textAlign:"center"}}>Cost data not available<br/><span style={{fontSize:14}}>Configure AWS Cost Explorer permissions</span></div>
                }
              </div>
            </div>
            {/* RDS instances */}
            {rdsList.length>0&&(
              <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,overflow:"hidden"}}>
                <div style={{padding:"12px 18px",borderBottom:`1px solid ${p.border}`,background:p.panelAlt,
                  display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                  <span style={{fontWeight:700,fontSize:16,color:p.text}}>🗄️ RDS Database Instances</span>
                  <span style={{fontSize:15,color:p.textMute}}>{rdsList.length} instances</span>
                </div>
                <div className="tbl-wrap" style={{maxHeight:240}}>
                  <table><thead><tr><th>IDENTIFIER</th><th>ENGINE</th><th>CLASS</th><th>STATUS</th><th>REGION</th></tr></thead>
                  <tbody>{rdsList.map((r,i)=>{
                    const st=(r.status||"").toLowerCase();
                    const sc=st==="available"?"#10b981":st==="stopped"?"#ef4444":"#f59e0b";
                    return(<tr key={i}>
                      <td><span style={{fontWeight:600,color:"#a855f7"}}>{r.identifier||r.db_instance_identifier||"—"}</span></td>
                      <td><span style={{color:"#FF9900",fontFamily:"monospace",fontSize:14}}>{r.engine||"—"} {r.engine_version||""}</span></td>
                      <td><span style={{fontFamily:"monospace",fontSize:14}}>{r.instance_class||"—"}</span></td>
                      <td><span style={{fontSize:13,fontWeight:700,padding:"2px 8px",borderRadius:5,color:sc,background:`${sc}15`,border:`1px solid ${sc}30`}}>{r.status||"—"}</span></td>
                      <td><span style={{fontSize:14,color:p.textMute}}>{r.region||"—"}</span></td>
                    </tr>);
                  })}</tbody></table>
                </div>
              </div>
            )}
            {/* S3 buckets summary */}
            {buckets.length>0&&(
              <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,overflow:"hidden"}}>
                <div style={{padding:"12px 18px",borderBottom:`1px solid ${p.border}`,background:p.panelAlt,
                  display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                  <span style={{fontWeight:700,fontSize:16,color:p.text}}>🪣 S3 Buckets</span>
                  <span style={{fontSize:15,color:p.textMute}}>{buckets.length} buckets</span>
                </div>
                <div className="tbl-wrap" style={{maxHeight:220}}>
                  <table><thead><tr><th>BUCKET NAME</th><th>REGION</th><th>CREATED</th></tr></thead>
                  <tbody>{buckets.slice(0,30).map((b,i)=>(
                    <tr key={i}>
                      <td><span style={{fontWeight:600,color:"#06b6d4"}}>{b.name||"—"}</span></td>
                      <td><span style={{fontSize:14,color:p.textMute}}>{b.region||"—"}</span></td>
                      <td><span style={{fontSize:14,color:p.textMute}}>{b.creation_date?new Date(b.creation_date).toLocaleDateString():"—"}</span></td>
                    </tr>
                  ))}</tbody></table>
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* ══════════════════════════════════════════════════════════
          HYPER-V TAB
      ══════════════════════════════════════════════════════════ */}
      {platTab==="hyperv"&&(()=>{
        if(hvLoading) return <LoadState msg="Loading Hyper-V capacity…"/>;
        const hostList=(hvHosts?.hosts||[]).filter(h=>h.host);
        if(hostList.length===0) return <NotCfgBlock icon="🪟" platform="Hyper-V" msg="Navigate to the Hyper-V page and configure hosts."/>;
        const allVMs=hvVMsData?.vms||[];
        const vmRunning=allVMs.filter(v=>v.State==="Running").length;
        const vmOff=allVMs.filter(v=>v.State==="Off").length;
        const vmTotal=allVMs.length;
        const vmRunPct=vmTotal>0?Math.round((vmRunning/vmTotal)*100):0;
        const vmsByHost=allVMs.reduce((acc,v)=>{ const h=v.Host||"Unknown"; acc[h]=(acc[h]||[]); acc[h].push(v); return acc; },{});
        return(
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <SectionHeader icon="🪟" title="Microsoft Hyper-V — VM Capacity" color="#00ADEF" badge={`${hostList.length} Host${hostList.length!==1?"s":""}`}/>
            {/* KPI */}
            <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:10}}>
              <StatCard icon="🪟" label="HV Hosts"    value={hostList.length}              color="#00ADEF"/>
              <StatCard icon="💻" label="VMs Running" value={`${vmRunning}/${vmTotal}`}    color="#10b981" sub={`${vmOff} off`}/>
              <StatCard icon="📊" label="VM Running %" value={`${vmRunPct}%`}              color={vmRunPct>80?"#10b981":vmRunPct>40?"#f59e0b":"#ef4444"}/>
              <StatCard icon="🟢" label="VMs On"      value={vmRunning}                    color="#10b981"/>
              <StatCard icon="🔴" label="VMs Off"     value={vmOff}                        color="#ef4444"/>
            </div>
            {/* Gauge */}
            <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,padding:"18px 20px"}}>
              <div style={{fontWeight:700,fontSize:16,color:"#00ADEF",marginBottom:14}}>📈 VM State Distribution</div>
              <GaugeBar pct={vmRunPct} color="#00ADEF" label="Running VMs" used={`${vmRunning} running`} total={`${vmTotal} total`} h={12}/>
            </div>
            {/* Per-host breakdown */}
            <div style={{fontWeight:800,fontSize:15,color:"#00ADEF",letterSpacing:"1.2px",textTransform:"uppercase",padding:"4px 0"}}>Per-Host Breakdown</div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              {hostList.map((h,i)=>{
                const hVMs=vmsByHost[h.host]||[];
                const hRun=hVMs.filter(v=>v.State==="Running").length;
                const hOff=hVMs.filter(v=>v.State==="Off").length;
                const hPct=hVMs.length>0?Math.round((hRun/hVMs.length)*100):0;
                const hc=hPct>80?"#10b981":hPct>40?"#f59e0b":"#64748b";
                return(
                  <div key={i} style={{background:p.panelAlt,borderRadius:12,border:`1px solid #00ADEF20`,borderLeft:`3px solid ${hc}`,padding:"14px 16px"}}>
                    <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:10}}>
                      <span style={{fontSize:20}}>🪟</span>
                      <div style={{flex:1}}>
                        <div style={{fontWeight:700,fontSize:16,color:"#00ADEF"}}>{h.host}</div>
                        <div style={{fontSize:14,color:p.textMute}}>{h.username||"—"}</div>
                      </div>
                      <span style={{fontSize:14,fontWeight:700,padding:"2px 10px",borderRadius:12,color:hc,background:`${hc}15`,border:`1px solid ${hc}30`}}>{hRun} running</span>
                    </div>
                    <div style={{height:7,borderRadius:4,background:`${p.border}60`,overflow:"hidden",marginBottom:8}}>
                      <div style={{width:`${hPct}%`,height:"100%",background:hc,borderRadius:4,transition:"width .8s"}}/>
                    </div>
                    <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:6}}>
                      {[{l:"Running",v:hRun,c:"#10b981"},{l:"Off",v:hOff,c:"#ef4444"},{l:"Total",v:hVMs.length,c:"#00ADEF"}].map(r=>(
                        <div key={r.l} style={{textAlign:"center",padding:"6px",borderRadius:7,background:p.panel}}>
                          <div style={{fontSize:18,fontWeight:800,color:r.c,fontFamily:"monospace"}}>{r.v}</div>
                          <div style={{fontSize:13,color:p.textMute}}>{r.l}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
            {/* VM table */}
            {allVMs.length>0&&(
              <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,overflow:"hidden"}}>
                <div style={{padding:"12px 18px",borderBottom:`1px solid ${p.border}`,background:p.panelAlt,
                  display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                  <span style={{fontWeight:700,fontSize:16,color:p.text}}>🪟 All Hyper-V VMs</span>
                  <span style={{fontSize:15,color:p.textMute}}>{allVMs.length} VMs</span>
                </div>
                <div className="tbl-wrap" style={{maxHeight:300}}>
                  <table><thead><tr><th>VM NAME</th><th>STATE</th><th>HOST</th><th>CPU</th><th>MEMORY</th></tr></thead>
                  <tbody>{allVMs.slice(0,50).map((v,i)=>{
                    const sc=v.State==="Running"?"#10b981":v.State==="Off"?"#ef4444":"#f59e0b";
                    return(<tr key={i}>
                      <td><span style={{fontWeight:600,color:"#00ADEF"}}>{v.Name||v.VMName||"—"}</span></td>
                      <td><span style={{fontSize:13,fontWeight:700,padding:"2px 8px",borderRadius:5,color:sc,background:`${sc}15`,border:`1px solid ${sc}30`}}>{v.State||"—"}</span></td>
                      <td><span style={{fontSize:14,color:p.textMute}}>{v.Host||"—"}</span></td>
                      <td><span style={{fontFamily:"monospace",fontSize:14}}>{v.ProcessorCount!=null?v.ProcessorCount+" vCPU":"—"}</span></td>
                      <td><span style={{fontFamily:"monospace",fontSize:14}}>{v.MemoryAssigned!=null?fmtGB(v.MemoryAssigned/1024):"—"}</span></td>
                    </tr>);
                  })}</tbody></table>
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* ══════════════════════════════════════════════════════════
          STORAGE TAB
      ══════════════════════════════════════════════════════════ */}
      {platTab==="storage"&&(()=>{
        if(storLoading) return <LoadState msg="Loading storage capacity…"/>;
        if(storArrays.length===0) return <NotCfgBlock icon="💾" platform="Storage Arrays" msg="Navigate to the Storage page and add a storage array."/>;
        const allArrayData=Object.values(storData).filter(Boolean);
        const totRawTB=allArrayData.reduce((s,d)=>s+(d.capacity?.raw_tb||d.capacity?.total_tb||0),0);
        const usedRawTB=allArrayData.reduce((s,d)=>s+(d.capacity?.used_tb||0),0);
        const freeTB=totRawTB-usedRawTB;
        const totCapPct=totRawTB>0?Math.round((usedRawTB/totRawTB)*100):0;
        return(
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <SectionHeader icon="💾" title="Storage Arrays — Capacity Overview" color="#a855f7" badge={`${storArrays.length} Array${storArrays.length!==1?"s":""}`}/>
            {/* Aggregate KPIs */}
            <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:10}}>
              <StatCard icon="💾" label="Arrays"      value={storArrays.length}            color="#a855f7"/>
              <StatCard icon="📦" label="Total Raw"   value={totRawTB>0?`${totRawTB.toFixed(1)} TB`:"—"} color="#3b82f6"/>
              <StatCard icon="🔴" label="Used"        value={usedRawTB>0?`${usedRawTB.toFixed(1)} TB`:"—"} color={pctColor(totCapPct)}/>
              <StatCard icon="🟢" label="Free"        value={freeTB>0?`${freeTB.toFixed(1)} TB`:"—"}  color="#10b981"/>
              <StatCard icon="📊" label="Used %"      value={totRawTB>0?`${totCapPct}%`:"—"}           color={pctColor(totCapPct)}/>
            </div>
            {totRawTB>0&&(
              <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,padding:"18px 20px"}}>
                <GaugeBar pct={totCapPct} color="#a855f7" label="Overall Storage Utilisation" used={`${usedRawTB.toFixed(1)} TB`} total={`${totRawTB.toFixed(1)} TB`} h={14}/>
              </div>
            )}
            {/* Per-array cards */}
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
              {storArrays.map(arr=>{
                const d=storData[arr.id];
                const capTot=d?.capacity?.raw_tb||d?.capacity?.total_tb||0;
                const capUsed=d?.capacity?.used_tb||0;
                const capFree=capTot-capUsed;
                const capPct=capTot>0?Math.round((capUsed/capTot)*100):0;
                const volumes=(d?.volumes||[]);
                const pools=(d?.pools||[]);
                const hc=pctColor(capPct);
                return(
                  <div key={arr.id} style={{background:p.panelAlt,borderRadius:12,
                    border:`1px solid #a855f720`,borderLeft:`4px solid ${hc}`,padding:"16px 18px"}}>
                    <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12}}>
                      <span style={{fontSize:24}}>💾</span>
                      <div style={{flex:1}}>
                        <div style={{fontWeight:800,fontSize:17,color:"#a855f7"}}>{arr.name||arr.host}</div>
                        <div style={{fontSize:14,color:p.textMute}}>{arr.type||"Storage Array"} · {arr.host}</div>
                      </div>
                      {capPct>0&&<span style={{fontSize:14,fontWeight:700,padding:"3px 10px",borderRadius:12,
                        color:hc,background:`${hc}15`,border:`1px solid ${hc}30`}}>{capPct}% used</span>}
                    </div>
                    {capTot>0&&(
                      <>
                        <GaugeBar pct={capPct} color={hc} label="Capacity" used={`${capUsed.toFixed(1)} TB`} total={`${capTot.toFixed(1)} TB`}/>
                        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:8,marginTop:8}}>
                          {[{l:"Total",v:`${capTot.toFixed(1)} TB`,c:"#3b82f6"},{l:"Used",v:`${capUsed.toFixed(1)} TB`,c:hc},{l:"Free",v:`${capFree.toFixed(1)} TB`,c:"#10b981"}].map(r=>(
                            <div key={r.l} style={{textAlign:"center",padding:"8px",borderRadius:8,background:p.panel}}>
                              <div style={{fontSize:16,fontWeight:800,color:r.c,fontFamily:"monospace"}}>{r.v}</div>
                              <div style={{fontSize:13,color:p.textMute}}>{r.l}</div>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                    <div style={{display:"flex",gap:12,marginTop:8,fontSize:14,color:p.textMute}}>
                      {volumes.length>0&&<span>📂 {volumes.length} volumes</span>}
                      {pools.length>0&&<span>🗄️ {pools.length} pools</span>}
                      {!capTot&&<span style={{color:p.textMute,fontStyle:"italic"}}>Connect array for capacity data</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* ══════════════════════════════════════════════════════════
          BACKUP TAB
      ══════════════════════════════════════════════════════════ */}
      {platTab==="backup"&&(()=>{
        if(veeamLoading) return <LoadState msg="Loading backup capacity…"/>;
        if(veeamConns.length===0) return <NotCfgBlock icon="🛡️" platform="Veeam Backup" msg="Navigate to the Backup page and add a Veeam B&R connection."/>;
        const allData=Object.values(veeamData).filter(Boolean);
        const allJobs=allData.flatMap(d=>d?.jobs||[]);
        const allSessions=allData.flatMap(d=>d?.sessions||[]);
        const successSess=allSessions.filter(s=>(s.result||"").toLowerCase()==="success").length;
        const warnSess=allSessions.filter(s=>(s.result||"").toLowerCase()==="warning").length;
        const failSess=allSessions.filter(s=>(s.result||"").toLowerCase()==="failed"||s.result?.toLowerCase()==="error").length;
        const succPct=allSessions.length>0?Math.round((successSess/allSessions.length)*100):0;
        return(
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <SectionHeader icon="🛡️" title="Veeam Backup & Replication — Job Status" color="#10b981" badge={`${veeamConns.length} Server${veeamConns.length!==1?"s":""}`}/>
            {/* KPI */}
            <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:10}}>
              <StatCard icon="🛡️" label="VBR Servers"   value={veeamConns.length}             color="#10b981"/>
              <StatCard icon="📋" label="Total Jobs"     value={allJobs.length}                color="#3b82f6"/>
              <StatCard icon="✅" label="Sessions OK"    value={successSess}                   color="#10b981" sub={`${succPct}% success rate`}/>
              <StatCard icon="⚠️" label="Warnings"       value={warnSess}                      color="#f59e0b"/>
              <StatCard icon="❌" label="Failed"         value={failSess}                      color={failSess>0?"#ef4444":"#10b981"}/>
            </div>
            {/* Success rate bar */}
            {allSessions.length>0&&(
              <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,padding:"18px 20px"}}>
                <GaugeBar pct={succPct} color={succPct>90?"#10b981":succPct>70?"#f59e0b":"#ef4444"}
                  label="Backup Success Rate" used={`${successSess} success`} total={`${allSessions.length} sessions`} h={12}/>
                <div style={{display:"flex",gap:14,marginTop:8}}>
                  {[{l:"Success",v:successSess,c:"#10b981"},{l:"Warning",v:warnSess,c:"#f59e0b"},{l:"Failed",v:failSess,c:"#ef4444"}].map(r=>(
                    <div key={r.l} style={{display:"flex",alignItems:"center",gap:6}}>
                      <div style={{width:10,height:10,borderRadius:"50%",background:r.c}}/>
                      <span style={{fontSize:14,color:p.textMute}}>{r.l}:</span>
                      <span style={{fontSize:14,fontWeight:700,color:r.c}}>{r.v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {/* Per-server breakdown */}
            {veeamConns.map(conn=>{
              const d=veeamData[conn.id];
              const jobs=d?.jobs||[];
              const sessions=d?.sessions||[];
              const sOk=sessions.filter(s=>(s.result||"").toLowerCase()==="success").length;
              const sFail=sessions.filter(s=>(s.result||"").toLowerCase()==="failed"||(s.result||"").toLowerCase()==="error").length;
              const sWarn=sessions.filter(s=>(s.result||"").toLowerCase()==="warning").length;
              const sRate=sessions.length>0?Math.round((sOk/sessions.length)*100):0;
              const hc=sRate>=90?"#10b981":sRate>=70?"#f59e0b":"#ef4444";
              return(
                <div key={conn.id} style={{background:p.panelAlt,borderRadius:12,
                  border:`1px solid #10b98120`,borderLeft:`4px solid ${hc}`,padding:"16px 18px"}}>
                  <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12}}>
                    <span style={{fontSize:22}}>🛡️</span>
                    <div style={{flex:1}}>
                      <div style={{fontWeight:800,fontSize:17,color:"#10b981"}}>{conn.name||conn.host}</div>
                      <div style={{fontSize:14,color:p.textMute}}>{conn.host} · Veeam B&R</div>
                    </div>
                    <span style={{fontSize:14,fontWeight:700,padding:"3px 10px",borderRadius:12,
                      color:hc,background:`${hc}15`,border:`1px solid ${hc}30`}}>{sRate}% success</span>
                  </div>
                  {sessions.length>0&&<GaugeBar pct={sRate} color={hc} label="Session Success Rate" used={`${sOk} ok`} total={`${sessions.length} sessions`}/>}
                  <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:8,marginTop:6}}>
                    {[{l:"Jobs",v:jobs.length,c:"#3b82f6"},{l:"Success",v:sOk,c:"#10b981"},{l:"Warning",v:sWarn,c:"#f59e0b"},{l:"Failed",v:sFail,c:"#ef4444"}].map(r=>(
                      <div key={r.l} style={{textAlign:"center",padding:"8px",borderRadius:8,background:p.panel}}>
                        <div style={{fontSize:20,fontWeight:800,color:r.c,fontFamily:"monospace"}}>{r.v}</div>
                        <div style={{fontSize:13,color:p.textMute}}>{r.l}</div>
                      </div>
                    ))}
                  </div>
                  {/* Recent jobs */}
                  {jobs.length>0&&(
                    <div style={{marginTop:12}}>
                      <div style={{fontWeight:700,fontSize:14,color:p.textMute,textTransform:"uppercase",letterSpacing:".8px",marginBottom:8}}>Recent Jobs</div>
                      <div style={{display:"flex",flexDirection:"column",gap:4}}>
                        {jobs.slice(0,6).map((j,i)=>{
                          const jr=(j.last_result||j.lastResult||"").toLowerCase();
                          const jc=jr==="success"?"#10b981":jr==="warning"?"#f59e0b":jr==="failed"?"#ef4444":"#64748b";
                          const je=jr==="success"?"✅":jr==="warning"?"⚠️":jr==="failed"?"❌":"⏸️";
                          return(
                            <div key={i} style={{display:"flex",alignItems:"center",gap:10,padding:"6px 10px",
                              borderRadius:7,background:p.panel}}>
                              <span style={{fontSize:15}}>{je}</span>
                              <span style={{flex:1,fontSize:14,fontWeight:600,color:p.text,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{j.name||"—"}</span>
                              <span style={{fontSize:13,fontWeight:700,padding:"2px 8px",borderRadius:5,color:jc,background:`${jc}15`}}>{j.last_result||j.lastResult||"—"}</span>
                              <span style={{fontSize:13,color:p.textMute,whiteSpace:"nowrap"}}>{j.type||""}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })()}

      {/* ══════════════════════════════════════════════════════════
          IPAM TAB
      ══════════════════════════════════════════════════════════ */}
      {platTab==="ipam"&&(()=>{
        const barColor=pct=>pct>=80?"#ef4444":pct>=60?"#f59e0b":"#10b981";
        const summary=ipamData?.summary||{};
        const subnets=ipamData?.subnets||[];
        if(ipamLoading) return <LoadState msg="Loading IPAM data…"/>;
        if(!ipamData||ipamData.error) return(
          <div style={{textAlign:"center",padding:"48px 20px",background:p.panelAlt,border:`1px dashed #06b6d428`,borderRadius:12,color:p.textMute,fontSize:17}}>
            <div style={{fontSize:40,marginBottom:10,opacity:.4}}>📡</div>
            <div style={{fontWeight:700,fontSize:19,marginBottom:6}}>IPAM Data Unavailable</div>
            <div style={{fontSize:16}}>{ipamData?.error||"Unable to reach SolarWinds IPAM. Check backend connectivity."}</div>
          </div>
        );
        return(
          <div style={{display:"flex",flexDirection:"column",gap:16}}>
            <SectionHeader icon="📡" title="IPAM — IP Address Management" color="#06b6d4" badge={`${summary.total_subnets||0} Subnets`}/>
            <div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:10}}>
              {[
                {icon:"📡",label:"Total Subnets",  value:summary.total_subnets||0,    color:"#06b6d4"},
                {icon:"🌐",label:"Total IPs",      value:(summary.total_ips||0).toLocaleString(), color:p.accent},
                {icon:"🔴",label:"Used IPs",       value:(summary.used_ips||0).toLocaleString(),  color:"#ef4444"},
                {icon:"🟢",label:"Available IPs",  value:(summary.available_ips||0).toLocaleString(), color:"#10b981"},
                {icon:"🔒",label:"Reserved IPs",   value:(summary.reserved_ips||0).toLocaleString(),  color:"#a855f7"},
                {icon:"📊",label:"Overall Used %", value:`${Math.round(summary.percent_used||0)}%`, color:barColor(summary.percent_used||0)},
              ].map(k=>(<StatCard key={k.label} icon={k.icon} label={k.label} value={k.value} color={k.color}/>))}
            </div>
            <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,padding:"18px 20px"}}>
              <GaugeBar pct={Math.round(summary.percent_used||0)} color={barColor(summary.percent_used||0)}
                label="Overall IP Address Utilisation"
                used={`${(summary.used_ips||0).toLocaleString()} used`}
                total={`${(summary.total_ips||0).toLocaleString()} total`} h={14}/>
              <div style={{display:"flex",gap:16,fontSize:14,marginTop:6}}>
                <span style={{color:"#ef4444",fontWeight:600}}>Used: {(summary.used_ips||0).toLocaleString()}</span>
                <span style={{color:"#10b981",fontWeight:600}}>Free: {(summary.available_ips||0).toLocaleString()}</span>
                <span style={{color:"#a855f7",fontWeight:600}}>Reserved: {(summary.reserved_ips||0).toLocaleString()}</span>
                {ipamData.cached_at&&<span style={{color:p.textMute,marginLeft:"auto"}}>Cached: {new Date(ipamData.cached_at*1000).toLocaleString()}</span>}
              </div>
            </div>
            <div className="card" style={{overflow:"hidden"}}>
              <div className="card-header">
                <span className="card-title">📡 IP Subnets</span>
                <span style={{fontSize:15,color:p.textMute}}>{subnets.length} subnets</span>
              </div>
              <div className="tbl-wrap" style={{maxHeight:400}}>
                <table><thead><tr>
                  <th>VLAN</th><th>CIDR</th><th>NAME</th><th>LOCATION</th>
                  <th>USAGE</th><th>TOTAL</th><th>USED</th><th>FREE</th><th>STATUS</th>
                </tr></thead>
                <tbody>{subnets.map((s,i)=>{
                  const bc=barColor(s.percent_used||0);
                  return(<tr key={i}>
                    <td><M size={13} color="#06b6d4">{s.vlan||"—"}</M></td>
                    <td><M size={13} color={p.accent}>{s.address_cidr||"—"}</M></td>
                    <td><span style={{fontSize:15,fontWeight:600,color:p.text}}>{s.name||"—"}</span></td>
                    <td><span style={{fontSize:15,color:p.textMute}}>{s.location||"—"}</span></td>
                    <td><div style={{display:"flex",alignItems:"center",gap:6}}><Bar pct={s.percent_used||0} color={bc}/><M color={bc} size={13}>{Math.round(s.percent_used||0)}%</M></div></td>
                    <td><M size={13}>{s.total||0}</M></td>
                    <td><M size={13} color="#ef4444">{s.used||0}</M></td>
                    <td><M size={13} color="#10b981">{s.available||0}</M></td>
                    <td><Badge color={(s.status||"active")==="active"?"connected":"error"}>{(s.status||"active").toUpperCase()}</Badge></td>
                  </tr>);
                })}</tbody></table>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
'''

path = "frontend/src/App.jsx"
src  = open(path, encoding="utf-8").read()

# Find exact boundaries
start_marker = "function CapacityPage({hosts,datastores,vcenters,selectedVC,currentUser,onRefresh,loading,error,onRetry,ocpData,nutData,summaries,p}){"
end_marker   = "// ─── SNAPSHOTS ───────────────────────────────────────────────────────────────"

p1 = src.index(start_marker)
p2 = src.index(end_marker)

# Remove the old function (everything from start_marker to just before end_marker)
new_src = src[:p1] + NEW_PAGE.lstrip("\n") + "\n" + src[p2:]

open(path, "w", encoding="utf-8").write(new_src)
print(f"Done. File size: {len(new_src)} chars (was {len(src)})")
