"""
Inject CMDBPage component into App.jsx just before the App() function,
add it to the nav, and add page routing.
"""

with open(r'c:\caas-dashboard\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# ──────────────────────────────────────────────────────────────────────────────
# 1. Add CMDB imports to api import block
# ──────────────────────────────────────────────────────────────────────────────
OLD_IMPORT = '  fetchIPAM2Summary, collectIPAMSnapshot,\n} from "./api";'
NEW_IMPORT = '''  fetchIPAM2Summary, collectIPAMSnapshot,
  fetchCMDBSummary, fetchCMDBCIs, collectCMDBNow,
  updateCMDBCI, fetchCMDBSNConfig, saveCMDBSNConfig, pushCMDBToSN,
} from "./api";'''

if OLD_IMPORT not in content:
    print("ERROR: import block not found")
else:
    content = content.replace(OLD_IMPORT, NEW_IMPORT, 1)
    print("OK: imports updated")

# ──────────────────────────────────────────────────────────────────────────────
# 2. Add CMDB nav item (VMware overview tile nav - first occurrence)
# ──────────────────────────────────────────────────────────────────────────────
OLD_IPAM_NAV1 = '    {id:"ipam",     label:"IPAM",       icon:"📡",  color:"#06b6d4",  badge:ipamData?`${ipamData.summary?.total_subnets||0} Subnets`:"—"},\n  ];'
NEW_IPAM_NAV1 = '    {id:"ipam",     label:"IPAM",       icon:"📡",  color:"#06b6d4",  badge:ipamData?`${ipamData.summary?.total_subnets||0} Subnets`:"—"},\n    {id:"cmdb",     label:"CMDB",       icon:"🗄️", color:"#8b5cf6",  badge:"CI Registry"},\n  ];'

if OLD_IPAM_NAV1 not in content:
    print("WARNING: first IPAM nav not found")
else:
    content = content.replace(OLD_IPAM_NAV1, NEW_IPAM_NAV1, 1)
    print("OK: VMware overview nav updated")

# ──────────────────────────────────────────────────────────────────────────────
# 3. Add CMDB to sidebar nav (second occurrence with roles)
# ──────────────────────────────────────────────────────────────────────────────
OLD_IPAM_NAV2 = '    {id:"ipam",      label:"IPAM",        icon:"📡", roles:["admin","operator","viewer"]},\n    {id:"assets",    label:"Asset Mgmt", icon:"🗃️", roles:["admin","operator","viewer"]},'
NEW_IPAM_NAV2 = '    {id:"ipam",      label:"IPAM",        icon:"📡", roles:["admin","operator","viewer"]},\n    {id:"cmdb",      label:"CMDB",        icon:"🗄️", roles:["admin","operator","viewer"]},\n    {id:"assets",    label:"Asset Mgmt", icon:"🗃️", roles:["admin","operator","viewer"]},'

if OLD_IPAM_NAV2 not in content:
    print("WARNING: sidebar nav IPAM not found (trying alternate)")
    # Try without trailing comma variations
    import re
    m = re.search(r'\{id:"ipam",\s+label:"IPAM"[^}]+\},\s*\n\s*\{id:"assets"', content)
    if m:
        print(f"Found at {m.start()}: {repr(content[m.start():m.start()+200])}")
    else:
        print("Not found at all")
else:
    content = content.replace(OLD_IPAM_NAV2, NEW_IPAM_NAV2, 1)
    print("OK: sidebar nav updated")

# ──────────────────────────────────────────────────────────────────────────────
# 4. Add page routing for cmdb
# ──────────────────────────────────────────────────────────────────────────────
OLD_ROUTING = '            {page==="assets"    &&<AssetManagementPage currentUser={currentUser} p={p}/>}'
NEW_ROUTING = '            {page==="cmdb"      &&<CMDBPage currentUser={currentUser} p={p}/>}\n            {page==="assets"    &&<AssetManagementPage currentUser={currentUser} p={p}/>}'

if OLD_ROUTING not in content:
    print("WARNING: assets routing not found")
else:
    content = content.replace(OLD_ROUTING, NEW_ROUTING, 1)
    print("OK: page routing updated")

# ──────────────────────────────────────────────────────────────────────────────
# 5. Insert CMDBPage component before App()
# ──────────────────────────────────────────────────────────────────────────────
CMDB_PAGE = r'''
// ─── CMDB PAGE ───────────────────────────────────────────────────────────────
function CMDBPage({ currentUser, p }) {
  const role = currentUser?.role || "viewer";
  const isAdmin = role === "admin";
  const isOp    = isAdmin || role === "operator";

  const [summary, setSummary]   = useState(null);
  const [cis,     setCIs]       = useState([]);
  const [loading, setLoading]   = useState(true);
  const [collecting, setCollecting] = useState(false);
  const [tab,     setTab]       = useState("all");
  const [search,  setSearch]    = useState("");
  const [msg,     setMsg]       = useState(null);

  // SN config modal
  const [showSN,  setShowSN]    = useState(false);
  const [snCfg,   setSnCfg]     = useState({instance_url:"",username:"",password:"",default_company:"SDx-COE",default_bu:"SDx-COE",push_vm:true,push_host:true,push_storage:true,push_network:true,push_physical:true});
  const [snSaving, setSnSaving] = useState(false);
  const [pushing,  setPushing]  = useState(false);
  const [pushResult, setPushResult] = useState(null);

  // Edit modal
  const [editCI, setEditCI]     = useState(null);
  const [editBusy, setEditBusy] = useState(false);

  const TAB_CLASSES = {
    all:      null,
    vms:      "cmdb_ci_vm_instance",
    esxi:     "cmdb_ci_esx_server",
    hv:       "cmdb_ci_win_server",
    nutanix:  "cmdb_ci_nutanix_node",
    aws:      "cmdb_ci_ec2_instance",
    storage:  "cmdb_ci_storage_device",
    ocp:      ["cmdb_ci_ocp_cluster","cmdb_ci_ocp_node"],
    physical: "cmdb_ci_server",
    network:  "cmdb_ci_ip_network",
  };

  const TAB_LABELS = [
    {id:"all",     icon:"🗄️", label:"All CIs"},
    {id:"vms",     icon:"💻", label:"Virtual Machines"},
    {id:"esxi",    icon:"🖥️", label:"ESXi Hosts"},
    {id:"hv",      icon:"🪟", label:"Hyper-V Hosts"},
    {id:"nutanix", icon:"⚡", label:"Nutanix Nodes"},
    {id:"aws",     icon:"☁️", label:"AWS EC2"},
    {id:"storage", icon:"💾", label:"Storage"},
    {id:"ocp",     icon:"🔴", label:"OpenShift"},
    {id:"physical",icon:"🖧",  label:"Physical Servers"},
    {id:"network", icon:"🌐", label:"Networks"},
  ];

  function load() {
    setLoading(true);
    Promise.all([
      fetchCMDBSummary(),
      fetchCMDBCIs(null, null, null, 2000, 0),
    ]).then(([s, c]) => {
      setSummary(s);
      setCIs(c.items || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  function doCollect() {
    setCollecting(true); setMsg(null);
    collectCMDBNow()
      .then(() => {
        setMsg({ok:true, text:"Collection started in background. Refresh in ~30s."});
        setTimeout(() => { load(); setCollecting(false); }, 30000);
      })
      .catch(e => { setMsg({ok:false, text:e.message}); setCollecting(false); });
  }

  // SN config
  function openSNModal() {
    fetchCMDBSNConfig().then(cfg => {
      if (cfg && cfg.instance_url) setSnCfg({...snCfg, ...cfg, password:""});
    }).catch(() => {});
    setPushResult(null);
    setShowSN(true);
  }

  function saveSNConfig() {
    setSnSaving(true);
    saveCMDBSNConfig(snCfg)
      .then(() => { setMsg({ok:true, text:"ServiceNow config saved."}); setShowSN(false); })
      .catch(e => setMsg({ok:false, text:e.message}))
      .finally(() => setSnSaving(false));
  }

  function doPush(dry) {
    setPushing(true); setPushResult(null);
    pushCMDBToSN(dry)
      .then(r => setPushResult(r))
      .catch(e => setPushResult({error: e.message}))
      .finally(() => setPushing(false));
  }

  function saveEditCI() {
    if (!editCI) return;
    setEditBusy(true);
    const {id, ...fields} = editCI;
    updateCMDBCI(id, fields)
      .then(() => { setMsg({ok:true, text:"CI updated."}); setEditCI(null); load(); })
      .catch(e => setMsg({ok:false, text:e.message}))
      .finally(() => setEditBusy(false));
  }

  // Filter CIs for current tab
  const clsFilter = TAB_CLASSES[tab];
  let filtered = cis.filter(c => {
    if (clsFilter) {
      if (Array.isArray(clsFilter)) { if (!clsFilter.includes(c.sys_class_name)) return false; }
      else { if (c.sys_class_name !== clsFilter) return false; }
    }
    if (search) {
      const q = search.toLowerCase();
      return (c.name||"").toLowerCase().includes(q)
          || (c.ip_address||"").includes(q)
          || (c.os||"").toLowerCase().includes(q)
          || (c.department||"").toLowerCase().includes(q)
          || (c.location||"").toLowerCase().includes(q)
          || (c.serial_number||"").toLowerCase().includes(q);
    }
    return true;
  });

  // Tab counts
  const tabCount = (tid) => {
    const cls = TAB_CLASSES[tid];
    if (!cls) return cis.length;
    if (Array.isArray(cls)) return cis.filter(c => cls.includes(c.sys_class_name)).length;
    return cis.filter(c => c.sys_class_name === cls).length;
  };

  const CLASS_ICON = {
    cmdb_ci_vm_instance:   "💻",
    cmdb_ci_esx_server:    "🖥️",
    cmdb_ci_win_server:    "🪟",
    cmdb_ci_nutanix_node:  "⚡",
    cmdb_ci_ec2_instance:  "☁️",
    cmdb_ci_storage_device:"💾",
    cmdb_ci_ocp_cluster:   "🔴",
    cmdb_ci_ocp_node:      "🔴",
    cmdb_ci_server:        "🖧",
    cmdb_ci_ip_network:    "🌐",
  };

  const SN_STATUS_COLOR = { ok:"#10b981", error:"#ef4444", pending:"#f59e0b", never:"#64748b" };

  const KPI = ({icon,label,value,color,sub}) => (
    <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,padding:"14px 18px",minWidth:130}}>
      <div style={{fontSize:22}}>{icon}</div>
      <div style={{fontSize:24,fontWeight:800,color:color||p.text,marginTop:4}}>{value}</div>
      <div style={{fontSize:12,color:p.textMute,marginTop:2,fontWeight:600}}>{label}</div>
      {sub&&<div style={{fontSize:11,color:p.textSub,marginTop:1}}>{sub}</div>}
    </div>
  );

  if (loading) return <div style={{padding:48,textAlign:"center",color:p.textMute,fontSize:16}}>Loading CMDB…</div>;

  return (
    <div style={{padding:"0 0 40px 0"}}>
      {/* ── Header ── */}
      <div style={{background:`linear-gradient(135deg,${p.panel},${p.panelAlt})`,border:`1px solid ${p.border}`,borderRadius:16,padding:"20px 28px",marginBottom:20,display:"flex",alignItems:"center",gap:16}}>
        <div style={{fontSize:36}}>🗄️</div>
        <div style={{flex:1}}>
          <div style={{fontWeight:900,fontSize:22,letterSpacing:"1.5px",textTransform:"uppercase",color:"#8b5cf6"}}>CMDB</div>
          <div style={{fontSize:13,color:p.textMute,marginTop:2}}>Configuration Management Database · ServiceNow-aligned · Auto-collected at 11 PM</div>
        </div>
        <div style={{display:"flex",gap:8,flexWrap:"wrap",justifyContent:"flex-end"}}>
          {isOp&&(
            <button onClick={doCollect} disabled={collecting} style={{padding:"8px 18px",borderRadius:8,border:"1.5px solid #8b5cf6",background:collecting?"#8b5cf630":"#8b5cf6",color:"#fff",fontWeight:700,fontSize:14,cursor:collecting?"wait":"pointer"}}>
              {collecting?"⟳ Collecting…":"⟳ Collect Now"}
            </button>
          )}
          {isAdmin&&(
            <button onClick={openSNModal} style={{padding:"8px 18px",borderRadius:8,border:"1.5px solid #06b6d4",background:"none",color:"#06b6d4",fontWeight:700,fontSize:14,cursor:"pointer"}}>
              🔗 ServiceNow
            </button>
          )}
        </div>
      </div>

      {/* ── Message bar ── */}
      {msg&&(
        <div style={{marginBottom:14,padding:"10px 18px",borderRadius:8,background:msg.ok?"#0f291a":"#2d1515",border:`1px solid ${msg.ok?"#10b981":"#ef4444"}`,color:msg.ok?"#10b981":"#ef4444",fontSize:14,display:"flex",justifyContent:"space-between",alignItems:"center"}}>
          <span>{msg.ok?"✅":"❌"} {msg.text}</span>
          <button onClick={()=>setMsg(null)} style={{background:"none",border:"none",color:"inherit",cursor:"pointer",fontSize:16}}>✕</button>
        </div>
      )}

      {/* ── KPI Summary ── */}
      {summary&&(
        <div style={{display:"flex",gap:12,flexWrap:"wrap",marginBottom:20}}>
          <KPI icon="🗄️" label="Total CIs"         value={(summary.total||0).toLocaleString()}          color="#8b5cf6"/>
          <KPI icon="✅" label="Operational"        value={(summary.operational||0).toLocaleString()}    color="#10b981"/>
          <KPI icon="💻" label="VMs"                value={(summary.vms||0).toLocaleString()}             color="#3b82f6"/>
          <KPI icon="🖥️" label="ESXi Hosts"        value={(summary.esxi_hosts||0).toLocaleString()}     color="#f59e0b"/>
          <KPI icon="⚡" label="Nutanix"            value={(summary.nutanix_nodes||0).toLocaleString()}  color="#facc15"/>
          <KPI icon="☁️" label="AWS EC2"            value={(summary.aws_ec2||0).toLocaleString()}        color="#38bdf8"/>
          <KPI icon="💾" label="Storage"            value={(summary.storage_devices||0).toLocaleString()} color="#a855f7"/>
          <KPI icon="🔴" label="OCP Nodes"          value={(summary.ocp_nodes||0).toLocaleString()}      color="#ef4444"/>
          <KPI icon="🖧"  label="Physical"          value={(summary.physical_servers||0).toLocaleString()} color="#84cc16"/>
          <KPI icon="🌐" label="Networks"           value={(summary.networks||0).toLocaleString()}       color="#06b6d4"/>
          <KPI icon="🔗" label="Pushed to SN"       value={(summary.pushed_to_sn||0).toLocaleString()}  color="#10b981"
               sub={summary.last_collected?`Last: ${summary.last_collected.slice(0,10)}`:null}/>
        </div>
      )}

      {/* ── Tab bar ── */}
      <div style={{display:"flex",gap:4,flexWrap:"wrap",marginBottom:14}}>
        {TAB_LABELS.map(t=>(
          <button key={t.id} onClick={()=>setTab(t.id)} style={{
            padding:"6px 14px",borderRadius:20,border:`1.5px solid ${tab===t.id?"#8b5cf6":p.border}`,
            background:tab===t.id?"#8b5cf620":"none",
            color:tab===t.id?"#8b5cf6":p.textMute,
            fontWeight:tab===t.id?700:400,fontSize:13,cursor:"pointer",
          }}>
            {t.icon} {t.label} <span style={{fontSize:11,opacity:.7}}>({tabCount(t.id)})</span>
          </button>
        ))}
      </div>

      {/* ── Search bar ── */}
      <div style={{marginBottom:12}}>
        <input
          value={search} onChange={e=>setSearch(e.target.value)}
          placeholder="Search by name, IP, OS, department, serial, location…"
          style={{width:"100%",padding:"8px 14px",borderRadius:8,border:`1px solid ${p.border}`,background:p.panelAlt,color:p.text,fontSize:14,boxSizing:"border-box"}}
        />
      </div>

      {/* ── CI Table ── */}
      <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,overflow:"hidden"}}>
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
            <thead>
              <tr style={{background:p.panelAlt}}>
                {["","CI Name","Class","IP Address","OS","Department","Environment","Location","CPU","RAM","Serial","SN Status",""].map((h,i)=>(
                  <th key={i} style={{padding:"10px 12px",textAlign:"left",color:p.textMute,fontWeight:700,fontSize:12,letterSpacing:"0.5px",whiteSpace:"nowrap",borderBottom:`1px solid ${p.border}`}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length===0&&(
                <tr><td colSpan={13} style={{padding:"30px",textAlign:"center",color:p.textMute}}>
                  {cis.length===0?"No CIs collected yet. Click \"Collect Now\" to populate.":"No CIs match the filter."}
                </td></tr>
              )}
              {filtered.slice(0,500).map((ci,i)=>{
                const snColor = SN_STATUS_COLOR[ci.sn_push_status||"pending"] || "#64748b";
                return(
                  <tr key={ci.id||i} style={{borderBottom:`1px solid ${p.border}20`,background:i%2===0?"transparent":`${p.panelAlt}40`}}>
                    <td style={{padding:"8px 12px",fontSize:18}}>{CLASS_ICON[ci.sys_class_name]||"📦"}</td>
                    <td style={{padding:"8px 12px",fontWeight:600,color:p.text,maxWidth:200}}>
                      <div style={{overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{ci.name||"—"}</div>
                      {ci.hypervisor_host&&<div style={{fontSize:11,color:p.textSub}}>on {ci.hypervisor_host}</div>}
                    </td>
                    <td style={{padding:"8px 12px",color:p.textMute,fontSize:11,whiteSpace:"nowrap"}}>{(ci.sys_class_name||"").replace("cmdb_ci_","")}</td>
                    <td style={{padding:"8px 12px",fontFamily:"monospace",fontSize:12,color:"#06b6d4"}}>{ci.ip_address||"—"}</td>
                    <td style={{padding:"8px 12px",color:p.textSub,maxWidth:150,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{ci.os||"—"}</td>
                    <td style={{padding:"8px 12px",color:p.textMute,fontSize:12}}>{ci.department||"—"}</td>
                    <td style={{padding:"8px 12px"}}>
                      {ci.environment?(
                        <span style={{padding:"2px 8px",borderRadius:10,fontSize:11,fontWeight:600,
                          background:ci.environment==="Production"?"#10b98120":ci.environment==="DR"?"#f59e0b20":"#3b82f620",
                          color:ci.environment==="Production"?"#10b981":ci.environment==="DR"?"#f59e0b":"#60a5fa"}}>
                          {ci.environment}
                        </span>
                      ):"—"}
                    </td>
                    <td style={{padding:"8px 12px",color:p.textSub,fontSize:12}}>{ci.location||"—"}</td>
                    <td style={{padding:"8px 12px",color:p.textMute,fontSize:12,textAlign:"right"}}>{ci.cpu_count||"—"}</td>
                    <td style={{padding:"8px 12px",color:p.textMute,fontSize:12,textAlign:"right"}}>{ci.ram_mb>0?`${Math.round(ci.ram_mb/1024)}GB`:"—"}</td>
                    <td style={{padding:"8px 12px",color:p.textSub,fontSize:11,fontFamily:"monospace"}}>{ci.serial_number||"—"}</td>
                    <td style={{padding:"8px 12px"}}>
                      <span style={{color:snColor,fontSize:11,fontWeight:700}}>{ci.sn_push_status||"pending"}</span>
                      {ci.sys_id&&<div style={{fontSize:10,color:p.textSub,fontFamily:"monospace"}}>{ci.sys_id.slice(0,8)}…</div>}
                    </td>
                    <td style={{padding:"8px 12px"}}>
                      {isAdmin&&(
                        <button onClick={()=>setEditCI({...ci})} title="Edit CI"
                          style={{padding:"3px 8px",borderRadius:6,border:`1px solid ${p.border}`,background:"none",color:"#8b5cf6",fontSize:12,cursor:"pointer"}}>
                          ✏️
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {filtered.length>500&&(
          <div style={{padding:"10px 16px",color:p.textMute,fontSize:13,textAlign:"center",borderTop:`1px solid ${p.border}`}}>
            Showing 500 of {filtered.length} CIs. Use search to narrow results.
          </div>
        )}
      </div>

      {/* ══ ServiceNow Config Modal ══ */}
      {showSN&&(
        <div style={{position:"fixed",inset:0,background:"#0009",zIndex:9999,display:"flex",alignItems:"center",justifyContent:"center"}}>
          <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:16,padding:32,width:"min(96vw,620px)",maxHeight:"90vh",overflowY:"auto"}}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20}}>
              <div style={{fontSize:20,fontWeight:800,color:"#06b6d4"}}>🔗 ServiceNow Integration</div>
              <button onClick={()=>setShowSN(false)} style={{background:"none",border:"none",color:p.textMute,fontSize:20,cursor:"pointer"}}>✕</button>
            </div>

            {/* Connection */}
            <div style={{fontSize:13,fontWeight:700,color:p.textMute,marginBottom:8}}>CONNECTION</div>
            {[
              {label:"Instance URL",  key:"instance_url",  placeholder:"https://your-instance.service-now.com",type:"text"},
              {label:"Username",      key:"username",       placeholder:"admin",type:"text"},
              {label:"Password",      key:"password",       placeholder:"••••••••",type:"password"},
              {label:"Client ID (OAuth, optional)", key:"client_id", placeholder:"",type:"text"},
              {label:"Client Secret (OAuth, optional)", key:"client_secret", placeholder:"",type:"password"},
            ].map(f=>(
              <div key={f.key} style={{marginBottom:12}}>
                <label style={{fontSize:12,color:p.textMute,fontWeight:600}}>{f.label}</label>
                <input type={f.type} value={snCfg[f.key]||""} onChange={e=>setSnCfg(c=>({...c,[f.key]:e.target.value}))}
                  placeholder={f.placeholder}
                  style={{display:"block",width:"100%",padding:"8px 12px",borderRadius:8,border:`1px solid ${p.border}`,background:p.panelAlt,color:p.text,fontSize:14,marginTop:4,boxSizing:"border-box"}}/>
              </div>
            ))}

            {/* Defaults */}
            <div style={{fontSize:13,fontWeight:700,color:p.textMute,margin:"16px 0 8px"}}>DEFAULTS (written to every CI)</div>
            {[
              {label:"Company",       key:"default_company"},
              {label:"Business Unit", key:"default_bu"},
            ].map(f=>(
              <div key={f.key} style={{marginBottom:12}}>
                <label style={{fontSize:12,color:p.textMute,fontWeight:600}}>{f.label}</label>
                <input value={snCfg[f.key]||""} onChange={e=>setSnCfg(c=>({...c,[f.key]:e.target.value}))}
                  style={{display:"block",width:"100%",padding:"8px 12px",borderRadius:8,border:`1px solid ${p.border}`,background:p.panelAlt,color:p.text,fontSize:14,marginTop:4,boxSizing:"border-box"}}/>
              </div>
            ))}

            {/* Push toggles */}
            <div style={{fontSize:13,fontWeight:700,color:p.textMute,margin:"16px 0 8px"}}>CI CLASSES TO PUSH</div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8,marginBottom:20}}>
              {[
                {key:"push_vm",      label:"Virtual Machines"},
                {key:"push_host",    label:"Hosts (ESXi/HV/Nutanix/OCP)"},
                {key:"push_storage", label:"Storage Arrays"},
                {key:"push_network", label:"IP Networks"},
                {key:"push_physical",label:"Physical Servers"},
              ].map(t=>(
                <label key={t.key} style={{display:"flex",alignItems:"center",gap:8,cursor:"pointer",fontSize:13}}>
                  <input type="checkbox" checked={!!snCfg[t.key]} onChange={e=>setSnCfg(c=>({...c,[t.key]:e.target.checked}))}/>
                  {t.label}
                </label>
              ))}
            </div>

            {/* Push buttons */}
            <div style={{display:"flex",gap:8,marginBottom:16}}>
              <button onClick={()=>doPush(true)} disabled={pushing||!snCfg.instance_url}
                style={{flex:1,padding:"9px",borderRadius:8,border:"1.5px solid #f59e0b",background:"none",color:"#f59e0b",fontWeight:700,fontSize:13,cursor:"pointer"}}>
                {pushing?"Pushing…":"🔍 Dry Run (test)"}
              </button>
              <button onClick={()=>doPush(false)} disabled={pushing||!snCfg.instance_url}
                style={{flex:1,padding:"9px",borderRadius:8,border:"1.5px solid #10b981",background:pushing?"#10b98130":"#10b981",color:"#fff",fontWeight:700,fontSize:13,cursor:pushing?"wait":"pointer"}}>
                {pushing?"Pushing…":"🚀 Push to ServiceNow"}
              </button>
            </div>

            {pushResult&&(
              <div style={{padding:"12px 16px",borderRadius:8,background:pushResult.error?"#2d1515":pushResult.errors>0?"#2d1f00":"#0f291a",border:`1px solid ${pushResult.error?"#ef4444":pushResult.errors>0?"#f59e0b":"#10b981"}`,marginBottom:16,fontSize:13}}>
                {pushResult.error?(
                  <span style={{color:"#ef4444"}}>❌ {pushResult.error}</span>
                ):(
                  <>
                    <div style={{color:"#10b981",fontWeight:700}}>
                      {pushResult.dry_run?"Dry Run – ":""}
                      ✅ {pushResult.pushed} pushed · ⚠️ {pushResult.errors} errors · ⏭ {pushResult.skipped} skipped
                    </div>
                    {(pushResult.error_samples||[]).map((e,i)=>(
                      <div key={i} style={{color:"#ef4444",marginTop:4,fontSize:12}}>{e.ci}: {e.error}</div>
                    ))}
                  </>
                )}
              </div>
            )}

            <div style={{display:"flex",gap:8}}>
              <button onClick={saveSNConfig} disabled={snSaving}
                style={{flex:1,padding:"10px",borderRadius:8,border:"none",background:"#06b6d4",color:"#fff",fontWeight:700,fontSize:14,cursor:snSaving?"wait":"pointer"}}>
                {snSaving?"Saving…":"💾 Save Config"}
              </button>
              <button onClick={()=>setShowSN(false)}
                style={{padding:"10px 20px",borderRadius:8,border:`1px solid ${p.border}`,background:"none",color:p.textMute,fontWeight:600,cursor:"pointer"}}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ Edit CI Modal ══ */}
      {editCI&&(
        <div style={{position:"fixed",inset:0,background:"#0009",zIndex:9999,display:"flex",alignItems:"center",justifyContent:"center"}}>
          <div style={{background:p.panel,border:`1px solid ${p.border}`,borderRadius:16,padding:28,width:"min(96vw,560px)",maxHeight:"90vh",overflowY:"auto"}}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:16}}>
              <div style={{fontSize:16,fontWeight:800,color:"#8b5cf6"}}>✏️ Edit CI: {editCI.name}</div>
              <button onClick={()=>setEditCI(null)} style={{background:"none",border:"none",color:p.textMute,fontSize:20,cursor:"pointer"}}>✕</button>
            </div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
              {[
                {label:"Name",              key:"name"},
                {label:"Operational Status",key:"operational_status"},
                {label:"Environment",       key:"environment"},
                {label:"Department",        key:"department"},
                {label:"Business Unit",     key:"business_unit"},
                {label:"Company",           key:"company"},
                {label:"Location",          key:"location"},
                {label:"IP Address",        key:"ip_address"},
                {label:"FQDN",              key:"fqdn"},
                {label:"OS",                key:"os"},
                {label:"OS Version",        key:"os_version"},
                {label:"Serial Number",     key:"serial_number"},
                {label:"Model",             key:"model_id"},
                {label:"Manufacturer",      key:"manufacturer"},
                {label:"Asset Tag",         key:"asset_tag"},
              ].map(f=>(
                <div key={f.key}>
                  <label style={{fontSize:11,color:p.textMute,fontWeight:600}}>{f.label.toUpperCase()}</label>
                  <input value={editCI[f.key]||""} onChange={e=>setEditCI(c=>({...c,[f.key]:e.target.value}))}
                    style={{display:"block",width:"100%",padding:"6px 10px",borderRadius:6,border:`1px solid ${p.border}`,background:p.panelAlt,color:p.text,fontSize:13,marginTop:3,boxSizing:"border-box"}}/>
                </div>
              ))}
            </div>
            <div style={{display:"flex",gap:8,marginTop:18}}>
              <button onClick={saveEditCI} disabled={editBusy}
                style={{flex:1,padding:"9px",borderRadius:8,border:"none",background:"#8b5cf6",color:"#fff",fontWeight:700,fontSize:14,cursor:editBusy?"wait":"pointer"}}>
                {editBusy?"Saving…":"💾 Save Changes"}
              </button>
              <button onClick={()=>setEditCI(null)}
                style={{padding:"9px 20px",borderRadius:8,border:`1px solid ${p.border}`,background:"none",color:p.textMute,cursor:"pointer"}}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

'''

INSERT_BEFORE = '// ─── APP ─────────────────────────────────────────────────────────────────────\nexport default '

if INSERT_BEFORE not in content:
    # try alternate
    INSERT_BEFORE2 = '// ─── APP ──────────────────────────────────────────────────────────────────────\nexport default '
    if INSERT_BEFORE2 in content:
        INSERT_BEFORE = INSERT_BEFORE2
        print("Using alternate INSERT_BEFORE")
    else:
        print("ERROR: INSERT_BEFORE not found")
        # Find it
        import re
        m = re.search(r'// ─+ APP ─+\nexport default ', content)
        if m:
            INSERT_BEFORE = content[m.start():m.start()+60]
            print(f"Found: {repr(INSERT_BEFORE)}")
        else:
            print("Not found at all")

if INSERT_BEFORE in content:
    content = content.replace(INSERT_BEFORE, CMDB_PAGE + INSERT_BEFORE, 1)
    print("OK: CMDBPage component inserted")

with open(r'c:\caas-dashboard\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.write(content)

lines = content.count('\n') + 1
print(f"Final App.jsx: {lines} lines")
