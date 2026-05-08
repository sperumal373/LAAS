import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchZertoSites, testZertoSite, createZertoSite, deleteZertoSite,
  fetchZertoDashboard, fetchZertoVPGs, fetchZertoVMs,
  fetchZertoAlerts, dismissZertoAlert,
  fetchZertoTasks, fetchZertoEvents, fetchZertoReports,
  zertoTestFailover, zertoStopTestFailover,
  zertoLiveFailover, zertoCommitFailover, zertoRollbackFailover,
  zertoMoveVPG, zertoFailback,
  fetchZertoCheckpoints, fetchZertoAuditLog,
  createZertoVPG, deleteZertoVPG, fetchZertoPeerSites,
  fetchZertoTask,
} from "./api";

const fmtRPO = (sec) => { if (!sec||sec===0) return "0s"; if (sec<60) return sec+"s"; if (sec<3600) return Math.floor(sec/60)+"m "+sec%60+"s"; return Math.floor(sec/3600)+"h "+Math.floor((sec%3600)/60)+"m"; };
const fmtGB = (mb) => mb ? (mb/1024).toFixed(1)+" GB" : "0 GB";
const fmtDate = (d) => { if (!d) return ""; try { return new Date(d).toLocaleString(); } catch { return d; } };
const fmtRel = (d) => { if (!d) return ""; try { const m=Math.floor((Date.now()-new Date(d).getTime())/60000); if(m<1)return"Just now"; if(m<60)return m+"m ago"; if(m<1440)return Math.floor(m/60)+"h ago"; return Math.floor(m/1440)+"d ago"; } catch { return d; } };
const VPG_STATUS_COLOR = {"MeetingSLA":"#10b981","NotMeetingSLA":"#ef4444","RpoNotMeetingSLA":"#f59e0b","HistoryNotMeetingSLA":"#f97316","FailingOver":"#8b5cf6","Moving":"#06b6d4","Deleting":"#ef4444","Recovered":"#10b981","Initializing":"#64748b","RollingBack":"#f97316"};
const SC = (s) => VPG_STATUS_COLOR[s]||"#64748b";

function Sparkline({data=[],color="#06b6d4",height=40,width=160}){if(!data.length)return<svg width={width} height={height}/>;const max=Math.max(...data,1);const pts=data.map((v,i)=>{const x=(i/(data.length-1||1))*width;const y=height-(v/max)*(height-4)-2;return x+","+y;}).join(" ");const area="0,"+height+" "+pts+" "+width+","+height;const gid="g"+color.replace("#","");return(<svg width={width} height={height} style={{overflow:"visible"}}><defs><linearGradient id={gid} x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor={color} stopOpacity="0.3"/><stop offset="100%" stopColor={color} stopOpacity="0.02"/></linearGradient></defs><polygon points={area} fill={"url(#"+gid+")"}/>  <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round"/></svg>);}

function VPGHealthGrid({vpgs}){return(<div style={{display:"flex",flexWrap:"wrap",gap:4,padding:"8px 0"}}>{vpgs.map(v=>(<div key={v.id} title={v.name+"\n"+v.status_text+"\nRPO: "+fmtRPO(v.rpo_seconds)} style={{width:28,height:28,borderRadius:4,cursor:"pointer",background:SC(v.status_text),border:"2px solid "+SC(v.status_text)+"40",opacity:.85,transition:"opacity .15s"}} onMouseEnter={e=>e.target.style.opacity=1} onMouseLeave={e=>e.target.style.opacity=0.85}/>))}{!vpgs.length&&<span style={{color:"#475569",fontSize:13}}>No VPGs</span>}</div>);}

function Donut({data,size=80}){const total=data.reduce((a,b)=>a+b.value,0);if(!total)return<svg width={size} height={size}><circle cx={size/2} cy={size/2} r={size/2-8} fill="none" stroke="#1a2540" strokeWidth="8"/></svg>;const r=size/2-10;const c=2*Math.PI*r;let off=0;return(<svg width={size} height={size}>{data.map((d,i)=>{const dash=(d.value/total)*c;const el=(<circle key={i} cx={size/2} cy={size/2} r={r} fill="none" stroke={d.color} strokeWidth="10" strokeDasharray={dash+" "+(c-dash)} strokeDashoffset={-off} style={{transform:"rotate(-90deg)",transformOrigin:"50% 50%"}}/>);off+=dash;return el;})}<text x={size/2} y={size/2+5} textAnchor="middle" fill="#fff" fontSize="13" fontWeight="700">{total}</text></svg>);}

const _ZS=`@keyframes zerPulse{0%,100%{opacity:1}50%{opacity:.3}}@keyframes zerSpin{to{transform:rotate(360deg)}}`;
export default function ZertoPage({p, currentUser}){
  const[tab,setTab]=useState("dash");
  const[sites,setSites]=useState([]);
  const[selSite,setSelSite]=useState(null);
  const[dash,setDash]=useState(null);
  const[vpgs,setVpgs]=useState([]);
  const[vms,setVms]=useState([]);
  const[alerts,setAlerts]=useState([]);
  const[tasks,setTasks]=useState([]);
  const[events,setEvents]=useState([]);
  const[reports,setReports]=useState([]);
  const[auditLog,setAuditLog]=useState([]);
  const[loading,setLoading]=useState(false);
  const[loadMsg,setLoadMsg]=useState("");
  const[modal,setModal]=useState(null);
  const[addSite,setAddSite]=useState(false);
  const[newSite,setNewSite]=useState({name:"",host:"",port:443,username:"admin",password:"",site_type:"dc",notes:""});
  const[testResult,setTestResult]=useState(null);
  const[opForm,setOpForm]=useState({});
  const[opResult,setOpResult]=useState(null);
  const[opProgress,setOpProgress]=useState(null);
  const opPollRef=useRef(null);
  const[vmSearch,setVmSearch]=useState("");
  const[vpgSearch,setVpgSearch]=useState("");
  const[iopsHist,setIopsHist]=useState([]);
  const[tpHist,setTpHist]=useState([]);
  const[createVPGModal,setCreateVPGModal]=useState(false);
  const[vpgWizStep,setVpgWizStep]=useState(1);
  const[virtSites,setVirtSites]=useState([]);
  const[virtVMs,setVirtVMs]=useState([]);
  const[virtVMsLoading,setVirtVMsLoading]=useState(false);
  const[vmSearch2,setVmSearch2]=useState('');
  const[peerSites,setPeerSites]=useState([]);
  const[newVPG,setNewVPG]=useState({name:"",rpo_seconds:300,journal_hours:24,priority:"Medium",target_site_id:""});
  const iref=useRef(null);

  const role=(currentUser||{}).role||"viewer";
  const isAdmin=role==="admin";
  const isOperator=role==="admin"||role==="operator";

  const s=p||{bg:"#080c14",surface:"#0d1322",panel:"#111827",panelAlt:"#141e2e",border:"#1a2540",borderHi:"#243352",accent:"#3b82f6",cyan:"#06b6d4",green:"#10b981",yellow:"#f59e0b",red:"#ef4444",purple:"#8b5cf6",orange:"#f97316",text:"#f1f5f9",textSub:"#94a3b8",textMute:"#475569"};

  const loadSites=useCallback(async()=>{const d=await fetchZertoSites();setSites(d||[]);if(!selSite&&d&&d.length)setSelSite(d[0]);},[selSite]);
  const loadPeerSites=useCallback(async()=>{if(!selSite)return;const r=await fetchZertoPeerSites(selSite.id).catch(()=>[]);setPeerSites(Array.isArray(r)?r:[]);},[selSite]);
  useEffect(()=>{loadSites();},[]);
  useEffect(()=>{loadPeerSites();},[selSite]);

  const stopOpPolling=()=>{if(opPollRef.current){clearInterval(opPollRef.current);opPollRef.current=null;}};
  const OP_STEPS={
    test_failover:['Initiating DR Drill','Suspending replication','Booting VMs at recovery site','Running verification','DR Drill active'],
    stop_test:['Stopping DR Drill','Shutting down test VMs','Restoring replication','Cleanup complete'],
    live_failover:['Initiating Failover','Suspending source replication','Failing over VMs','Updating network routes','Failover complete'],
    commit_failover:['Committing Failover','Finalising VM state','Removing journals','Setting up reverse protection','Committed'],
    rollback_failover:['Rolling back','Restoring protected site','Resuming replication','Cleanup','Rollback complete'],
    planned_move:['Planned Move initiated','Quiescing VMs','Final sync','Starting at recovery site','Move complete'],
    failback:['Initiating Failback','Replicating to DC','Syncing data','Booting at protected site','Failback complete'],
  };
  const startOperationTracking=(taskId,siteId,opType,vpgName)=>{
    const steps=OP_STEPS[opType]||['Initiating','Processing','Executing','Finalising','Complete'];
    const entry=(msg)=>({time:new Date().toISOString(),msg});
    setOpProgress({taskId,siteId,opType,vpgName,steps,state:1,progress:0,currentStep:0,
      started:new Date().toISOString(),reason:'',polling:true,
      log:[entry('Started: '+opType+' on '+vpgName)]});
    stopOpPolling();
    opPollRef.current=setInterval(async()=>{
      try{
        const t=await fetchZertoTask(siteId,taskId);
        if(t&&!t.error){
          const done=t.state===5||t.state===4||t.state===7;
          const si=Math.min(Math.floor((t.progress/100)*(steps.length-1)),steps.length-1);
          setOpProgress(prev=>{if(!prev)return prev;
            const last=prev.log[prev.log.length-1];
            const msg=steps[si]+(t.progress>0?' ('+t.progress+'%)':'');
            const newLog=last&&last.msg===msg?prev.log:[...prev.log,{time:new Date().toISOString(),msg}].slice(-20);
            return{...prev,state:t.state,progress:t.progress,currentStep:si,reason:t.complete_reason||'',polling:!done,log:newLog};
          });
          if(done){stopOpPolling();setTimeout(()=>{},2000);}
        }
      }catch(e){console.warn('poll err',e);}
    },2500);
  };

  const loadData=useCallback(async()=>{
    if(!selSite)return;setLoading(true);
    try{
      if(tab==="dash"){setLoadMsg("Loading...");const d=await fetchZertoDashboard(selSite.id);setDash(d);if(d?.kpis){setIopsHist(prev=>[...prev.slice(-29),d.kpis.total_iops]);setTpHist(prev=>[...prev.slice(-29),d.kpis.total_throughput_mb]);}}
      else if(tab==="vpgs"){setLoadMsg("Loading VPGs...");setVpgs(await fetchZertoVPGs(selSite.id)||[]);}
      else if(tab==="vms"){setLoadMsg("Loading VMs...");setVms(await fetchZertoVMs(selSite.id)||[]);}
      else if(tab==="alerts"){setLoadMsg("Loading...");setAlerts(await fetchZertoAlerts(selSite.id)||[]);setTasks(await fetchZertoTasks(selSite.id)||[]);}
      else if(tab==="reports"){setLoadMsg("Loading...");setReports(await fetchZertoReports(selSite.id).then(r=>Array.isArray(r)?r:[]).catch(()=>[]));}
      else if(tab==="events"){setLoadMsg("Loading...");setEvents(await fetchZertoEvents(selSite.id)||[]);}
      else if(tab==="audit"){setLoadMsg("Loading audit...");setAuditLog(await fetchZertoAuditLog(selSite.id)||[]);}
      else if(tab==="ops"){setLoadMsg("Loading tasks...");setTasks(await fetchZertoTasks(selSite.id)||[]);}
      else if(tab==="sites"){setLoadMsg("Loading sites...");const d=await fetchZertoDashboard(selSite.id);setDash(d);}
    }finally{setLoading(false);setLoadMsg("");}
  },[selSite,tab]);

  useEffect(()=>{loadData();if(iref.current)clearInterval(iref.current);iref.current=setInterval(loadData,30000);return()=>clearInterval(iref.current);},[loadData]);

  const card={background:s.panel,border:"1px solid "+s.border,borderRadius:10,overflow:"hidden"};
  const kpiCard=(c)=>({background:s.panel,border:"1px solid "+s.border,borderRadius:10,padding:"14px 16px",borderTop:"3px solid "+c});
  const btn=(c,bg)=>({display:"inline-flex",alignItems:"center",gap:5,padding:"5px 12px",borderRadius:7,cursor:"pointer",border:"1px solid "+c+"50",background:bg||(c+"15"),color:c,fontSize:13,fontWeight:600});
  const ts=(t)=>({padding:"7px 14px",borderRadius:"7px 7px 0 0",cursor:"pointer",fontSize:13,fontWeight:600,border:"1px solid "+(tab===t?s.border:"transparent"),borderBottom:tab===t?"2px solid "+s.cyan:"1px solid transparent",color:tab===t?s.cyan:s.textSub,background:tab===t?s.panel:"transparent"});
  const tH={padding:"7px 10px",fontSize:12,fontWeight:700,textTransform:"uppercase",letterSpacing:".7px",color:s.textMute,borderBottom:"1px solid "+s.border,background:s.surface};
  const tD={padding:"7px 10px",fontSize:13,borderBottom:"1px solid "+s.border+"18"};
  const inp={background:s.panelAlt,border:"1px solid "+s.border,borderRadius:7,color:s.text,padding:"7px 10px",fontSize:13,width:"100%"};

  const SiteBar=()=>(<div style={{display:"flex",alignItems:"center",gap:10,padding:"0 0 14px 0",flexWrap:"wrap"}}>{sites.map(st=>(<div key={st.id} onClick={()=>setSelSite(st)} style={{padding:"6px 16px",borderRadius:8,cursor:"pointer",border:"1px solid "+(selSite?.id===st.id?s.cyan:s.border),background:selSite?.id===st.id?(s.cyan+"15"):s.panel,color:selSite?.id===st.id?s.cyan:s.text,fontSize:13,fontWeight:600,display:"flex",alignItems:"center",gap:8}}><span style={{width:8,height:8,borderRadius:"50%",background:st.status==="connected"?s.green:st.status==="unreachable"?s.red:s.yellow,display:"inline-block"}}/>{st.name}<span style={{fontSize:11,color:s.textMute}}>{st.site_type?.toUpperCase()}</span></div>))}<button onClick={()=>setAddSite(true)} style={btn(s.cyan)}>+ Add Site</button>{selSite&&<button onClick={async()=>{setTestResult(null);const r=await testZertoSite(selSite.id);setTestResult(r);loadSites();}} style={btn(s.green)}>Test</button>}<button onClick={loadData} style={btn(s.textSub)}>Refresh</button>{testResult&&<span style={{fontSize:12,color:testResult.ok?s.green:s.red,padding:"4px 10px",background:(testResult.ok?s.green:s.red)+"15",borderRadius:6}}>{testResult.ok?"Connected "+testResult.site_name:"Failed: "+testResult.error}</span>}</div>);

  const TABS=[{id:"dashboard",label:"Dashboard"},{id:"vpgs",label:"VPGs"},{id:"vms",label:"Protected VMs"},{id:"operations",label:"DR Operations"},{id:"alerts",label:"Alerts"+(dash?.kpis?.active_alerts>0?" ("+dash.kpis.active_alerts+")":"")},{id:"reports",label:"Reports"},{id:"events",label:"Events & Audit"},{id:"sites",label:"Sites"}];

  const DashboardTab=()=>{if(loading)return<div style={{color:s.textMute,padding:40,textAlign:"center"}}>Loading dashboard...</div>;if(!dash)return<div style={{color:s.textMute,padding:40,textAlign:"center"}}>No data  click Refresh</div>;const k=dash.kpis||{};const kpis=[{label:"VPGs",value:k.total_vpgs,sub:k.meeting_sla+" meeting SLA",c:s.cyan},{label:"VMs",value:k.total_vms,sub:"Protected",c:s.green},{label:"Protected",value:(k.protected_gb||0)+" GB",sub:"Storage",c:s.purple},{label:"Avg RPO",value:fmtRPO(k.avg_rpo_seconds),sub:"All VPGs",c:s.yellow},{label:"IOPS",value:(k.total_iops||0).toFixed(1),sub:"Replication",c:s.accent},{label:"Throughput",value:(k.total_throughput_mb||0).toFixed(2)+" MB/s",sub:"Network",c:s.orange}];const dd=[{label:"Meeting SLA",value:k.meeting_sla||0,color:s.green},{label:"Not Meeting",value:k.not_meeting_sla||0,color:s.red}].filter(d=>d.value>0);return(<div style={{display:"flex",flexDirection:"column",gap:14}}><div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:10}}>{kpis.map(k2=>(<div key={k2.label} style={kpiCard(k2.c)}><div style={{fontSize:11,color:s.textMute,textTransform:"uppercase",marginBottom:4}}>{k2.label}</div><div style={{fontSize:24,fontWeight:800,color:k2.c}}>{k2.value}</div><div style={{fontSize:11,color:s.textMute,marginTop:2}}>{k2.sub}</div></div>))}</div><div style={{display:"grid",gridTemplateColumns:"1fr 1fr 220px",gap:12}}><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,display:"flex",justifyContent:"space-between"}}><span style={{fontWeight:700}}>IOPS</span><span style={{fontWeight:800,color:s.accent}}>{(k.total_iops||0).toFixed(1)}</span></div><div style={{padding:"12px 14px"}}><Sparkline data={iopsHist.length?iopsHist:[0,0,0,0,0]} color={s.accent} width={280} height={55}/></div></div><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,display:"flex",justifyContent:"space-between"}}><span style={{fontWeight:700}}>Throughput MB/s</span><span style={{fontWeight:800,color:s.green}}>{(k.total_throughput_mb||0).toFixed(2)}</span></div><div style={{padding:"12px 14px"}}><Sparkline data={tpHist.length?tpHist:[0,0,0,0,0]} color={s.green} width={280} height={55}/></div></div><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,fontWeight:700}}>VPG Status</div><div style={{padding:14,display:"flex",flexDirection:"column",alignItems:"center",gap:10}}><Donut data={dd.length?dd:[{label:"None",value:1,color:"#1a2540"}]} size={80}/>{[{l:"Meeting SLA",c:s.green,v:k.meeting_sla||0},{l:"Not Meeting",c:s.red,v:k.not_meeting_sla||0}].map(d=>(<div key={d.l} style={{display:"flex",alignItems:"center",gap:6,fontSize:11,width:"100%"}}><span style={{width:8,height:8,borderRadius:"50%",background:d.c}}/><span style={{color:s.textSub}}>{d.l}</span><span style={{marginLeft:"auto",fontWeight:700,color:d.c}}>{d.v}</span></div>))}</div></div></div><div style={{display:"grid",gridTemplateColumns:"1fr 300px 260px",gap:12}}><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,fontWeight:700}}>VPG Health Grid</div><div style={{padding:14}}><VPGHealthGrid vpgs={dash.vpg_health||[]}/><div style={{display:"flex",gap:10,marginTop:8,flexWrap:"wrap"}}>{[["#10b981","Meeting SLA"],["#f59e0b","RPO Not Met"],["#ef4444","Not Meeting"],["#64748b","Initializing"]].map(([c,l])=>(<div key={l} style={{display:"flex",alignItems:"center",gap:4,fontSize:11,color:s.textSub}}><span style={{width:10,height:10,borderRadius:2,background:c}}/>{l}</div>))}</div></div></div><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,display:"flex",justifyContent:"space-between"}}><span style={{fontWeight:700}}>Active Alerts</span><span style={{fontSize:12,color:s.cyan,cursor:"pointer"}} onClick={()=>setTab("alerts")}>View All</span></div><div style={{maxHeight:200,overflowY:"auto"}}>{(dash.active_alerts||[]).slice(0,6).map((a,i)=>(<div key={i} style={{padding:"8px 14px",borderBottom:"1px solid "+s.border+"20",display:"flex",gap:8}}><span>{a.level==="error"?"":""}</span><div><div style={{fontSize:12}}>{a.description}</div><div style={{fontSize:10,color:s.textMute}}>{fmtRel(a.turned_on)}</div></div></div>))}{!(dash.active_alerts||[]).length&&<div style={{padding:20,textAlign:"center",color:s.textMute,fontSize:12}}>No active alerts </div>}</div></div><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,fontWeight:700}}>Running Tasks</div><div style={{maxHeight:200,overflowY:"auto"}}>{(dash.running_tasks||[]).slice(0,5).map((t,i)=>(<div key={i} style={{padding:"8px 14px",borderBottom:"1px solid "+s.border+"20"}}><div style={{fontSize:12}}>{t.type||"Task"}</div><div style={{display:"flex",alignItems:"center",gap:6,marginTop:4}}><div style={{flex:1,height:4,background:s.border,borderRadius:2,overflow:"hidden"}}><div style={{width:(t.progress||0)+"%",height:"100%",background:s.cyan,borderRadius:2}}/></div><span style={{fontSize:10,color:s.textMute}}>{t.progress||0}%</span></div></div>))}{!(dash.running_tasks||[]).length&&<div style={{padding:20,textAlign:"center",color:s.textMute,fontSize:12}}>No tasks</div>}</div></div></div></div>);};

  const VPGsTab=()=>{const filtered=vpgs.filter(v=>!vpgSearch||v.name.toLowerCase().includes(vpgSearch.toLowerCase()));return(<div style={{display:"flex",flexDirection:"column",gap:12}}><div style={{display:"flex",alignItems:"center",gap:10,flexWrap:"wrap"}}><input placeholder="Search VPGs..." value={vpgSearch} onChange={e=>setVpgSearch(e.target.value)} style={{...inp,width:200}}/><span style={{fontSize:12,color:s.textMute}}>{filtered.length} VPGs</span>{isAdmin&&<button onClick={()=>{setNewVPG({name:"",rpo_seconds:300,journal_hours:24,priority:"Medium",target_site_id:peerSites[0]?.SiteIdentifier||""});setCreateVPGModal(true);}} style={{...btn(s.cyan),marginLeft:"auto"}}>+ Create VPG</button>}</div><div style={card}><table style={{width:"100%",borderCollapse:"collapse"}}><thead><tr>{["VPG","STATUS","RPO","VMS","IOPS","THROUGHPUT","JOURNAL","SOURCE  TARGET","ACTIONS"].map(h=>(<th key={h} style={tH}>{h}</th>))}</tr></thead><tbody>{filtered.map((v,i)=>(<tr key={i}><td style={{...tD,fontWeight:700}}>{v.name}</td><td style={tD}><span style={{padding:"3px 8px",borderRadius:4,fontSize:11,fontWeight:700,background:SC(v.status_text)+"20",color:SC(v.status_text)}}>{v.status_text}</span></td><td style={{...tD,color:s.cyan}}>{fmtRPO(v.rpo_seconds)}</td><td style={tD}>{v.vms_count}</td><td style={tD}>{v.iops?.toFixed(1)}</td><td style={tD}>{v.throughput_mb?.toFixed(2)} MB/s</td><td style={tD}>{fmtGB(v.journal_mb)}</td><td style={{...tD,fontSize:11}}>{v.source_site}  {v.target_site}</td><td style={{...tD,whiteSpace:"nowrap"}}><div style={{display:"flex",gap:4,flexWrap:"wrap"}}>{isOperator&&<button onClick={()=>setModal({type:"test_failover",vpg_id:v.id,vpg:v})} style={{...btn(s.yellow),fontSize:11,padding:"3px 8px"}}>DR Drill</button>}{isOperator&&<button onClick={()=>setModal({type:"live_failover",vpg_id:v.id,vpg:v})} style={{...btn(s.red),fontSize:11,padding:"3px 8px"}}>Failover</button>}{isOperator&&<button onClick={()=>setModal({type:"failback",vpg_id:v.id,vpg:v})} style={{...btn(s.green),fontSize:11,padding:"3px 8px"}}>Failback</button>}{isAdmin&&<button onClick={async()=>{if(window.confirm("Delete VPG "+v.name+"? This removes Zerto protection.")){const r=await deleteZertoVPG(selSite.id,v.id).catch(e=>({error:e.message}));r.ok?setTimeout(loadData,1500):alert("Error: "+(r.error||"Failed"));}}} style={{...btn(s.red),fontSize:11,padding:"3px 8px",opacity:.7}}>Delete</button>}</div></td></tr>))}{!filtered.length&&<tr><td colSpan={9} style={{padding:30,textAlign:"center",color:s.textMute}}>{loading?"Loading...":"No VPGs found"}</td></tr>}</tbody></table></div></div>);};
  
  const VMsTab=()=>{const fl=vms.filter(v=>!vmSearch||v.name?.toLowerCase().includes(vmSearch.toLowerCase())||v.vpg_name?.toLowerCase().includes(vmSearch.toLowerCase()));return(<div style={{display:"flex",flexDirection:"column",gap:10}}><div style={{display:"flex",gap:10,alignItems:"center"}}><input placeholder="Search VMs..." value={vmSearch} onChange={e=>setVmSearch(e.target.value)} style={{...inp,width:260}}/><span style={{fontSize:13,color:s.textMute}}>{fl.length} VMs</span></div><div style={card}><table style={{width:"100%",borderCollapse:"collapse"}}><thead><tr>{["VM Name","VPG","Status","RPO","IOPS","Journal","Protected Site","Recovery Site"].map(h=>(<th key={h} style={tH}>{h}</th>))}</tr></thead><tbody>{fl.map(v=>(<tr key={v.id} onMouseEnter={e=>Array.from(e.currentTarget.cells).forEach(c=>c.style.background=s.accent+"08")} onMouseLeave={e=>Array.from(e.currentTarget.cells).forEach(c=>c.style.background="")}><td style={tD}><b>{v.name}</b></td><td style={tD}>{v.vpg_name}</td><td style={tD}><span style={{padding:"2px 7px",borderRadius:4,fontSize:11,fontWeight:700,background:SC(v.status_text)+"18",color:SC(v.status_text)}}>{v.status_text}</span></td><td style={{...tD,color:s.cyan}}>{fmtRPO(v.rpo_seconds)}</td><td style={tD}>{(v.iops||0).toFixed(1)}</td><td style={tD}>{fmtGB(v.journal_mb)}</td><td style={{...tD,fontSize:11}}>{v.protected_site}</td><td style={{...tD,fontSize:11}}>{v.recovery_site}</td></tr>))}{!fl.length&&<tr><td colSpan={8} style={{padding:30,textAlign:"center",color:s.textMute}}>{loading?"Loading...":"No VMs"}</td></tr>}</tbody></table></div></div>);};

  const OpsTab=()=>{const ops=[{id:"test_failover",label:"Test Failover (DR Drill)",c:s.yellow,icon:"",desc:"Non-disruptive test. VMs boot at recovery site without stopping production."},{id:"stop_test",label:"Stop Test Failover",c:s.orange,icon:"",desc:"Cleanly stop an ongoing DR drill."},{id:"live_failover",label:"LIVE FAILOVER",c:s.red,icon:"",desc:"Emergency failover  moves workloads to recovery site."},{id:"commit_failover",label:"Commit Failover",c:s.green,icon:"",desc:"Confirm live failover is complete."},{id:"rollback_failover",label:"Rollback Failover",c:s.purple,icon:"",desc:"Undo a failover before committing."},{id:"planned_move",label:"Planned Move",c:s.cyan,icon:"",desc:"Graceful planned failover with full sync."},{id:"failback",label:"Failback",c:s.accent,icon:"",desc:"Return workloads to original protected site."}];return(<div style={{display:"flex",flexDirection:"column",gap:14}}><div style={{padding:12,background:s.yellow+"10",border:"1px solid "+s.yellow+"30",borderRadius:8,fontSize:13,color:s.yellow}}> DR Operations affect production workloads. Verify with your team before executing any failover.</div><div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:12}}>{ops.map(op=>(<div key={op.id} style={{...card,padding:16,borderLeft:"3px solid "+op.c}}><div style={{fontSize:20,marginBottom:6}}>{op.icon}</div><div style={{fontSize:14,fontWeight:700,color:op.c,marginBottom:6}}>{op.label}</div><div style={{fontSize:12,color:s.textSub,marginBottom:12,lineHeight:1.5}}>{op.desc}</div><div style={{marginBottom:10}}><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4}}>SELECT VPG</label><select style={{...inp,fontSize:12}} onChange={e=>setOpForm(f=>({...f,[op.id+"_vpg"]:e.target.value}))}><option value=""> Choose VPG </option>{vpgs.map(v=><option key={v.id} value={v.id}>{v.name} ({v.status_text})</option>)}</select></div>{op.id==="stop_test"&&<div style={{marginBottom:10}}><input placeholder="Notes..." style={{...inp,fontSize:12}} onChange={e=>setOpForm(f=>({...f,stop_notes:e.target.value}))}/></div>}{op.id==="commit_failover"&&<div style={{display:"flex",gap:6,alignItems:"center",marginBottom:10,fontSize:12}}><input type="checkbox" onChange={e=>setOpForm(f=>({...f,reverse_protection:e.target.checked}))}/><span style={{color:s.textSub}}>Enable Reverse Protection</span></div>}<button onClick={()=>setModal({type:op.id,vpg_id:opForm[op.id+"_vpg"],op_form:opForm})} disabled={!opForm[op.id+"_vpg"]} style={{...btn(op.c),width:"100%",justifyContent:"center",opacity:opForm[op.id+"_vpg"]?1:.5,cursor:opForm[op.id+"_vpg"]?"pointer":"not-allowed"}}>Execute {op.icon}</button></div>))}</div>{opResult&&<div style={{padding:12,background:(opResult.error?s.red:s.green)+"10",border:"1px solid "+(opResult.error?s.red:s.green)+"30",borderRadius:8,fontSize:13}}>{opResult.error?"Error: "+opResult.error:"Operation initiated successfully."}</div>}</div>);};

  const AlertsTab=()=>(<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,fontWeight:700}}>Active Alerts</div><div>{alerts.filter(a=>!a.is_dismissed).map(a=>(<div key={a.id} style={{padding:"10px 14px",borderBottom:"1px solid "+s.border+"20",display:"flex",justifyContent:"space-between",gap:10}}><div><div style={{display:"flex",alignItems:"center",gap:6,marginBottom:3}}><span style={{width:8,height:8,borderRadius:"50%",background:a.level==="error"?s.red:s.yellow}}/><b>{a.description}</b></div><div style={{fontSize:11,color:s.textMute}}>{a.entity}  {fmtRel(a.turned_on)}</div></div><button onClick={async()=>{await dismissZertoAlert(selSite?.id,a.id);loadData();}} style={{...btn(s.textMute),padding:"3px 8px",fontSize:11}}>Dismiss</button></div>))}{!alerts.filter(a=>!a.is_dismissed).length&&<div style={{padding:20,textAlign:"center",color:s.textMute}}>No active alerts </div>}</div></div><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,fontWeight:700}}>Running Tasks</div><div>{tasks.map(t=>(<div key={t.id} style={{padding:"10px 14px",borderBottom:"1px solid "+s.border+"20"}}><div style={{fontWeight:600,fontSize:13}}>{t.type}</div><div style={{display:"flex",gap:6,alignItems:"center",marginTop:6}}><div style={{flex:1,height:5,background:s.border,borderRadius:3,overflow:"hidden"}}><div style={{width:(t.progress||0)+"%",height:"100%",background:s.cyan,borderRadius:3}}/></div><span style={{fontSize:11,color:s.textMute}}>{t.progress||0}%</span><span style={{fontSize:11,padding:"1px 6px",borderRadius:4,background:(t.status==="Success"?s.green:t.status==="Failed"?s.red:s.cyan)+"18",color:t.status==="Success"?s.green:t.status==="Failed"?s.red:s.cyan}}>{t.status}</span></div></div>))}{!tasks.length&&<div style={{padding:20,textAlign:"center",color:s.textMute}}>No tasks</div>}</div></div></div>);

  const ReportsTab=()=>(<div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,fontWeight:700}}>Recovery Reports</div><table style={{width:"100%",borderCollapse:"collapse"}}><thead><tr>{["VPG","Test Type","Started","Duration","RPO Achieved","Status","Initiator"].map(h=>(<th key={h} style={tH}>{h}</th>))}</tr></thead><tbody>{reports.map((r,i)=>(<tr key={i}><td style={tD}><b>{r.vpg_name}</b></td><td style={tD}>{r.test_type}</td><td style={{...tD,fontSize:11}}>{fmtDate(r.started)}</td><td style={tD}>{r.duration_min||""} min</td><td style={{...tD,color:s.cyan}}>{fmtRPO(r.rpo_achieved)}</td><td style={tD}><span style={{padding:"2px 7px",borderRadius:4,fontSize:11,fontWeight:700,background:(r.result==="Success"?s.green:s.red)+"18",color:r.result==="Success"?s.green:s.red}}>{r.result||""}</span></td><td style={{...tD,fontSize:11}}>{r.initiator||""}</td></tr>))}{!reports.length&&<tr><td colSpan={7} style={{padding:30,textAlign:"center",color:s.textMute}}>{loading?"Loading...":"No reports"}</td></tr>}</tbody></table></div>);

  const EventsTab=()=>(<div style={{display:"flex",flexDirection:"column",gap:12}}><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,fontWeight:700}}>ZVM Events</div><table style={{width:"100%",borderCollapse:"collapse"}}><thead><tr>{["Time","Description","Type","User","Site"].map(h=>(<th key={h} style={tH}>{h}</th>))}</tr></thead><tbody>{events.slice(0,50).map((e,i)=>(<tr key={i}><td style={{...tD,fontSize:11}}>{fmtDate(e.timestamp)}</td><td style={tD}>{e.description}</td><td style={{...tD,fontSize:11}}>{e.type}</td><td style={{...tD,fontSize:11}}>{e.user}</td><td style={{...tD,fontSize:11}}>{e.site}</td></tr>))}{!events.length&&<tr><td colSpan={5} style={{padding:30,textAlign:"center",color:s.textMute}}>{loading?"Loading...":"No events"}</td></tr>}</tbody></table></div><div style={card}><div style={{padding:"10px 14px",borderBottom:"1px solid "+s.border,fontWeight:700}}>DR Audit Trail</div><table style={{width:"100%",borderCollapse:"collapse"}}><thead><tr>{["Time","Action","VPG","Detail","Site","Status"].map(h=>(<th key={h} style={tH}>{h}</th>))}</tr></thead><tbody>{auditLog.map((a,i)=>(<tr key={i}><td style={{...tD,fontSize:11}}>{fmtDate(a.created_at)}</td><td style={tD}><b style={{color:s.cyan}}>{a.action}</b></td><td style={tD}>{a.vpg_name}</td><td style={{...tD,fontSize:12}}>{a.detail}</td><td style={{...tD,fontSize:11}}>{a.site_name}</td><td style={tD}><span style={{padding:"2px 7px",borderRadius:4,fontSize:11,fontWeight:700,background:(a.status==="Success"?s.green:s.red)+"18",color:a.status==="Success"?s.green:s.red}}>{a.status}</span></td></tr>))}{!auditLog.length&&<tr><td colSpan={6} style={{padding:30,textAlign:"center",color:s.textMute}}>No audit records</td></tr>}</tbody></table></div></div>);

  const SitesTab=()=>(<div style={{display:"flex",flexDirection:"column",gap:12}}><div style={{display:"flex",justifyContent:"flex-end"}}><button onClick={()=>setAddSite(true)} style={btn(s.cyan)}>+ Add Site</button></div><div style={{display:"grid",gridTemplateColumns:"repeat(2,1fr)",gap:12}}>{sites.map(st=>(<div key={st.id} style={{...card,padding:16,borderLeft:"3px solid "+(st.status==="connected"?s.green:s.red)}}><div style={{display:"flex",justifyContent:"space-between"}}><div><div style={{fontSize:16,fontWeight:700}}>{st.name}</div><div style={{fontSize:12,color:s.textMute,marginTop:2}}><span style={{padding:"2px 8px",borderRadius:4,background:(st.site_type==="dc"?s.accent:s.purple)+"20",color:st.site_type==="dc"?s.accent:s.purple,marginRight:6,fontWeight:700,fontSize:11}}>{st.site_type?.toUpperCase()}</span>{st.host}:{st.port}</div></div><span style={{width:10,height:10,borderRadius:"50%",background:st.status==="connected"?s.green:st.status==="unreachable"?s.red:s.yellow,display:"inline-block",boxShadow:"0 0 6px "+(st.status==="connected"?s.green:s.red)}}/></div><div style={{marginTop:12,display:"flex",flexDirection:"column",gap:5}}>{[["Status",st.status],["Last Check",fmtDate(st.last_check)],["Notes",st.notes]].map(([k,v])=>v?(<div key={k} style={{display:"flex",gap:8,fontSize:12}}><span style={{color:s.textMute,minWidth:90}}>{k}:</span><span>{v}</span></div>):null)}</div><div style={{display:"flex",gap:8,marginTop:14}}><button onClick={async()=>{const r=await testZertoSite(st.id);alert(r.ok?"Connected: "+r.site_name:"Failed: "+r.error);loadSites();}} style={btn(s.green)}>Test</button><button onClick={async()=>{if(window.confirm("Delete "+st.name+"?")){await deleteZertoSite(st.id);loadSites();}}} style={btn(s.red)}>Delete</button></div></div>))}</div></div>);

  const ConfirmModal=()=>{if(!modal)return null;const vpg=modal.vpg||vpgs.find(v=>v.id===modal.vpg_id);const TL={test_failover:"Start DR Drill",stop_test:"Stop Test Failover",live_failover:"LIVE FAILOVER",commit_failover:"Commit Failover",rollback_failover:"Rollback Failover",planned_move:"Planned Move",failback:"Failback"};const TC={test_failover:s.yellow,stop_test:s.orange,live_failover:s.red,commit_failover:s.green,rollback_failover:s.purple,planned_move:s.cyan,failback:s.accent};const c=TC[modal.type]||s.accent;const execute=async()=>{const vid=vpg?.id;const vn=vpg?.name||"";const sid=selSite?.id;let r;if(modal.type==="test_failover")r=await zertoTestFailover(sid,vid,vn);else if(modal.type==="stop_test")r=await zertoStopTestFailover(sid,vid,vn,true,modal.notes||"");else if(modal.type==="live_failover")r=await zertoLiveFailover(sid,vid,vn,{});else if(modal.type==="commit_failover")r=await zertoCommitFailover(sid,vid,vn,modal.reverse||false);else if(modal.type==="rollback_failover")r=await zertoRollbackFailover(sid,vid,vn);else if(modal.type==="planned_move")r=await zertoMoveVPG(sid,vid,vn,{});else if(modal.type==="failback")r=await zertoFailback(sid,vid,vn,{});setOpResult(r);setModal(null);const tid=r&&(r.task_id||r.taskId||r.TaskIdentifier);if(tid&&selSite){startOperationTracking(tid,selSite.id,modal.type,vpg?.name||modal.vpg_id||'VPG');}else{setTimeout(loadData,2000);}};return(<div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.6)",backdropFilter:"blur(4px)",zIndex:300,display:"flex",alignItems:"center",justifyContent:"center"}}><div style={{background:s.panel,border:"1px solid "+c+"40",borderRadius:14,padding:28,width:460,maxWidth:"95vw",boxShadow:"0 0 40px "+c+"15"}}><div style={{fontSize:18,fontWeight:700,color:c,marginBottom:8}}>{TL[modal.type]}</div><div style={{fontSize:13,color:s.textSub,marginBottom:16}}>VPG: <b style={{color:s.text}}>{vpg?.name||modal.vpg_id||""}</b></div>{modal.type==="live_failover"&&<div style={{padding:12,background:s.red+"15",border:"1px solid "+s.red+"30",borderRadius:8,fontSize:12,color:s.red,marginBottom:16}}> LIVE FAILOVER  Production workloads will be moved to recovery site. This cannot be undone without Rollback.</div>}{modal.type==="stop_test"&&<div style={{marginBottom:16}}><input style={inp} placeholder="Notes..." onChange={e=>setModal(m=>({...m,notes:e.target.value}))}/></div>}{modal.type==="commit_failover"&&<div style={{display:"flex",gap:8,alignItems:"center",marginBottom:16,fontSize:12}}><input type="checkbox" onChange={e=>setModal(m=>({...m,reverse:e.target.checked}))}/><span style={{color:s.textSub}}>Enable Reverse Protection</span></div>}<div style={{display:"flex",gap:10,justifyContent:"flex-end"}}><button onClick={()=>setModal(null)} style={btn(s.textSub)}>Cancel</button><button onClick={execute} style={{...btn(c),background:c+"25",fontWeight:700}}>Confirm</button></div></div></div>);};

  const AddSiteModal=()=>!addSite?null:(<div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.6)",backdropFilter:"blur(4px)",zIndex:300,display:"flex",alignItems:"center",justifyContent:"center"}}><div style={{background:s.panel,border:"1px solid "+s.border,borderRadius:14,padding:28,width:500,maxWidth:"95vw"}}><div style={{fontSize:18,fontWeight:700,marginBottom:16}}>Add ZVM Site</div><div style={{display:"flex",flexDirection:"column",gap:12}}>{[{k:"name",l:"Site Name",p:"e.g. DR-Chicago"},{k:"host",l:"Host / IP",p:"172.17.x.x"},{k:"port",l:"Port",p:"443"},{k:"username",l:"Username",p:"admin"},{k:"password",l:"Password",p:"",t:"password"},{k:"notes",l:"Notes",p:"Optional"}].map(f=>(<div key={f.k}><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase"}}>{f.l}</label><input type={f.t||"text"} placeholder={f.p} style={inp} onChange={e=>setNewSite(n=>({...n,[f.k]:e.target.value}))}/></div>))}<div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase"}}>Site Type</label><select style={inp} onChange={e=>setNewSite(n=>({...n,site_type:e.target.value}))}><option value="dc">DC (Protected)</option><option value="dr">DR (Recovery)</option></select></div></div><div style={{display:"flex",gap:10,marginTop:20,justifyContent:"flex-end"}}><button onClick={()=>setAddSite(false)} style={btn(s.textSub)}>Cancel</button><button onClick={async()=>{await createZertoSite(newSite);setAddSite(false);loadSites();}} style={btn(s.cyan)}>Add Site</button></div></div></div>);

  const CreateVPGModal=()=>{
    if(!createVPGModal||!isAdmin)return null;
    const prioOpts=["Low","Medium","High"];
    const step1Ok=!!(newVPG.name&&newVPG.name.trim());
    const totalSteps=3;
    const loadVirtSites=async()=>{
      if(!selSite)return;
      const r=await fetchZertoVirtSites(selSite.id).catch(()=>[]);
      setVirtSites(Array.isArray(r)?r:[]);
    };
    const loadVirtVMs=async(vsId)=>{
      if(!vsId||!selSite)return;
      setVirtVMsLoading(true);setVirtVMs([]);
      const r=await fetchZertoVirtSiteVMs(selSite.id,vsId).catch(()=>[]);
      setVirtVMs(Array.isArray(r)?r:[]);
      setVirtVMsLoading(false);
    };
    const filtVMs=(virtVMs||[]).filter(v=>{
      if(!vmSearch2)return true;
      const q=vmSearch2.toLowerCase();
      return(v.VmName||v.vmName||"").toLowerCase().includes(q)||(v.DatacenterName||"").toLowerCase().includes(q)||(v.HostName||"").toLowerCase().includes(q);
    });
    const selVmIds=newVPG.vm_ids||[];
    const toggleVM=(id)=>setNewVPG(n=>({...n,vm_ids:selVmIds.includes(id)?selVmIds.filter(x=>x!==id):[...selVmIds,id]}));
    const selAllVMs=()=>setNewVPG(n=>({...n,vm_ids:filtVMs.map(v=>v.VmIdentifier||v.vmIdentifier)}));
    const clearAllVMs=()=>setNewVPG(n=>({...n,vm_ids:[]}));
    const closeWiz=()=>{setCreateVPGModal(false);setVpgWizStep(1);setVirtSites([]);setVirtVMs([]);setVmSearch2('');};
    const StepDot=({n:sn})=>{
      const done=vpgWizStep>sn;const active=vpgWizStep===sn;
      return(<div style={{display:"flex",alignItems:"center",gap:6}}>
        <div style={{width:26,height:26,borderRadius:"50%",background:done?s.green:active?s.cyan:"transparent",border:"2px solid "+(done?s.green:active?s.cyan:s.textMute),display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,fontWeight:700,color:done||active?s.panel:s.textMute,flexShrink:0}}>{done?"v":sn}</div>
        <span style={{fontSize:11,color:active?s.text:done?s.textSub:s.textMute,fontWeight:active?700:400,whiteSpace:"nowrap"}}>{sn===1?"Settings":sn===2?"Select VMs":"Review"}</span>
      </div>);
    };
    return(<div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.65)",backdropFilter:"blur(4px)",zIndex:400,display:"flex",alignItems:"center",justifyContent:"center"}}>
      <div style={{background:s.panel,border:"1px solid "+s.cyan+"40",borderRadius:14,width:640,maxWidth:"97vw",boxShadow:"0 0 40px "+s.cyan+"10",display:"flex",flexDirection:"column",maxHeight:"92vh",overflow:"hidden"}}>
        <div style={{padding:"20px 24px 14px",background:s.surface,borderBottom:"1px solid "+s.border}}>
          <div style={{fontSize:17,fontWeight:700,color:s.cyan,marginBottom:2}}>Create New VPG</div>
          <div style={{fontSize:11,color:s.textMute,marginBottom:14}}>Configure settings, select VMs, then create the protection group in Zerto</div>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <StepDot n={1}/><div style={{flex:1,height:2,background:vpgWizStep>1?s.green:s.border,transition:"background .3s",borderRadius:1}}/><StepDot n={2}/><div style={{flex:1,height:2,background:vpgWizStep>2?s.green:s.border,transition:"background .3s",borderRadius:1}}/><StepDot n={3}/>
          </div>
        </div>
        <div style={{padding:"20px 24px",flex:1,overflowY:"auto"}}>
          {vpgWizStep===1&&(<div style={{display:"flex",flexDirection:"column",gap:14}}>
            <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>VPG Name *</label><input placeholder="e.g. WebApp-VPG" value={newVPG.name} style={inp} onChange={e=>setNewVPG(n=>({...n,name:e.target.value}))}/></div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>RPO (seconds)</label><input type="number" value={newVPG.rpo_seconds} style={inp} onChange={e=>setNewVPG(n=>({...n,rpo_seconds:+e.target.value}))}/></div>
              <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>Journal History (hours)</label><input type="number" value={newVPG.journal_hours} style={inp} onChange={e=>setNewVPG(n=>({...n,journal_hours:+e.target.value}))}/></div>
            </div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>Priority</label><select style={inp} value={newVPG.priority} onChange={e=>setNewVPG(n=>({...n,priority:e.target.value}))}>{prioOpts.map(p=>(<option key={p}>{p}</option>))}</select></div>
              <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>Recovery Site</label><select style={inp} value={newVPG.target_site_id} onChange={e=>setNewVPG(n=>({...n,target_site_id:e.target.value}))}>{peerSites.map(ps=>(<option key={ps.SiteIdentifier} value={ps.SiteIdentifier}>{ps.PeerSiteName}</option>))}{!peerSites.length&&<option value="">No peer sites</option>}</select></div>
            </div>
          </div>)}
          {vpgWizStep===2&&(<div>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:12,flexWrap:"wrap"}}>
              <input placeholder="Search by name, datacenter, host..." value={vmSearch2} style={{...inp,flex:1,minWidth:180,margin:0}} onChange={e=>setVmSearch2(e.target.value)}/>
              {virtSites.length>0&&(<select style={{...inp,margin:0,width:200}} defaultValue="" onChange={e=>loadVirtVMs(e.target.value)}>
                <option value="" disabled>-- Select vCenter site --</option>
                {virtSites.map(vs=>(<option key={vs.SiteIdentifier||vs.siteIdentifier} value={vs.SiteIdentifier||vs.siteIdentifier}>{vs.VirtualizationSiteName||vs.SiteName||vs.siteIdentifier}</option>))}
              </select>)}
              {virtSites.length===0&&(<button onClick={loadVirtSites} style={{...btn(s.cyan),padding:"6px 14px",fontSize:12}}>Load vCenter Sites</button>)}
              <span style={{fontSize:11,color:s.cyan,fontWeight:700,minWidth:70}}>{selVmIds.length} VM{selVmIds.length!==1?"s":""} selected</span>
            </div>
            {selVmIds.length>0&&(<div style={{display:"flex",flexWrap:"wrap",gap:5,marginBottom:10,padding:"8px 10px",background:s.cyan+"08",borderRadius:6,border:"1px solid "+s.cyan+"20"}}>
              {selVmIds.map(id=>{const vm=virtVMs.find(v=>(v.VmIdentifier||v.vmIdentifier)===id);return(<span key={id} style={{background:s.cyan+"22",border:"1px solid "+s.cyan+"40",borderRadius:4,padding:"2px 8px 2px 7px",fontSize:11,color:s.cyan,display:"inline-flex",alignItems:"center",gap:5}}>{vm?(vm.VmName||vm.vmName||id):id}<span onClick={(e)=>{e.stopPropagation();toggleVM(id);}} style={{cursor:"pointer",color:s.textMute,fontSize:12,lineHeight:1}}>&times;</span></span>);})}
            </div>)}
            <div style={{background:s.surface,borderRadius:8,border:"1px solid "+s.border,overflow:"hidden"}}>
              <div style={{display:"grid",gridTemplateColumns:"36px 1fr 150px 90px",padding:"7px 12px",borderBottom:"1px solid "+s.border,background:s.panel+"80"}}>
                <div><input type="checkbox" title="Select all" onChange={e=>e.target.checked?selAllVMs():clearAllVMs()} checked={filtVMs.length>0&&filtVMs.every(v=>selVmIds.includes(v.VmIdentifier||v.vmIdentifier))} style={{accentColor:s.cyan}}/></div>
                {["VM Name","Datacenter / Host","Power"].map((h,i)=>(<div key={i} style={{fontSize:10,color:s.textMute,fontWeight:700,textTransform:"uppercase",letterSpacing:".5px"}}>{h}</div>))}
              </div>
              <div style={{maxHeight:280,overflowY:"auto"}}>
                {virtVMsLoading&&<div style={{padding:28,textAlign:"center",color:s.textMute,fontSize:12}}>Loading VMs from vCenter...</div>}
                {!virtVMsLoading&&virtVMs.length===0&&(<div style={{padding:28,textAlign:"center",color:s.textMute,fontSize:12}}>
                  {virtSites.length===0?"Click \"Load vCenter Sites\", then select a site to browse VMs":"Select a vCenter site from the dropdown above to load VMs"}
                </div>)}
                {!virtVMsLoading&&virtVMs.length>0&&filtVMs.length===0&&<div style={{padding:16,textAlign:"center",color:s.textMute,fontSize:12}}>No VMs match your search</div>}
                {!virtVMsLoading&&filtVMs.map((vm,i)=>{
                  const id=vm.VmIdentifier||vm.vmIdentifier;
                  const sel=selVmIds.includes(id);
                  const power=vm.PowerStatus||vm.powerStatus||vm.Status||"";
                  const pOn=power.toLowerCase()==="on"||power==="1";
                  const pOff=power.toLowerCase()==="off"||power==="0";
                  const pColor=pOn?s.green:pOff?s.textMute:s.yellow;
                  return(<div key={id||i} onClick={()=>toggleVM(id)} style={{display:"grid",gridTemplateColumns:"36px 1fr 150px 90px",padding:"9px 12px",borderBottom:"1px solid "+s.border+"40",cursor:"pointer",background:sel?s.cyan+"0B":"transparent",transition:"background .1s"}}>
                    <div onClick={e=>e.stopPropagation()}><input type="checkbox" checked={sel} onChange={()=>toggleVM(id)} style={{accentColor:s.cyan}}/></div>
                    <div style={{fontSize:12,color:s.text,fontWeight:sel?600:400,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{vm.VmName||vm.vmName||id}</div>
                    <div style={{fontSize:11,color:s.textMute,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{[vm.DatacenterName||vm.datacenterName,vm.HostName||vm.hostName].filter(Boolean).join(" / ")||""}</div>
                    <div style={{fontSize:11,color:pColor,fontWeight:600}}>{pOn?"On":pOff?"Off":power||""}</div>
                  </div>);
                })}
              </div>
            </div>
          </div>)}
          {vpgWizStep===3&&(<div style={{display:"flex",flexDirection:"column",gap:14}}>
            <div style={{background:s.surface,borderRadius:8,padding:"14px 16px",border:"1px solid "+s.border}}>
              <div style={{fontSize:11,color:s.textMute,fontWeight:700,textTransform:"uppercase",letterSpacing:".5px",marginBottom:10}}>VPG Configuration</div>
              {[["Name",newVPG.name],["RPO",newVPG.rpo_seconds+" seconds"],["Journal History",newVPG.journal_hours+" hours"],["Priority",newVPG.priority],["Recovery Site",(peerSites.find(p=>p.SiteIdentifier===newVPG.target_site_id)||{}).PeerSiteName||newVPG.target_site_id||""]].map(([k,v])=>(<div key={k} style={{display:"flex",justifyContent:"space-between",padding:"5px 0",borderBottom:"1px solid "+s.border+"30",fontSize:13}}><span style={{color:s.textMute}}>{k}</span><span style={{color:s.text,fontWeight:600}}>{v}</span></div>))}
            </div>
            <div style={{background:s.surface,borderRadius:8,padding:"14px 16px",border:"1px solid "+s.border}}>
              <div style={{fontSize:11,color:s.textMute,fontWeight:700,textTransform:"uppercase",letterSpacing:".5px",marginBottom:10}}>VMs to Protect <span style={{color:s.cyan}}>({selVmIds.length})</span></div>
              {selVmIds.length===0?(<div style={{fontSize:12,color:s.yellow}}><b>No VMs selected.</b> The VPG will be created empty  you can add VMs later from the Zerto console.</div>):(<div style={{display:"flex",flexWrap:"wrap",gap:5}}>{selVmIds.map(id=>{const vm=virtVMs.find(v=>(v.VmIdentifier||v.vmIdentifier)===id);return(<span key={id} style={{background:s.green+"15",border:"1px solid "+s.green+"35",borderRadius:4,padding:"3px 8px",fontSize:11,color:s.green}}>{vm?(vm.VmName||vm.vmName||id):id}</span>);})}</div>)}
            </div>
          </div>)}
        </div>
        <div style={{padding:"14px 24px",borderTop:"1px solid "+s.border,background:s.surface,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <button onClick={()=>vpgWizStep===1?closeWiz():setVpgWizStep(n=>n-1)} style={btn(s.textSub)}>{vpgWizStep===1?"Cancel":"← Back"}</button>
          <span style={{fontSize:11,color:s.textMute}}>Step {vpgWizStep} of {totalSteps}</span>
          {vpgWizStep<3&&(<button disabled={vpgWizStep===1&&!step1Ok} onClick={()=>{if(vpgWizStep===1)loadVirtSites();setVpgWizStep(n=>n+1);}} style={{...btn(s.cyan),background:s.cyan+"22",fontWeight:700,opacity:vpgWizStep===1&&!step1Ok?.4:1}}>Next →</button>)}
          {vpgWizStep===3&&(<button onClick={async()=>{const r=await createZertoVPG(selSite.id,newVPG).catch(e=>({error:e.message}));if(r&&(r.ok||r.result)){closeWiz();alert("VPG \""+newVPG.name+"\" created with "+selVmIds.length+" VM(s) protected!");}else{alert("Error: "+(r&&r.error?""+r.error:"Creation failed"));}}} style={{...btn(s.cyan),background:s.cyan+"22",fontWeight:700}}>🚀 Create VPG</button>)}
        </div>
      </div>
    </div>);
  };



  const OperationProgressDrawer=()=>{
    if(!opProgress)return null;
    const ST={1:{l:"In Progress",c:s.cyan},2:{l:"Waiting",c:s.yellow},3:{l:"Paused",c:s.yellow},4:{l:"Failed",c:s.red},5:{l:"Completed",c:s.green},6:{l:"Cancelling",c:s.orange},7:{l:"Cancelled",c:s.textMute}};
    const OL={test_failover:"DR Drill",stop_test:"Stop DR Drill",live_failover:"Live Failover",commit_failover:"Commit Failover",rollback_failover:"Rollback Failover",planned_move:"Planned Move",failback:"Failback"};
    const{opType,vpgName,steps=[],state=1,progress=0,started,reason="",log=[],currentStep=0,polling}=opProgress;
    const m=ST[state]||{l:"Unknown",c:s.textMute};
    const isDone=state===5||state===4||state===7;
    const elapsed=started?Math.floor((Date.now()-new Date(started).getTime())/1000):0;
    const fmt=(x)=>x<60?x+"s":Math.floor(x/60)+"m "+x%60+"s";
    return(
      <div style={{position:"fixed",bottom:0,right:24,width:400,maxHeight:"75vh",background:s.panel,border:"1px solid "+s.borderHi,borderRadius:"12px 12px 0 0",boxShadow:"0 -4px 32px rgba(0,0,0,.5)",zIndex:500,display:"flex",flexDirection:"column",overflow:"hidden"}}>
        <div style={{padding:"10px 14px",background:s.surface,borderBottom:"1px solid "+s.border,display:"flex",alignItems:"center",justifyContent:"space-between",cursor:"pointer"}} onClick={()=>setOpProgress(p=>({...p,_min:!p._min}))}>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            {!isDone&&<div style={{width:8,height:8,borderRadius:"50%",background:m.c,animation:"zerPulse 1.2s ease-in-out infinite"}}/>}
            {isDone&&<div style={{width:8,height:8,borderRadius:"50%",background:m.c}}/>}
            <span style={{fontWeight:700,fontSize:13,color:s.text}}>{OL[opType]||opType}</span>
            <span style={{fontSize:11,color:s.textMute}}>{vpgName}</span>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:6}}>
            <span style={{fontSize:11,color:m.c,fontWeight:700}}>{progress}%</span>
            <span style={{fontSize:11,padding:"1px 6px",borderRadius:3,background:m.c+"20",color:m.c}}>{m.l}</span>
            <span style={{fontSize:11,color:s.textMute}}>{fmt(elapsed)}</span>
            {isDone&&<span onClick={(e)=>{e.stopPropagation();setOpProgress(null);stopOpPolling();}} style={{color:s.textMute,cursor:"pointer",fontSize:14,marginLeft:4}}>x</span>}
          </div>
        </div>
        <div style={{height:3,background:s.surface}}>
          <div style={{height:"100%",width:progress+"%",background:state===4?s.red:state===5?s.green:s.cyan,transition:"width .6s"}}/>
        </div>
        {!opProgress._min&&(
          <div style={{padding:"12px 14px",flex:1,overflowY:"auto"}}>
            <div style={{marginBottom:14}}>
              {steps.map((step,i)=>{
                const active=i===currentStep&&!isDone;
                const done_s=isDone&&state===5?true:i<currentStep;
                const fail_s=isDone&&state===4&&i===currentStep;
                const c=fail_s?s.red:done_s?s.green:active?s.cyan:s.textMute;
                return(
                  <div key={i} style={{display:"flex",gap:10,marginBottom:i<steps.length-1?0:4}}>
                    <div style={{display:"flex",flexDirection:"column",alignItems:"center",width:20,flexShrink:0}}>
                      <div style={{width:20,height:20,borderRadius:"50%",border:"2px solid "+c,background:c+"18",display:"flex",alignItems:"center",justifyContent:"center",fontSize:10,color:c,fontWeight:700}}>{done_s?"v":fail_s?"x":active?"O":i+1}</div>
                      {i<steps.length-1&&<div style={{width:2,flex:1,minHeight:12,background:done_s?s.green:s.border,margin:"2px 0"}}/>}
                    </div>
                    <div style={{paddingTop:2,paddingBottom:i<steps.length-1?10:0}}>
                      <div style={{fontSize:12,fontWeight:active?700:400,color:active?s.text:done_s?s.textSub:s.textMute}}>{step}</div>
                      {active&&<div style={{fontSize:11,color:s.cyan,marginTop:2,display:"flex",alignItems:"center",gap:4}}><span style={{display:"inline-block",width:7,height:7,border:"1.5px solid "+s.cyan,borderTopColor:"transparent",borderRadius:"50%",animation:"zerSpin .7s linear infinite"}}/><span>Processing...</span></div>}
                      {fail_s&&reason&&<div style={{fontSize:11,color:s.red,marginTop:2}}>{reason}</div>}
                    </div>
                  </div>
                );
              })}
            </div>
            <div>
              <div style={{fontSize:10,color:s.textMute,fontWeight:700,letterSpacing:".6px",textTransform:"uppercase",marginBottom:5}}>Activity Log</div>
              <div style={{background:s.surface,borderRadius:6,padding:"6px 8px",maxHeight:100,overflowY:"auto",display:"flex",flexDirection:"column-reverse"}}>
                {[...log].reverse().slice(0,12).map((e,i)=>(
                  <div key={i} style={{fontSize:11,color:s.textSub,padding:"1px 0",display:"flex",gap:8}}>
                    <span style={{color:s.textMute,flexShrink:0}}>{new Date(e.time).toLocaleTimeString()}</span>
                    <span>{e.msg}</span>
                  </div>
                ))}
              </div>
            </div>
            {isDone&&(
              <div style={{marginTop:10,padding:"8px 10px",borderRadius:7,background:(state===5?s.green:s.red)+"12",border:"1px solid "+(state===5?s.green:s.red)+"30"}}>
                <span style={{fontSize:12,fontWeight:700,color:state===5?s.green:s.red}}>{state===5?"Completed successfully":"Operation "+m.l.toLowerCase()}</span>
                {reason&&<div style={{fontSize:11,color:s.textSub,marginTop:3}}>{reason}</div>}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return(<div style={{padding:"0 0 20px 0"}}><style>{_ZS}</style><ConfirmModal/><AddSiteModal/><CreateVPGModal/><OperationProgressDrawer/>
    <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:18,flexWrap:"wrap",gap:10}}>
      <div>
        <div style={{fontSize:22,fontWeight:700,color:s.cyan}}>Disaster Recovery</div>
        <div style={{fontSize:12,color:s.textMute,marginTop:2}}>Zerto Virtual Replication  VPG protection, failover, DR drills</div>
      </div>
      <div style={{display:"flex",gap:8,flexWrap:"wrap",alignItems:"center"}}>
        {isAdmin&&<button onClick={()=>setAddSite(true)} style={btn(s.cyan)}>+ Add ZVM Site</button>}
        {selSite&&isAdmin&&<button onClick={()=>{setNewVPG({name:"",rpo_seconds:300,journal_hours:24,priority:"Medium",target_site_id:"",vm_ids:[]});setVpgWizStep(1);setVirtSites([]);setVirtVMs([]);setVmSearch2("");setCreateVPGModal(true);}} style={{...btn(s.green),background:s.green+"22"}}>+ Create VPG</button>}
        {selSite&&<button onClick={loadData} style={btn(s.textSub)} disabled={loading}>{loading?"Loading...":"Refresh"}</button>}
      </div>
    </div>
    {opResult&&<div style={{marginBottom:12,padding:"10px 14px",background:opResult.error?s.red+"15":s.green+"15",border:"1px solid "+(opResult.error?s.red:s.green)+"30",borderRadius:8,fontSize:12,color:opResult.error?s.red:s.green,display:"flex",justifyContent:"space-between",alignItems:"center"}}><span>{opResult.error?"Error: "+opResult.error:"Operation initiated successfully"+(opResult.task_id?" (Task: "+opResult.task_id+")":"")}</span><span onClick={()=>setOpResult(null)} style={{cursor:"pointer",color:s.textMute,fontSize:14}}>x</span></div>}
    <div style={{display:"flex",gap:8,marginBottom:16,flexWrap:"wrap",alignItems:"center"}}>
      <span style={{fontSize:11,color:s.textMute}}>ZVM Site:</span>
      {sites.map(st=>(<button key={st.id} onClick={()=>{setSelSite(st);}} style={{...btn(selSite&&selSite.id===st.id?s.cyan:s.textMute),fontWeight:selSite&&selSite.id===st.id?700:400}}>{st.name||st.host}</button>))}
      {!sites.length&&<span style={{fontSize:12,color:s.textMute}}>No ZVM sites configured</span>}
    </div>
    {selSite&&(<div>
      <div style={{display:"flex",gap:0,marginBottom:16,borderBottom:"1px solid "+s.border}}>
        {["Dashboard","VPGs","VMs","Operations","Alerts","Reports","Events","Sites","Audit"].map((tb,i)=>{
          const keys=["dash","vpgs","vms","ops","alerts","reports","events","sites","audit"];
          const k=keys[i];
          return(<button key={k} onClick={()=>setTab(k)} style={{background:"transparent",border:"none",borderBottom:"3px solid "+(tab===k?s.cyan:"transparent"),color:tab===k?s.cyan:"#e2e8f0",padding:"10px 18px",fontSize:14,fontWeight:tab===k?700:500,cursor:"pointer",transition:"color .15s,border-color .15s"}}>{tb}</button>);
        })}
      </div>
      {tab==="dash"&&<DashboardTab/>}
      {tab==="vpgs"&&<VPGsTab/>}
      {tab==="vms"&&<VMsTab/>}
      {tab==="ops"&&<OpsTab/>}
      {tab==="alerts"&&<AlertsTab/>}
      {tab==="reports"&&<ReportsTab/>}
      {tab==="events"&&<EventsTab/>}
      {tab==="sites"&&<SitesTab/>}
      {tab==="audit"&&(<div style={{overflowX:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}><thead><tr>{["Time","User","Action","Entity","Result","Details"].map(h=>(<th key={h} style={{padding:"8px 10px",borderBottom:"1px solid "+s.border,color:s.textMute,fontWeight:700,textAlign:"left",textTransform:"uppercase",fontSize:10,letterSpacing:".5px"}}>{h}</th>))}</tr></thead><tbody>{(auditLog||[]).map((a,i)=>(<tr key={i} style={{borderBottom:"1px solid "+s.border+"30"}}><td style={{padding:"7px 10px",color:s.textMute,whiteSpace:"nowrap"}}>{a.timestamp?(new Date(a.timestamp).toLocaleString()):""}</td><td style={{padding:"7px 10px",color:s.text}}>{a.user||a.initiated_by||""}</td><td style={{padding:"7px 10px",color:s.cyan,fontWeight:600}}>{a.action||""}</td><td style={{padding:"7px 10px",color:s.text}}>{a.entity||a.vpg_name||""}</td><td style={{padding:"7px 10px"}}><span style={{color:a.result==="Success"?s.green:s.red,fontWeight:600}}>{a.result||""}</span></td><td style={{padding:"7px 10px",color:s.textMute,maxWidth:200,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{a.details||""}</td></tr>))}{!auditLog?.length&&<tr><td colSpan={6} style={{padding:24,textAlign:"center",color:s.textMute}}>No audit records</td></tr>}</tbody></table></div>)}
    </div>)}
    {!loading&&!selSite&&sites.length>0&&<div style={{textAlign:"center",padding:40,color:s.textMute}}>Select a ZVM site above to view DR status</div>}
    {!loading&&!sites.length&&<div style={{textAlign:"center",padding:60}}><div style={{fontSize:48,marginBottom:12}}>DR</div><div style={{color:s.textMute,marginBottom:16}}>No Zerto ZVM sites configured yet.</div>{isAdmin&&<button onClick={()=>setAddSite(true)} style={btn(s.cyan)}>+ Add First ZVM Site</button>}</div>}
  </div>);
}