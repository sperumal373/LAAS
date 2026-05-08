import sys
sys.stdout.reconfigure(encoding="utf-8")

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")

# Fix imports - add new API functions
if "fetchZertoVirtSites" not in t:
    t = t.replace(
        "import {fetchZertoTask,",
        "import {fetchZertoTask,fetchZertoVirtSites,fetchZertoVirtSiteVMs,"
    )

# Add wizard state vars after createVPGModal state
if "vpgWizStep" not in t:
    t = t.replace(
        "  const[createVPGModal,setCreateVPGModal]=useState(false);",
        "  const[createVPGModal,setCreateVPGModal]=useState(false);\n  const[vpgWizStep,setVpgWizStep]=useState(1);\n  const[virtSites,setVirtSites]=useState([]);\n  const[virtVMs,setVirtVMs]=useState([]);\n  const[virtVMsLoading,setVirtVMsLoading]=useState(false);\n  const[vmSearch2,setVmSearch2]=useState('');"
    )

# Replace CreateVPGModal with wizard (using exact anchors)
START = "  const CreateVPGModal=()=>{"
END_ANCHOR = "Create VPG</button></div></div></div>);};"
idx_s = t.find(START)
idx_e = t.find(END_ANCHOR, idx_s) + len(END_ANCHOR)

NEW_MODAL = r"""  const CreateVPGModal=()=>{
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
          <button onClick={()=>vpgWizStep===1?closeWiz():setVpgWizStep(n=>n-1)} style={btn(s.textSub)}>{vpgWizStep===1?"Cancel":"\u2190 Back"}</button>
          <span style={{fontSize:11,color:s.textMute}}>Step {vpgWizStep} of {totalSteps}</span>
          {vpgWizStep<3&&(<button disabled={vpgWizStep===1&&!step1Ok} onClick={()=>{if(vpgWizStep===1)loadVirtSites();setVpgWizStep(n=>n+1);}} style={{...btn(s.cyan),background:s.cyan+"22",fontWeight:700,opacity:vpgWizStep===1&&!step1Ok?.4:1}}>Next \u2192</button>)}
          {vpgWizStep===3&&(<button onClick={async()=>{const r=await createZertoVPG(selSite.id,newVPG).catch(e=>({error:e.message}));if(r&&(r.ok||r.result)){closeWiz();alert("VPG \""+newVPG.name+"\" created with "+selVmIds.length+" VM(s) protected!");}else{alert("Error: "+(r&&r.error?""+r.error:"Creation failed"));}}} style={{...btn(s.cyan),background:s.cyan+"22",fontWeight:700}}>\u{1F680} Create VPG</button>)}
        </div>
      </div>
    </div>);
  };"""

t = t[:idx_s] + NEW_MODAL + "\n\n" + t[idx_e:]
print("Wizard injected:", "vpgWizStep" in t)
print("VM selection:", "filtVMs" in t)

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(t.encode("utf-8-sig"))
print("Done. Size:", len(t))