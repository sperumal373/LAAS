import sys
sys.stdout.reconfigure(encoding="utf-8")

bt = chr(96)  # backtick for template literals

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")

#  1. Add API imports 
t = t.replace(
    "import {fetchZertoTask,",
    "import {fetchZertoTask,fetchZertoVirtSites,fetchZertoVirtSiteVMs,"
)

#  2. Add state for wizard 
OLD_STATE = "  const[createVPGModal,setCreateVPGModal]=useState(false);"
NEW_STATE = (
    "  const[createVPGModal,setCreateVPGModal]=useState(false);\n"
    "  const[vpgWizStep,setVpgWizStep]=useState(1);\n"
    "  const[virtSites,setVirtSites]=useState([]);\n"
    "  const[virtVMs,setVirtVMs]=useState([]);\n"
    "  const[virtVMsLoading,setVirtVMsLoading]=useState(false);\n"
    "  const[vmSearch2,setVmSearch2]=useState('');\n"
)
t = t.replace(OLD_STATE, NEW_STATE)

#  3. Replace CreateVPGModal with wizard 
OLD_MODAL_START = "  const CreateVPGModal=()=>{"
OLD_MODAL_END = "}}}}} style={{...btn(s.cyan),background:s.cyan+\"25\",fontWeight:700,opacity:newVPG.name?1:.5}}>Create VPG</button></div></div></div>);};"
idx_start = t.find(OLD_MODAL_START)
idx_end = t.find(OLD_MODAL_END, idx_start)
if idx_start < 0 or idx_end < 0:
    print("ERROR: Could not find CreateVPGModal bounds")
    print("start:", idx_start, "end:", idx_end)
    sys.exit(1)
idx_end += len(OLD_MODAL_END)

NEW_MODAL = """  const CreateVPGModal=()=>{
    if(!createVPGModal||!isAdmin)return null;
    const prioOpts=["Low","Medium","High"];
    const step1Ok=newVPG.name&&newVPG.name.trim().length>0;
    const totalSteps=3;
    // Load virt sites when modal opens
    const loadVirtSites=async()=>{
      if(!selSite||virtSites.length)return;
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
      return (v.VmName||v.vmName||"").toLowerCase().includes(q)||(v.DatacenterName||"").toLowerCase().includes(q)||(v.HostName||"").toLowerCase().includes(q);
    });
    const selVmIds=newVPG.vm_ids||[];
    const toggleVM=(id)=>setNewVPG(n=>({...n,vm_ids:selVmIds.includes(id)?selVmIds.filter(x=>x!==id):[...selVmIds,id]}));
    const selAll=()=>setNewVPG(n=>({...n,vm_ids:filtVMs.map(v=>v.VmIdentifier||v.vmIdentifier)}));
    const clearAll=()=>setNewVPG(n=>({...n,vm_ids:[]}));
    const StepDot=({n})=>{
      const done=vpgWizStep>n; const active=vpgWizStep===n;
      return(<div style={{display:"flex",alignItems:"center",gap:4}}>
        <div style={{width:26,height:26,borderRadius:"50%",background:done?s.green:active?s.cyan:"transparent",border:"2px solid "+(done?s.green:active?s.cyan:s.textMute),display:"flex",alignItems:"center",justifyContent:"center",fontSize:11,fontWeight:700,color:done||active?s.panel:s.textMute,transition:"all .2s"}}>{done?"":n}</div>
        <span style={{fontSize:11,color:active?s.text:done?s.textSub:s.textMute,fontWeight:active?700:400}}>{n===1?"Settings":n===2?"Select VMs":"Review"}</span>
      </div>);
    };
    return(<div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.65)",backdropFilter:"blur(4px)",zIndex:400,display:"flex",alignItems:"center",justifyContent:"center"}}>
      <div style={{background:s.panel,border:"1px solid "+s.cyan+"40",borderRadius:14,padding:"0",width:620,maxWidth:"97vw",boxShadow:"0 0 40px "+s.cyan+"10",display:"flex",flexDirection:"column",maxHeight:"92vh",overflow:"hidden"}}>
        {/* Header */}
        <div style={{padding:"20px 24px 0",background:s.surface,borderBottom:"1px solid "+s.border}}>
          <div style={{fontSize:17,fontWeight:700,color:s.cyan,marginBottom:2}}>Create New VPG</div>
          <div style={{fontSize:11,color:s.textMute,marginBottom:14}}>Virtual Protection Group wizard  configure settings, select VMs, then create</div>
          <div style={{display:"flex",alignItems:"center",gap:12,paddingBottom:14}}>
            <StepDot n={1}/><div style={{flex:1,height:2,background:vpgWizStep>1?s.green:s.border,transition:"background .3s"}}/>
            <StepDot n={2}/><div style={{flex:1,height:2,background:vpgWizStep>2?s.green:s.border,transition:"background .3s"}}/>
            <StepDot n={3}/>
          </div>
        </div>
        {/* Body */}
        <div style={{padding:"20px 24px",flex:1,overflowY:"auto"}}>
          {/* STEP 1: VPG Settings */}
          {vpgWizStep===1&&(<div style={{display:"flex",flexDirection:"column",gap:14}}>
            <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>VPG Name *</label><input placeholder="e.g. WebApp_VPG" value={newVPG.name} style={inp} onChange={e=>setNewVPG(n=>({...n,name:e.target.value}))}/></div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>RPO (seconds)</label><input type="number" value={newVPG.rpo_seconds} style={inp} onChange={e=>setNewVPG(n=>({...n,rpo_seconds:+e.target.value}))}/></div>
              <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>Journal History (hours)</label><input type="number" value={newVPG.journal_hours} style={inp} onChange={e=>setNewVPG(n=>({...n,journal_hours:+e.target.value}))}/></div>
            </div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>Priority</label><select style={inp} value={newVPG.priority} onChange={e=>setNewVPG(n=>({...n,priority:e.target.value}))}>{prioOpts.map(p=>(<option key={p} value={p}>{p}</option>))}</select></div>
              <div><label style={{fontSize:11,color:s.textMute,display:"block",marginBottom:4,textTransform:"uppercase",letterSpacing:".5px"}}>Recovery Site</label><select style={inp} value={newVPG.target_site_id} onChange={e=>setNewVPG(n=>({...n,target_site_id:e.target.value}))}>{peerSites.map(ps=>(<option key={ps.SiteIdentifier} value={ps.SiteIdentifier}>{ps.PeerSiteName}</option>))}{!peerSites.length&&<option value="">No peer sites</option>}</select></div>
            </div>
          </div>)}
          {/* STEP 2: VM Selection */}
          {vpgWizStep===2&&(<div>
            <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12,flexWrap:"wrap"}}>
              <div style={{flex:1,minWidth:180}}><input placeholder="Search VMs, datacenter, host..." value={vmSearch2} style={{...inp,margin:0}} onChange={e=>setVmSearch2(e.target.value)}/></div>
              {virtSites.length>0&&(<select style={{...inp,margin:0,width:"auto"}} onChange={e=>loadVirtVMs(e.target.value)}>
                <option value="">Select vCenter site...</option>
                {virtSites.map(vs=>(<option key={vs.SiteIdentifier||vs.siteIdentifier} value={vs.SiteIdentifier||vs.siteIdentifier}>{vs.VirtualizationSiteName||vs.SiteName||vs.siteIdentifier}</option>))}
              </select>)}
              <button onClick={loadVirtSites} style={{...btn(s.cyan),padding:"6px 12px",fontSize:11}}>Load Sites</button>
              <span style={{fontSize:11,color:s.textMute}}>{selVmIds.length} selected</span>
            </div>
            {selVmIds.length>0&&(<div style={{display:"flex",flexWrap:"wrap",gap:5,marginBottom:10}}>
              {selVmIds.map(id=>{const vm=virtVMs.find(v=>(v.VmIdentifier||v.vmIdentifier)===id);return(<span key={id} style={{background:s.cyan+"20",border:"1px solid "+s.cyan+"40",borderRadius:4,padding:"2px 7px",fontSize:11,color:s.cyan,display:"flex",alignItems:"center",gap:4}}>{vm?(vm.VmName||vm.vmName||id):id}<span onClick={()=>toggleVM(id)} style={{cursor:"pointer",color:s.textMute,marginLeft:2}}></span></span>);})}
            </div>)}
            <div style={{background:s.surface,borderRadius:8,border:"1px solid "+s.border,overflow:"hidden"}}>
              <div style={{display:"grid",gridTemplateColumns:"32px 1fr 1fr 100px 80px",padding:"6px 10px",borderBottom:"1px solid "+s.border,background:s.panel}}>
                <div><input type="checkbox" onChange={e=>e.target.checked?selAll():clearAll()} checked={filtVMs.length>0&&filtVMs.every(v=>selVmIds.includes(v.VmIdentifier||v.vmIdentifier))} style={{accentColor:s.cyan}}/></div>
                {["VM Name","Datacenter / Host","Power",""].map((h,i)=>(<div key={i} style={{fontSize:10,color:s.textMute,fontWeight:700,textTransform:"uppercase",letterSpacing:".5px"}}>{h}</div>))}
              </div>
              <div style={{maxHeight:300,overflowY:"auto"}}>
                {virtVMsLoading&&<div style={{padding:24,textAlign:"center",color:s.textMute,fontSize:12}}>Loading VMs from vCenter...</div>}
                {!virtVMsLoading&&filtVMs.length===0&&<div style={{padding:24,textAlign:"center",color:s.textMute,fontSize:12}}>{virtVMs.length===0?"Select a vCenter site above to load VMs":"No VMs match your search"}</div>}
                {!virtVMsLoading&&filtVMs.map((vm,i)=>{
                  const id=vm.VmIdentifier||vm.vmIdentifier;
                  const sel=selVmIds.includes(id);
                  const power=vm.PowerStatus||vm.powerStatus||vm.Status||"";
                  const dc=vm.DatacenterName||vm.datacenterName||"";
                  const host=vm.HostName||vm.hostName||"";
                  const pColor=power.toLowerCase()==="on"||power==="1"?s.green:power.toLowerCase()==="off"||power==="0"?s.textMute:s.yellow;
                  return(<div key={id||i} onClick={()=>toggleVM(id)} style={{display:"grid",gridTemplateColumns:"32px 1fr 1fr 100px 80px",padding:"8px 10px",borderBottom:"1px solid "+s.border+"50",cursor:"pointer",background:sel?s.cyan+"08":"transparent",transition:"background .1s"}}>
                    <div><input type="checkbox" checked={sel} readOnly style={{accentColor:s.cyan}}/></div>
                    <div style={{fontSize:12,color:s.text,fontWeight:sel?600:400}}>{vm.VmName||vm.vmName||id}</div>
                    <div style={{fontSize:11,color:s.textMute}}>{dc}{dc&&host?" / ":""}{host}</div>
                    <div style={{fontSize:11,color:pColor,fontWeight:600}}>{power||""}</div>
                    <div/>
                  </div>);
                })}
              </div>
            </div>
          </div>)}
          {/* STEP 3: Review */}
          {vpgWizStep===3&&(<div style={{display:"flex",flexDirection:"column",gap:14}}>
            <div style={{background:s.surface,borderRadius:8,padding:"14px 16px",border:"1px solid "+s.border}}>
              <div style={{fontSize:12,color:s.textMute,fontWeight:700,textTransform:"uppercase",letterSpacing:".5px",marginBottom:10}}>VPG Configuration</div>
              {[["Name",newVPG.name],["RPO",newVPG.rpo_seconds+" seconds"],["Journal",newVPG.journal_hours+" hours"],["Priority",newVPG.priority],["Recovery Site",(peerSites.find(p=>p.SiteIdentifier===newVPG.target_site_id)||{}).PeerSiteName||newVPG.target_site_id||""]].map(([k,v])=>(<div key={k} style={{display:"flex",justifyContent:"space-between",marginBottom:6,fontSize:13}}><span style={{color:s.textMute}}>{k}</span><span style={{color:s.text,fontWeight:600}}>{v}</span></div>))}
            </div>
            <div style={{background:s.surface,borderRadius:8,padding:"14px 16px",border:"1px solid "+s.border}}>
              <div style={{fontSize:12,color:s.textMute,fontWeight:700,textTransform:"uppercase",letterSpacing:".5px",marginBottom:10}}>VMs to Protect <span style={{color:s.cyan,fontWeight:700}}>({selVmIds.length})</span></div>
              {selVmIds.length===0?(<div style={{fontSize:12,color:s.yellow,padding:"6px 0"}}> No VMs selected  VPG will be created empty. You can add VMs later via Zerto console.</div>):(
                <div style={{display:"flex",flexWrap:"wrap",gap:5}}>
                  {selVmIds.map(id=>{const vm=virtVMs.find(v=>(v.VmIdentifier||v.vmIdentifier)===id);return(<span key={id} style={{background:s.green+"15",border:"1px solid "+s.green+"30",borderRadius:4,padding:"2px 8px",fontSize:11,color:s.green}}>{vm?(vm.VmName||vm.vmName||id):id}</span>);})}
                </div>
              )}
            </div>
          </div>)}
        </div>
        {/* Footer */}
        <div style={{padding:"14px 24px",borderTop:"1px solid "+s.border,background:s.surface,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <button onClick={()=>{if(vpgWizStep===1){setCreateVPGModal(false);setVpgWizStep(1);setVirtSites([]);setVirtVMs([]);setVmSearch2('');}else{setVpgWizStep(s=>s-1);}}} style={btn(s.textSub)}>{vpgWizStep===1?"Cancel":" Back"}</button>
          <div style={{fontSize:11,color:s.textMute}}>Step {vpgWizStep} of {totalSteps}</div>
          {vpgWizStep<3&&(<button disabled={vpgWizStep===1&&!step1Ok} onClick={()=>{if(vpgWizStep===1)loadVirtSites();setVpgWizStep(s=>s+1);}} style={{...btn(s.cyan),background:s.cyan+"25",fontWeight:700,opacity:vpgWizStep===1&&!step1Ok?.4:1}}>Next </button>)}
          {vpgWizStep===3&&(<button onClick={async()=>{const r=await createZertoVPG(selSite.id,newVPG).catch(e=>({error:e.message}));if(r.ok||r.result){setCreateVPGModal(false);setVpgWizStep(1);setVirtSites([]);setVirtVMs([]);setVmSearch2('');alert("VPG "+newVPG.name+" created with "+selVmIds.length+" VMs!");}else{alert("Error: "+(r.error||"Creation failed"));}}} style={{...btn(s.cyan),background:s.cyan+"25",fontWeight:700}}> Create VPG</button>)}
        </div>
      </div>
    </div>);
  };
"""

idx_start = t.find("  const CreateVPGModal=()=>{")
idx_end_str = "}}}}} style={{...btn(s.cyan),background:s.cyan+\"25\",fontWeight:700,opacity:newVPG.name?1:.5}}>Create VPG</button></div></div></div>);};"
idx_end = t.find(idx_end_str, idx_start)
if idx_end < 0:
    print("ERROR: could not find end of CreateVPGModal")
    # Try a different anchor
    idx_end_str2 = "Create VPG</button></div></div></div>);};"
    idx_end = t.find(idx_end_str2, idx_start)
    if idx_end < 0:
        print("Still not found, searching...")
        print(repr(t[idx_start+3800:idx_start+4100]))
        sys.exit(1)
    idx_end += len(idx_end_str2)
else:
    idx_end += len(idx_end_str)

t = t[:idx_start] + NEW_MODAL + t[idx_end:]
print("CreateVPGModal replaced:", "vpgWizStep" in t)

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(t.encode("utf-8-sig"))
print("Done. Size:", len(t))