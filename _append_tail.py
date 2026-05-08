import sys
sys.stdout.reconfigure(encoding="utf-8")

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")

# The file currently ends with the wizard };
# We need to append: OperationProgressDrawer + main return + closing }

TAIL = r"""

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

"""

# Main return - render all tabs
MAIN_RETURN = r"""
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
    {loading&&<div style={{textAlign:"center",padding:32,color:s.textMute,fontSize:13}}>{loadMsg||"Loading..."}</div>}
    {!loading&&selSite&&(<div>
      <div style={{display:"flex",gap:0,marginBottom:16,borderBottom:"1px solid "+s.border}}>
        {["Dashboard","VPGs","VMs","Operations","Alerts","Reports","Events","Sites","Audit"].map((tb,i)=>{
          const keys=["dash","vpgs","vms","ops","alerts","reports","events","sites","audit"];
          const k=keys[i];
          return(<button key={k} onClick={()=>setTab(k)} style={{background:"transparent",border:"none",borderBottom:"2px solid "+(tab===k?s.cyan:"transparent"),color:tab===k?s.cyan:s.textMute,padding:"8px 14px",fontSize:12,fontWeight:tab===k?700:400,cursor:"pointer",transition:"all .15s"}}>{tb}</button>);
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
      {tab==="audit"&&<AuditTab/>}
    </div>)}
    {!loading&&!selSite&&sites.length>0&&<div style={{textAlign:"center",padding:40,color:s.textMute}}>Select a ZVM site above to view DR status</div>}
    {!loading&&!sites.length&&<div style={{textAlign:"center",padding:60}}><div style={{fontSize:48,marginBottom:12}}>DR</div><div style={{color:s.textMute,marginBottom:16}}>No Zerto ZVM sites configured yet.</div>{isAdmin&&<button onClick={()=>setAddSite(true)} style={btn(s.cyan)}>+ Add First ZVM Site</button>}</div>}
  </div>);
}
"""

t = t.rstrip() + TAIL + MAIN_RETURN

print("Has Drawer:", "OperationProgressDrawer" in t)
print("Has return:", "return(<div style={{padding" in t)
print("Has export:", "export default function" in t)
print("Lines:", t.count("\n"))

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(t.encode("utf-8-sig"))
print("Done. Size:", len(t))