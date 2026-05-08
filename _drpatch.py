import sys
sys.stdout.reconfigure(encoding="utf-8")

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    text = f.read().decode("utf-8-sig")

# 3. Inject startOperationTracking + stopOpPolling before loadData
TRACKER = (
    "  const stopOpPolling=()=>{if(opPollRef.current){clearInterval(opPollRef.current);opPollRef.current=null;}};\n"
    "  const OP_STEPS={\n"
    "    test_failover:['Initiating DR Drill','Suspending replication','Booting VMs at recovery site','Running verification','DR Drill active'],\n"
    "    stop_test:['Stopping DR Drill','Shutting down test VMs','Restoring replication','Cleanup complete'],\n"
    "    live_failover:['Initiating Failover','Suspending source replication','Failing over VMs','Updating network routes','Failover complete'],\n"
    "    commit_failover:['Committing Failover','Finalising VM state','Removing journals','Setting up reverse protection','Committed'],\n"
    "    rollback_failover:['Rolling back','Restoring protected site','Resuming replication','Cleanup','Rollback complete'],\n"
    "    planned_move:['Planned Move initiated','Quiescing VMs','Final sync','Starting at recovery site','Move complete'],\n"
    "    failback:['Initiating Failback','Replicating to DC','Syncing data','Booting at protected site','Failback complete'],\n"
    "  };\n"
    "  const startOperationTracking=(taskId,siteId,opType,vpgName)=>{\n"
    "    const steps=OP_STEPS[opType]||['Initiating','Processing','Executing','Finalising','Complete'];\n"
    "    const entry=(msg)=>({time:new Date().toISOString(),msg});\n"
    "    setOpProgress({taskId,siteId,opType,vpgName,steps,state:1,progress:0,currentStep:0,\n"
    "      started:new Date().toISOString(),reason:'',polling:true,\n"
    "      log:[entry('Started: '+opType+' on '+vpgName)]});\n"
    "    stopOpPolling();\n"
    "    opPollRef.current=setInterval(async()=>{\n"
    "      try{\n"
    "        const t=await fetchZertoTask(siteId,taskId);\n"
    "        if(t&&!t.error){\n"
    "          const done=t.state===5||t.state===4||t.state===7;\n"
    "          const si=Math.min(Math.floor((t.progress/100)*(steps.length-1)),steps.length-1);\n"
    "          setOpProgress(prev=>{if(!prev)return prev;\n"
    "            const last=prev.log[prev.log.length-1];\n"
    "            const msg=steps[si]+(t.progress>0?' ('+t.progress+'%)':'');\n"
    "            const newLog=last&&last.msg===msg?prev.log:[...prev.log,{time:new Date().toISOString(),msg}].slice(-20);\n"
    "            return{...prev,state:t.state,progress:t.progress,currentStep:si,reason:t.complete_reason||'',polling:!done,log:newLog};\n"
    "          });\n"
    "          if(done){stopOpPolling();setTimeout(()=>{},2000);}\n"
    "        }\n"
    "      }catch(e){console.warn('poll err',e);}\n"
    "    },2500);\n"
    "  };\n\n"
)

text = text.replace(
    "  const loadData=useCallback(async()=>{",
    TRACKER + "  const loadData=useCallback(async()=>{"
)

# 4. Wire startOperationTracking into execute
old_exec = "setOpResult(r);setModal(null);setTimeout(loadData,2000);};"
new_exec = (
    "setOpResult(r);setModal(null);"
    "const tid=r&&(r.task_id||r.taskId||r.TaskIdentifier);"
    "if(tid&&selSite){startOperationTracking(tid,selSite.id,modal.type,vpg?.name||modal.vpg_id||'VPG');}"
    "else{setTimeout(loadData,2000);}}"
    ";"
)
text = text.replace(old_exec, new_exec)

print("Tracker injected:", "startOperationTracking" in text)
print("Exec wired:", "startOperationTracking(tid" in text)

# 5. Add OperationProgressDrawer component and inject into JSX
DRAWER = '''
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
            {isDone&&<span onClick={(e)=>{e.stopPropagation();setOpProgress(null);stopOpPolling();}} style={{color:s.textMute,cursor:"pointer",fontSize:14,marginLeft:4}}></span>}
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
                      <div style={{width:20,height:20,borderRadius:"50%",border:"2px solid "+c,background:c+"18",display:"flex",alignItems:"center",justifyContent:"center",fontSize:10,color:c,fontWeight:700}}>{done_s?"":fail_s?"":active?"":i+1}</div>
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
                    <span style={{color:s.textMute,flexShrink:0,fontVariantNumeric:"tabular-nums"}}>{new Date(e.time).toLocaleTimeString()}</span>
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

'''

# Inject keyframe styles at start of component
old_comp_start = "export default function ZertoPage({p, currentUser}){"
new_comp_start = (
    'const _ZS=`@keyframes zerPulse{0%,100%{opacity:1}50%{opacity:.3}}'
    '@keyframes zerSpin{to{transform:rotate(360deg)}}`;\n'
    "export default function ZertoPage({p, currentUser}){"
)
text = text.replace(old_comp_start, new_comp_start)

# Insert Drawer before return
old_ret = '\n  return(<div style={{padding:"0 0 20px 0"}}><ConfirmModal/><AddSiteModal/><CreateVPGModal/>'
new_ret = DRAWER + '\n  return(<div style={{padding:"0 0 20px 0"}}><style>{_ZS}</style><ConfirmModal/><AddSiteModal/><CreateVPGModal/><OperationProgressDrawer/>'
text = text.replace(old_ret, new_ret)

print("Drawer injected:", "OperationProgressDrawer" in text)
print("Styles injected:", "_ZS" in text)

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(text.encode("utf-8-sig"))
print("Done. Size:", len(text))