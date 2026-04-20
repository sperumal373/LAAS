import { useState, useEffect, useCallback } from "react";
import {
  fetchAAPInstances, createAAPInstance, updateAAPInstance,
  deleteAAPInstance, testAAPInstance,
  fetchAAPDashboard, fetchAAPJobs, fetchAAPJobOutput, fetchAAPTemplates,
  fetchAAPInventories, fetchAAPProjects, fetchAAPHosts,
  fetchAAPCredentials, fetchAAPOrganizations, fetchAAPUsers,
  fetchAAPTeams, fetchAAPSchedules,
  launchAAPTemplate, cancelAAPJob, deleteAAPJob, deleteAAPTemplate,
  syncAAPInventory, deleteAAPInventory,
  syncAAPProject, deleteAAPProject,
  toggleAAPHost, deleteAAPHost,
  deleteAAPCredential,
  toggleAAPSchedule, deleteAAPSchedule,
  createAAPUser, deleteAAPUser,
  createAAPTemplate, updateAAPTemplate,
  createAAPInventory, updateAAPInventory,
  createAAPProject, updateAAPProject,
  createAAPCredential, updateAAPCredential,
  fetchAAPWorkflows, createAAPWorkflow, updateAAPWorkflow, deleteAAPWorkflow, launchAAPWorkflow,
  fetchAAPExecutionEnvironments, fetchAAPProjectLocalPaths,
} from "./api";

// ─── helpers ─────────────────────────────────────────────────────────────────
function _age(iso) {
  if (!iso) return "—";
  const d = Math.floor((Date.now() - new Date(iso)) / 864e5);
  if (d < 1) return "<1d"; if (d < 30) return `${d}d`;
  const m = Math.floor(d / 30); if (m < 12) return `${m}mo`;
  return `${Math.floor(m / 12)}y`;
}
function _elapsed(sec) {
  if (!sec) return "—";
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
}
function _dt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" });
}

function Spinner() {
  return (
    <div style={{ display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:56,gap:14 }}>
      <div className="spinner"/>
      <span style={{ fontSize:13,color:"#94a3b8" }}>Loading…</span>
    </div>
  );
}
function ErrMsg({ msg, onRetry }) {
  return (
    <div style={{ textAlign:"center",padding:40 }}>
      <div style={{ fontSize:34,marginBottom:10 }}>⚠️</div>
      <div style={{ color:"#ef4444",fontWeight:600,marginBottom:6 }}>Error</div>
      <div style={{ fontSize:12,color:"#94a3b8",marginBottom:14,maxWidth:340,margin:"0 auto 14px" }}>{msg}</div>
      {onRetry && <button className="btn btn-danger" onClick={onRetry}>↺ Retry</button>}
    </div>
  );
}

// ─── Status badge helper ──────────────────────────────────────────────────────
function JobStatusBadge({ status }) {
  const map = {
    successful: { color:"#10b981", bg:"#10b98115", label:"Successful" },
    failed:     { color:"#ef4444", bg:"#ef444415", label:"Failed" },
    running:    { color:"#3b82f6", bg:"#3b82f615", label:"Running" },
    pending:    { color:"#f59e0b", bg:"#f59e0b15", label:"Pending" },
    canceled:   { color:"#6b7280", bg:"#6b728015", label:"Canceled" },
    waiting:    { color:"#a78bfa", bg:"#a78bfa15", label:"Waiting" },
  };
  const s = map[status?.toLowerCase()] || { color:"#64748b", bg:"#64748b15", label: status||"Unknown" };
  return (
    <span style={{ display:"inline-flex",alignItems:"center",gap:4,padding:"2px 9px",borderRadius:99,
                   fontSize:11,fontWeight:700,color:s.color,background:s.bg,border:`1px solid ${s.color}28` }}>
      <span style={{ width:5,height:5,borderRadius:"50%",background:s.color,flexShrink:0 }}/>
      {s.label}
    </span>
  );
}
function HealthBadge({ ok, label }) {
  return (
    <span style={{ display:"inline-block",padding:"2px 8px",borderRadius:99,fontSize:11,fontWeight:600,
                   color:ok?"#10b981":"#ef4444", background:ok?"#10b98115":"#ef444415",
                   border:`1px solid ${ok?"#10b98128":"#ef444428"}` }}>
      {ok ? "✓" : "✗"} {label}
    </span>
  );
}

// ─── Confirm Dialog ──────────────────────────────────────────────────────────
function ConfirmDialog({ title, message, onConfirm, onCancel, busy, err, danger=true, p }) {
  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3000,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e=>e.target===e.currentTarget&&onCancel()}>
      <div style={{ background:p.panel,border:`1px solid ${danger?"#ef444438":p.border}`,
                    borderRadius:14,padding:28,maxWidth:400,width:"100%",
                    boxShadow:"0 20px 60px #00000080" }}>
        <div style={{ fontSize:24,marginBottom:10 }}>{danger?"⚠️":"ℹ️"}</div>
        <div style={{ fontWeight:700,fontSize:16,color:danger?"#ef4444":p.text,marginBottom:8 }}>{title}</div>
        <div style={{ fontSize:13,color:p.textMute,marginBottom:16 }}>{message}</div>
        {err && <div style={{ fontSize:12,color:"#ef4444",background:"#ef444412",padding:"8px 12px",
                               borderRadius:6,marginBottom:12 }}>{err}</div>}
        <div style={{ display:"flex",gap:10,justifyContent:"flex-end" }}>
          <button onClick={onCancel} style={{ padding:"8px 18px",borderRadius:7,border:`1px solid ${p.border}`,
                                              background:"transparent",color:p.text,cursor:"pointer",fontSize:13 }}>
            Cancel
          </button>
          <button disabled={busy} onClick={onConfirm}
            style={{ padding:"8px 20px",borderRadius:7,border:"none",
                     background:danger?"#ef4444":"#3b82f6",color:"#fff",
                     cursor:"pointer",fontWeight:700,fontSize:13,opacity:busy?0.6:1 }}>
            {busy ? "Processing…" : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Launch Modal ─────────────────────────────────────────────────────────────
function LaunchModal({ template, onLaunch, onClose, busy, err, p }) {
  const [extraVars, setExtraVars] = useState("");
  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3000,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ background:p.panel,border:"1px solid #10b98138",borderRadius:14,padding:28,
                    maxWidth:520,width:"100%",boxShadow:"0 20px 60px #00000080" }}>
        <div style={{ display:"flex",alignItems:"center",gap:10,marginBottom:20 }}>
          <span style={{ fontSize:24 }}>🚀</span>
          <div>
            <div style={{ fontWeight:700,fontSize:16,color:"#10b981" }}>Launch Job Template</div>
            <div style={{ fontSize:12,color:"#64748b" }}>{template.name}</div>
          </div>
          <button onClick={onClose} style={{ marginLeft:"auto",background:"#ef444412",border:"1px solid #ef444430",
                                             color:"#ef4444",borderRadius:6,padding:"3px 10px",cursor:"pointer",fontWeight:700 }}>✕</button>
        </div>
        <div style={{ marginBottom:16 }}>
          <div style={{ fontSize:12,fontWeight:600,color:"#475569",marginBottom:6 }}>
            Extra Variables <span style={{ fontWeight:400,color:"#94a3b8" }}>(YAML / JSON, optional)</span>
          </div>
          <textarea value={extraVars} onChange={e=>setExtraVars(e.target.value)} rows={5}
            placeholder={'---\nmy_var: value'}
            style={{ width:"100%",padding:10,fontSize:12,fontFamily:"monospace",
                     background:"#0f172a",color:"#e2e8f0",border:"1px solid #334155",
                     borderRadius:8,resize:"vertical",outline:"none",boxSizing:"border-box" }}/>
        </div>
        {err && <div style={{ fontSize:12,color:"#ef4444",background:"#ef444412",padding:"8px 12px",borderRadius:6,marginBottom:12 }}>{err}</div>}
        <div style={{ display:"flex",gap:10,justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{ padding:"8px 18px",borderRadius:7,border:`1px solid ${p.border}`,background:"transparent",color:p.text,cursor:"pointer",fontSize:13 }}>Cancel</button>
          <button disabled={busy} onClick={()=>onLaunch(extraVars)}
            style={{ padding:"8px 22px",borderRadius:7,border:"none",background:"#10b981",color:"#fff",
                     cursor:"pointer",fontWeight:700,fontSize:13,opacity:busy?0.6:1 }}>
            {busy ? "Launching…" : "🚀 Launch"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Job Output Modal ─────────────────────────────────────────────────────────
function JobOutputModal({ job, instId, onClose, p }) {
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetchAAPJobOutput(instId, job.id)
      .then(o => setOutput(o))
      .catch(e => setOutput(`[Error] ${e.message}`))
      .finally(() => setLoading(false));
  }, [instId, job.id]);
  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3000,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ background:"#0f172a",border:"1px solid #1e293b",borderRadius:14,padding:24,
                    maxWidth:960,width:"100%",maxHeight:"90vh",display:"flex",flexDirection:"column",
                    boxShadow:"0 20px 60px #00000080" }}>
        <div style={{ display:"flex",alignItems:"center",gap:10,marginBottom:16,flexShrink:0 }}>
          <span style={{ fontSize:22 }}>📄</span>
          <div style={{ flex:1 }}>
            <div style={{ fontWeight:700,fontSize:14,color:"#10b981" }}>Job Output</div>
            <div style={{ fontSize:11,color:"#64748b" }}>Job #{job.id} — {job.name || job.job_template}</div>
          </div>
          <JobStatusBadge status={job.status}/>
          <button onClick={onClose} style={{ background:"#ef444412",border:"1px solid #ef444430",
                                             color:"#ef4444",borderRadius:6,padding:"3px 10px",cursor:"pointer",fontWeight:700 }}>✕</button>
        </div>
        <div style={{ flex:1,overflowY:"auto" }}>
          {loading ? <Spinner/> :
            <pre style={{ fontSize:11,lineHeight:1.6,color:"#cbd5e1",fontFamily:"monospace",
                          whiteSpace:"pre-wrap",wordBreak:"break-all",margin:0,padding:8 }}>
              {output || "(no output)"}
            </pre>
          }
        </div>
      </div>
    </div>
  );
}

// ─── Create/Edit User Modal ───────────────────────────────────────────────────
function UserFormModal({ instId, onDone, onClose, busy, setBusy, p }) {
  const [form, setForm] = useState({ username:"", password:"", first_name:"", last_name:"", email:"", is_superuser:false });
  const [err, setErr] = useState(null);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.type==="checkbox"?e.target.checked:e.target.value }));
  async function submit() {
    if (!form.username || !form.password) { setErr("Username and password are required."); return; }
    setBusy(true); setErr(null);
    try { await createAAPUser(instId, form); onDone(); }
    catch(e) { setErr(e.message); }
    setBusy(false);
  }
  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3000,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ background:p.panel,border:"1px solid #3b82f630",borderRadius:14,padding:28,
                    maxWidth:480,width:"100%",boxShadow:"0 20px 60px #00000080" }}>
        <div style={{ display:"flex",alignItems:"center",gap:10,marginBottom:20 }}>
          <span style={{ fontSize:24 }}>👤</span>
          <div style={{ fontWeight:700,fontSize:16,color:"#3b82f6" }}>Create AAP User</div>
          <button onClick={onClose} style={{ marginLeft:"auto",background:"#ef444412",border:"1px solid #ef444430",
                                             color:"#ef4444",borderRadius:6,padding:"3px 10px",cursor:"pointer",fontWeight:700 }}>✕</button>
        </div>
        {[["username","Username *"],["password","Password *"],["first_name","First Name"],["last_name","Last Name"],["email","Email"]].map(([k,lbl])=>(
          <div key={k} style={{ marginBottom:12 }}>
            <div style={{ fontSize:11,fontWeight:600,color:"#475569",marginBottom:4 }}>{lbl}</div>
            <input type={k==="password"?"password":"text"} value={form[k]} onChange={set(k)}
              style={{ width:"100%",padding:"8px 10px",borderRadius:7,border:`1px solid ${p.border}`,
                       background:p.surface,color:p.text,fontSize:13,boxSizing:"border-box" }}/>
          </div>
        ))}
        <label style={{ display:"flex",alignItems:"center",gap:8,marginBottom:16,cursor:"pointer" }}>
          <input type="checkbox" checked={form.is_superuser} onChange={set("is_superuser")}/>
          <span style={{ fontSize:13,color:p.text }}>Superuser (System Administrator)</span>
        </label>
        {err && <div style={{ fontSize:12,color:"#ef4444",background:"#ef444412",padding:"8px 12px",borderRadius:6,marginBottom:12 }}>{err}</div>}
        <div style={{ display:"flex",gap:10,justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{ padding:"8px 18px",borderRadius:7,border:`1px solid ${p.border}`,background:"transparent",color:p.text,cursor:"pointer",fontSize:13 }}>Cancel</button>
          <button disabled={busy} onClick={submit}
            style={{ padding:"8px 22px",borderRadius:7,border:"none",background:"#3b82f6",color:"#fff",
                     cursor:"pointer",fontWeight:700,fontSize:13,opacity:busy?0.6:1 }}>
            {busy ? "Creating…" : "Create User"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Instance Form Modal ──────────────────────────────────────────────────────
function InstanceFormModal({ existing, onSave, onClose, p }) {
  const [form, setForm] = useState(existing || { name:"", url:"", username:"", password:"", env:"PROD", description:"" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  async function submit() {
    if (!form.name || !form.url || !form.username || !form.password) {
      setErr("Name, URL, username and password are required."); return;
    }
    setBusy(true); setErr(null);
    try {
      if (existing?.id) await updateAAPInstance(existing.id, form);
      else await createAAPInstance(form);
      onSave();
    } catch(e) { setErr(e.message); }
    setBusy(false);
  }
  const envOpts = ["PROD","PROD1","STAGING","DEV","DR","TEST"];
  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3000,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ background:p.panel,border:"1px solid #ee000030",borderRadius:16,padding:28,
                    maxWidth:540,width:"100%",boxShadow:"0 24px 70px #00000090" }}>
        {/* Header */}
        <div style={{ display:"flex",alignItems:"center",gap:12,marginBottom:22 }}>
          <img src="https://logo.clearbit.com/redhat.com" alt="AAP" width={32} height={32}
               style={{ borderRadius:6 }} onError={e=>{e.target.style.display="none";}}/>
          <div>
            <div style={{ fontWeight:800,fontSize:17,color:"#ee0000" }}>
              {existing?.id ? "Edit AAP Instance" : "Add AAP Instance"}
            </div>
            <div style={{ fontSize:12,color:"#64748b" }}>Ansible Automation Platform</div>
          </div>
          <button onClick={onClose} style={{ marginLeft:"auto",background:"#ef444412",border:"1px solid #ef444430",
                                             color:"#ef4444",borderRadius:6,padding:"3px 10px",cursor:"pointer",fontWeight:700 }}>✕</button>
        </div>

        {/* Fields */}
        {[["name","Instance Name *","e.g. PROD"],
          ["url","AAP URL *","https://aap.example.com"],
          ["username","Username *","admin"],
          ["password","Password *",""],
          ["description","Description","Optional notes"]
        ].map(([k,lbl,ph])=>(
          <div key={k} style={{ marginBottom:14 }}>
            <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:5,letterSpacing:.3 }}>{lbl.toUpperCase()}</div>
            <input type={k==="password"?"password":"text"} value={form[k]||""} onChange={set(k)}
              placeholder={ph}
              style={{ width:"100%",padding:"9px 12px",borderRadius:8,border:`1px solid ${p.border}`,
                       background:p.surface,color:p.text,fontSize:13,boxSizing:"border-box",outline:"none" }}/>
          </div>
        ))}
        <div style={{ marginBottom:18 }}>
          <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:5,letterSpacing:.3 }}>ENVIRONMENT</div>
          <div style={{ display:"flex",gap:8,flexWrap:"wrap" }}>
            {envOpts.map(e=>(
              <button key={e} onClick={()=>setForm(f=>({...f,env:e}))}
                style={{ padding:"6px 14px",borderRadius:20,border:"none",cursor:"pointer",fontSize:12,fontWeight:700,
                         background:form.env===e?"#ee0000":"#f1f5f9",color:form.env===e?"#fff":"#475569" }}>
                {e}
              </button>
            ))}
          </div>
        </div>

        {err && <div style={{ fontSize:12,color:"#ef4444",background:"#ef444412",padding:"8px 12px",borderRadius:6,marginBottom:12 }}>{err}</div>}
        <div style={{ display:"flex",gap:10,justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{ padding:"8px 18px",borderRadius:7,border:`1px solid ${p.border}`,background:"transparent",color:p.text,cursor:"pointer",fontSize:13 }}>Cancel</button>
          <button disabled={busy} onClick={submit}
            style={{ padding:"9px 24px",borderRadius:8,border:"none",background:"linear-gradient(135deg,#ee0000,#b91c1c)",
                     color:"#fff",cursor:"pointer",fontWeight:800,fontSize:13,opacity:busy?0.6:1 }}>
            {busy ? "Saving…" : (existing?.id ? "Save Changes" : "Add Instance")}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Dashboard overview cards ──────────────────────────────────────────────────
function DashboardTab({ instId, p }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setLoading(true);
    fetchAAPDashboard(instId)
      .then(d => { setData(d); setErr(null); })
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false));
  }, [instId]);
  if (loading) return <Spinner/>;
  if (err) return <ErrMsg msg={err} onRetry={()=>{ setLoading(true); fetchAAPDashboard(instId).then(setData).catch(e=>setErr(e.message)).finally(()=>setLoading(false)); }}/>;
  if (!data) return null;
  const kpis = [
    { icon:"🔄", label:"Total Jobs",       value:data.jobs_total||0,        color:"#3b82f6" },
    { icon:"✅", label:"Jobs Succeeded",   value:data.jobs_succeeded||0,     color:"#10b981" },
    { icon:"❌", label:"Jobs Failed",      value:data.jobs_failed||0,        color:"#ef4444" },
    { icon:"📦", label:"Inventories",      value:data.inventories_total||0,  color:"#6366f1" },
    { icon:"📁", label:"Projects",         value:data.projects_total||0,     color:"#f59e0b" },
    { icon:"⚙️", label:"Job Templates",   value:data.templates_total||0,    color:"#ee0000" },
    { icon:"🖥️", label:"Hosts",           value:data.hosts_total||0,        color:"#06b6d4" },
    { icon:"⚠️", label:"Hosts Failed",    value:data.hosts_failed||0,       color:"#f97316" },
  ];
  return (
    <div style={{ padding:"24px 28px" }}>
      <h2 style={{ margin:"0 0 20px",fontSize:18,fontWeight:700,color:p.text }}>📊 Dashboard Overview</h2>
      <div style={{ display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(180px,1fr))",gap:14 }}>
        {kpis.map(k=>(
          <div key={k.label} style={{ background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,
                                       padding:"18px 20px",boxShadow:"0 1px 4px #0000000a" }}>
            <div style={{ fontSize:24,marginBottom:6 }}>{k.icon}</div>
            <div style={{ fontSize:28,fontWeight:800,color:k.color,lineHeight:1 }}>{k.value.toLocaleString()}</div>
            <div style={{ fontSize:12,color:p.textMute,marginTop:4,fontWeight:500 }}>{k.label}</div>
          </div>
        ))}
      </div>
      {data.error && <div style={{ marginTop:20,padding:14,background:"#ef444412",borderRadius:8,color:"#ef4444",fontSize:13 }}>⚠️ {data.error}</div>}
    </div>
  );
}

// ─── Generic resource table ───────────────────────────────────────────────────
function ResourceTable({ columns, rows, actions, loading, err, onRetry, emptyMsg, searchKeys=[], p }) {
  const [q, setQ] = useState("");
  const filtered = q ? rows.filter(r => searchKeys.some(k => String(r[k]||"").toLowerCase().includes(q.toLowerCase()))) : rows;
  if (loading) return <Spinner/>;
  if (err) return <ErrMsg msg={err} onRetry={onRetry}/>;
  return (
    <div>
      {searchKeys.length > 0 && (
        <div style={{ marginBottom:12,display:"flex",gap:10,alignItems:"center" }}>
          <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search…"
            style={{ padding:"7px 12px",borderRadius:7,border:`1px solid ${p.border}`,fontSize:12,
                     background:p.surface,color:p.text,width:240,outline:"none" }}/>
          <span style={{ fontSize:12,color:p.textMute,marginLeft:"auto" }}>
            {filtered.length} / {rows.length} items
          </span>
        </div>
      )}
      {filtered.length === 0 ? (
        <div style={{ textAlign:"center",padding:48,color:p.textMute,fontSize:13 }}>{emptyMsg||"No items found."}</div>
      ) : (
        <div style={{ background:p.panel,border:`1px solid ${p.border}`,borderRadius:12,overflow:"hidden",
                      boxShadow:"0 1px 4px #0000000a" }}>
          <table style={{ width:"100%",borderCollapse:"collapse" }}>
            <thead>
              <tr style={{ background:p.surface,borderBottom:`2px solid ${p.border}` }}>
                {columns.map(c=>(
                  <th key={c.key} style={{ padding:"10px 14px",textAlign:"left",fontSize:11,
                                           fontWeight:700,color:p.textMute,letterSpacing:.5,
                                           whiteSpace:"nowrap" }}>{c.label}</th>
                ))}
                {actions && <th style={{ padding:"10px 14px",fontSize:11,fontWeight:700,color:p.textMute }}>ACTIONS</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((row,i)=>(
                <tr key={row.id||i} style={{ borderBottom:`1px solid ${p.border}` }}>
                  {columns.map(c=>(
                    <td key={c.key} style={{ padding:"9px 14px",fontSize:13,color:p.text,
                                             maxWidth:c.maxW||280,overflow:"hidden",textOverflow:"ellipsis",
                                             whiteSpace:c.wrap?"normal":"nowrap" }}>
                      {c.render ? c.render(row) : (row[c.key]??"—")}
                    </td>
                  ))}
                  {actions && (
                    <td style={{ padding:"8px 12px",whiteSpace:"nowrap" }}>
                      {actions(row)}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Tab content components ───────────────────────────────────────────────────
function JobsTab({ instId, canAct, isAdmin, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [outputJob, setOutputJob] = useState(null);
  const [confirm, setConfirm] = useState(null); // {action,job}
  const [busy, setBusy] = useState(false);
  const [cErr, setCErr] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchAAPJobs(instId, 200)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);

  async function doConfirm() {
    setBusy(true); setCErr(null);
    try {
      if (confirm.action === "cancel") await cancelAAPJob(instId, confirm.job.id);
      else await deleteAAPJob(instId, confirm.job.id);
      setConfirm(null);
      load();
    } catch(e) { setCErr(e.message); }
    setBusy(false);
  }

  const cols = [
    { key:"id",           label:"ID",       maxW:60 },
    { key:"job_template", label:"Template",  maxW:200 },
    { key:"status",       label:"Status",    render:r=><JobStatusBadge status={r.status}/> },
    { key:"launched_by",  label:"Launched By" },
    { key:"inventory",    label:"Inventory" },
    { key:"elapsed",      label:"Duration",  render:r=>_elapsed(r.elapsed) },
    { key:"started",      label:"Started",   render:r=>_dt(r.started) },
    { key:"finished",     label:"Finished",  render:r=>_dt(r.finished) },
  ];

  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>🔄 Jobs <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No jobs found." searchKeys={["job_template","status","launched_by","inventory"]} p={p}
        actions={row=>(
          <span style={{ display:"flex",gap:4 }}>
            <button title="View Output" onClick={()=>setOutputJob(row)}
              style={{ background:"#f1f5f9",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#475569" }}>📄 Output</button>
            {canAct && (row.status==="running"||row.status==="waiting"||row.status==="pending") &&
              <button title="Cancel Job" onClick={()=>{ setCErr(null); setConfirm({action:"cancel",job:row}); }}
                style={{ background:"#fef3c7",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#b45309" }}>⏹ Cancel</button>}
            {canAct &&
              <button title="Delete Job" onClick={()=>{ setCErr(null); setConfirm({action:"delete",job:row}); }}
                style={{ background:"#fff1f2",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#ef4444" }}>🗑️</button>}
          </span>
        )}/>
      {outputJob && <JobOutputModal job={outputJob} instId={instId} onClose={()=>setOutputJob(null)} p={p}/>}
      {confirm && (
        <ConfirmDialog p={p} busy={busy} err={cErr}
          title={confirm.action==="cancel" ? "Cancel Job?" : "Delete Job?"}
          message={`Job #${confirm.job.id} — ${confirm.job.job_template||confirm.job.name||""}`}
          onConfirm={doConfirm} onCancel={()=>setConfirm(null)}/>
      )}
    </div>
  );
}

// ─── Job Template Form Modal ──────────────────────────────────────────────────
function TemplateFormModal({ instId, existing, orgs, projects, inventories, onSave, onClose, p }) {
  const empty = { name:"", description:"", job_type:"run", project:0, playbook:"", inventory:0,
                  credential:0, verbosity:0, extra_vars:"", become_enabled:false };
  const [form, setForm] = useState(existing
    ? { name:existing.name||"", description:existing.description||"",
        job_type:existing.job_type||"run", project:existing.project_id||0,
        playbook:existing.playbook||"", inventory:existing.inventory_id||0,
        credential:0, verbosity:existing.verbosity||0,
        extra_vars:existing.extra_vars||"", become_enabled:existing.become_enabled||false }
    : empty);
  const [busy, setBusy] = useState(false);
  const [err,  setErr]  = useState(null);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.type==="checkbox"?e.target.checked:e.target.type==="number"?Number(e.target.value):e.target.value }));
  async function submit() {
    if (!form.name || !form.playbook || !form.project) { setErr("Name, Project and Playbook are required."); return; }
    setBusy(true); setErr(null);
    try {
      if (existing) await updateAAPTemplate(instId, existing.id, form);
      else          await createAAPTemplate(instId, form);
      onSave();
    } catch(e) { setErr(e.message); }
    setBusy(false);
  }
  const isEdit = !!existing;
  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3100,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ background:p.panel,border:"1px solid #10b98138",borderRadius:16,padding:28,
                    maxWidth:580,width:"100%",maxHeight:"92vh",overflowY:"auto",
                    boxShadow:"0 24px 70px #00000090" }}>
        <div style={{ display:"flex",alignItems:"center",gap:10,marginBottom:22 }}>
          <span style={{ fontSize:26 }}>⚙️</span>
          <div>
            <div style={{ fontWeight:800,fontSize:16,color:"#10b981" }}>{isEdit?"Edit":"New"} Job Template</div>
            <div style={{ fontSize:12,color:"#64748b" }}>{isEdit?`Editing: ${existing.name}`:"Create a new job template in AAP"}</div>
          </div>
          <button onClick={onClose} style={{ marginLeft:"auto",background:"#ef444412",border:"1px solid #ef444430",
                                             color:"#ef4444",borderRadius:6,padding:"3px 10px",cursor:"pointer",fontWeight:700 }}>✕</button>
        </div>
        {/* Name + Description */}
        {[["name","Name *"],["description","Description"],["playbook","Playbook *"]].map(([k,lbl])=>(
          <div key={k} style={{ marginBottom:13 }}>
            <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>{lbl.toUpperCase()}</div>
            <input value={form[k]||""} onChange={set(k)} placeholder={k==="playbook"?"site.yml":""} 
              style={{ width:"100%",padding:"8px 11px",borderRadius:7,border:`1px solid ${p.border}`,
                       background:p.surface,color:p.text,fontSize:13,boxSizing:"border-box" }}/>
          </div>
        ))}
        {/* Job Type */}
        <div style={{ marginBottom:13 }}>
          <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>JOB TYPE</div>
          <select value={form.job_type} onChange={set("job_type")}
            style={{ width:"100%",padding:"8px 11px",borderRadius:7,border:`1px solid ${p.border}`,
                     background:p.surface,color:p.text,fontSize:13 }}>
            <option value="run">Run</option>
            <option value="check">Check (Dry Run)</option>
          </select>
        </div>
        {/* Verbosity */}
        <div style={{ marginBottom:13 }}>
          <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>VERBOSITY</div>
          <select value={form.verbosity} onChange={set("verbosity")}
            style={{ width:"100%",padding:"8px 11px",borderRadius:7,border:`1px solid ${p.border}`,
                     background:p.surface,color:p.text,fontSize:13 }}>
            {[0,1,2,3,4,5].map(v=><option key={v} value={v}>{v} — {["Normal","Verbose","More Verbose","Debug","Connection Debug","WinRM Debug"][v]}</option>)}
          </select>
        </div>
        {/* Extra Vars */}
        <div style={{ marginBottom:13 }}>
          <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>EXTRA VARIABLES (YAML/JSON)</div>
          <textarea value={form.extra_vars||""} onChange={set("extra_vars")} rows={3}
            placeholder={"---\nmy_var: value"}
            style={{ width:"100%",padding:10,fontSize:12,fontFamily:"monospace",
                     background:"#0f172a",color:"#e2e8f0",border:"1px solid #334155",
                     borderRadius:8,resize:"vertical",outline:"none",boxSizing:"border-box" }}/>
        </div>
        {/* Become */}
        <label style={{ display:"flex",alignItems:"center",gap:8,marginBottom:16,cursor:"pointer" }}>
          <input type="checkbox" checked={form.become_enabled} onChange={set("become_enabled")}/>
          <span style={{ fontSize:13,color:p.text }}>Enable Privilege Escalation (become)</span>
        </label>
        {err && <div style={{ fontSize:12,color:"#ef4444",background:"#ef444412",padding:"8px 12px",borderRadius:6,marginBottom:12 }}>{err}</div>}
        <div style={{ display:"flex",gap:10,justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{ padding:"8px 18px",borderRadius:7,border:`1px solid ${p.border}`,background:"transparent",color:p.text,cursor:"pointer",fontSize:13 }}>Cancel</button>
          <button disabled={busy} onClick={submit}
            style={{ padding:"9px 22px",borderRadius:8,border:"none",background:"#10b981",color:"#fff",
                     cursor:"pointer",fontWeight:800,fontSize:13,opacity:busy?0.6:1 }}>
            {busy?(isEdit?"Saving…":"Creating…"):(isEdit?"💾 Save Changes":"➕ Create Template")}
          </button>
        </div>
      </div>
    </div>
  );
}

function TemplatesTab({ instId, canAct, isAdmin, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [launchTpl, setLaunchTpl] = useState(null);
  const [launchBusy, setLaunchBusy] = useState(false);
  const [launchErr, setLaunchErr] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState(null);
  const [formTarget, setFormTarget] = useState(null); // null=closed, false=add, obj=edit

  const load = useCallback(() => {
    setLoading(true);
    fetchAAPTemplates(instId)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);

  async function doLaunch(extraVars) {
    setLaunchBusy(true); setLaunchErr(null);
    try { await launchAAPTemplate(instId, launchTpl.id, extraVars); setLaunchTpl(null); load(); }
    catch(e) { setLaunchErr(e.message); }
    setLaunchBusy(false);
  }

  async function doDelete() {
    setDelBusy(true); setDelErr(null);
    try { await deleteAAPTemplate(instId, delTarget.id); setDelTarget(null); load(); }
    catch(e) { setDelErr(e.message); }
    setDelBusy(false);
  }

  const cols = [
    { key:"name",            label:"NAME",     maxW:220 },
    { key:"playbook",        label:"PLAYBOOK", maxW:180 },
    { key:"project",         label:"PROJECT",  maxW:160 },
    { key:"inventory",       label:"INVENTORY",maxW:160 },
    { key:"last_job_run",    label:"LAST RUN", render:r=><span style={{ fontSize:12 }}>{_dt(r.last_job_run)}</span> },
    { key:"last_job_failed", label:"STATUS",   render:r=><HealthBadge ok={!r.last_job_failed} label={r.last_job_failed?"Failed":"OK"}/> },
  ];

  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>⚙️ Job Templates <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <div style={{ display:"flex",gap:8 }}>
          {canAct && <button className="btn btn-primary btn-sm" onClick={()=>setFormTarget(false)}>＋ New Template</button>}
          <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
        </div>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No job templates found." searchKeys={["name","playbook","project","inventory"]} p={p}
        actions={row=>(
          <span style={{ display:"flex",gap:4 }}>
            {canAct && <button title="Launch" onClick={()=>{ setLaunchErr(null); setLaunchTpl(row); }}
              style={{ background:"#f0fdf4",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#16a34a",fontWeight:700 }}>🚀 Launch</button>}
            {canAct && <button title="Edit" onClick={()=>setFormTarget(row)}
              style={{ background:"#eff6ff",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#3b82f6",fontWeight:700 }}>✏️ Edit</button>}
            {isAdmin && <button title="Delete" onClick={()=>{ setDelErr(null); setDelTarget(row); }}
              style={{ background:"#fff1f2",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#ef4444" }}>🗑️</button>}
          </span>
        )}/>
      {launchTpl && <LaunchModal template={launchTpl} onLaunch={doLaunch} onClose={()=>setLaunchTpl(null)} busy={launchBusy} err={launchErr} p={p}/>}
      {formTarget !== null && (
        <TemplateFormModal instId={instId} existing={formTarget||null} p={p}
          orgs={[]} projects={[]} inventories={[]}
          onSave={()=>{ setFormTarget(null); load(); }} onClose={()=>setFormTarget(null)}/>
      )}
      {delTarget && <ConfirmDialog p={p} busy={delBusy} err={delErr}
        title="Delete Job Template?" message={`"${delTarget.name}" will be permanently deleted.`}
        onConfirm={doDelete} onCancel={()=>setDelTarget(null)}/>}
    </div>
  );
}

// ─── Inventory Form Modal ─────────────────────────────────────────────────────
function InventoryFormModal({ instId, existing, onSave, onClose, p }) {
  const empty = { name:"", description:"", organization:0, kind:"", variables:"" };
  const [form, setForm] = useState(existing
    ? { name:existing.name||"", description:existing.description||"",
        organization:existing.org_id||0, kind:existing.kind||"", variables:existing.variables||"" }
    : empty);
  const [busy, setBusy] = useState(false);
  const [err,  setErr]  = useState(null);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.value }));
  async function submit() {
    if (!form.name) { setErr("Name is required."); return; }
    setBusy(true); setErr(null);
    try {
      if (existing) await updateAAPInventory(instId, existing.id, form);
      else          await createAAPInventory(instId, form);
      onSave();
    } catch(e) { setErr(e.message); }
    setBusy(false);
  }
  const isEdit = !!existing;
  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3100,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ background:p.panel,border:"1px solid #6366f138",borderRadius:16,padding:28,
                    maxWidth:520,width:"100%",boxShadow:"0 24px 70px #00000090" }}>
        <div style={{ display:"flex",alignItems:"center",gap:10,marginBottom:22 }}>
          <span style={{ fontSize:26 }}>📦</span>
          <div>
            <div style={{ fontWeight:800,fontSize:16,color:"#6366f1" }}>{isEdit?"Edit":"New"} Inventory</div>
            <div style={{ fontSize:12,color:"#64748b" }}>{isEdit?`Editing: ${existing.name}`:"Create a new inventory in AAP"}</div>
          </div>
          <button onClick={onClose} style={{ marginLeft:"auto",background:"#ef444412",border:"1px solid #ef444430",
                                             color:"#ef4444",borderRadius:6,padding:"3px 10px",cursor:"pointer",fontWeight:700 }}>✕</button>
        </div>
        {[["name","Name *"],["description","Description"]].map(([k,lbl])=>(
          <div key={k} style={{ marginBottom:13 }}>
            <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>{lbl.toUpperCase()}</div>
            <input value={form[k]||""} onChange={set(k)}
              style={{ width:"100%",padding:"8px 11px",borderRadius:7,border:`1px solid ${p.border}`,
                       background:p.surface,color:p.text,fontSize:13,boxSizing:"border-box" }}/>
          </div>
        ))}
        <div style={{ marginBottom:13 }}>
          <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>KIND</div>
          <select value={form.kind||""} onChange={set("kind")}
            style={{ width:"100%",padding:"8px 11px",borderRadius:7,border:`1px solid ${p.border}`,background:p.surface,color:p.text,fontSize:13 }}>
            <option value="">Standard (static)</option>
            <option value="smart">Smart</option>
            <option value="constructed">Constructed</option>
          </select>
        </div>
        <div style={{ marginBottom:18 }}>
          <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>VARIABLES (YAML/JSON, optional)</div>
          <textarea value={form.variables||""} onChange={set("variables")} rows={4}
            placeholder={"---\nansible_user: ec2-user"}
            style={{ width:"100%",padding:10,fontSize:12,fontFamily:"monospace",
                     background:"#0f172a",color:"#e2e8f0",border:"1px solid #334155",
                     borderRadius:8,resize:"vertical",outline:"none",boxSizing:"border-box" }}/>
        </div>
        {err && <div style={{ fontSize:12,color:"#ef4444",background:"#ef444412",padding:"8px 12px",borderRadius:6,marginBottom:12 }}>{err}</div>}
        <div style={{ display:"flex",gap:10,justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{ padding:"8px 18px",borderRadius:7,border:`1px solid ${p.border}`,background:"transparent",color:p.text,cursor:"pointer",fontSize:13 }}>Cancel</button>
          <button disabled={busy} onClick={submit}
            style={{ padding:"9px 22px",borderRadius:8,border:"none",background:"#6366f1",color:"#fff",
                     cursor:"pointer",fontWeight:800,fontSize:13,opacity:busy?0.6:1 }}>
            {busy?(isEdit?"Saving…":"Creating…"):(isEdit?"💾 Save Changes":"➕ Create Inventory")}
          </button>
        </div>
      </div>
    </div>
  );
}

function InventoriesTab({ instId, canAct, isAdmin, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [syncTarget, setSyncTarget] = useState(null);
  const [syncBusy, setSyncBusy] = useState(false);
  const [delTarget, setDelTarget] = useState(null);
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState(null);
  const [syncErr, setSyncErr] = useState(null);
  const [formTarget, setFormTarget] = useState(null); // null=closed, false=add, obj=edit

  const load = useCallback(() => {
    setLoading(true);
    fetchAAPInventories(instId)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);

  async function doSync() {
    setSyncBusy(true); setSyncErr(null);
    try { await syncAAPInventory(instId, syncTarget.id); setSyncTarget(null); load(); }
    catch(e) { setSyncErr(e.message); }
    setSyncBusy(false);
  }
  async function doDelete() {
    setDelBusy(true); setDelErr(null);
    try { await deleteAAPInventory(instId, delTarget.id); setDelTarget(null); load(); }
    catch(e) { setDelErr(e.message); }
    setDelBusy(false);
  }

  const cols = [
    { key:"name",         label:"NAME",         maxW:220 },
    { key:"organization", label:"ORG",           maxW:160 },
    { key:"kind",         label:"TYPE",          render:r=><span style={{ fontSize:11,background:"#6366f115",color:"#6366f1",borderRadius:6,padding:"2px 8px",fontWeight:600 }}>{r.kind||"standard"}</span> },
    { key:"hosts_total",  label:"HOSTS",         render:r=><span style={{ fontSize:13,fontWeight:600,color:"#3b82f6" }}>{r.hosts_total}</span> },
    { key:"hosts_failed", label:"FAILURES",      render:r=>r.hosts_failed>0?<span style={{ color:"#ef4444",fontWeight:700 }}>{r.hosts_failed}</span>:<span style={{ color:"#10b981" }}>0</span> },
    { key:"has_active_failures", label:"STATUS", render:r=><HealthBadge ok={!r.has_active_failures} label={r.has_active_failures?"Issues":"Healthy"}/> },
  ];

  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>📦 Inventories <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <div style={{ display:"flex",gap:8 }}>
          {canAct && <button className="btn btn-primary btn-sm" onClick={()=>setFormTarget(false)}>＋ New Inventory</button>}
          <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
        </div>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No inventories found." searchKeys={["name","organization"]} p={p}
        actions={row=>(
          <span style={{ display:"flex",gap:4 }}>
            {canAct && <button title="Sync" onClick={()=>{ setSyncErr(null); setSyncTarget(row); }}
              style={{ background:"#eff6ff",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#3b82f6",fontWeight:700 }}>🔄 Sync</button>}
            {canAct && <button title="Edit" onClick={()=>setFormTarget(row)}
              style={{ background:"#f5f3ff",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#6366f1",fontWeight:700 }}>✏️ Edit</button>}
            {isAdmin && <button title="Delete" onClick={()=>{ setDelErr(null); setDelTarget(row); }}
              style={{ background:"#fff1f2",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#ef4444" }}>🗑️</button>}
          </span>
        )}/>
      {formTarget !== null && (
        <InventoryFormModal instId={instId} existing={formTarget||null} p={p}
          onSave={()=>{ setFormTarget(null); load(); }} onClose={()=>setFormTarget(null)}/>
      )}
      {syncTarget && <ConfirmDialog p={p} busy={syncBusy} err={syncErr} danger={false}
        title="Sync Inventory?" message={`Trigger update for all sources in "${syncTarget.name}".`}
        onConfirm={doSync} onCancel={()=>setSyncTarget(null)}/>}
      {delTarget && <ConfirmDialog p={p} busy={delBusy} err={delErr}
        title="Delete Inventory?" message={`"${delTarget.name}" and all its hosts/groups will be removed.`}
        onConfirm={doDelete} onCancel={()=>setDelTarget(null)}/>}
    </div>
  );
}

// ─── Project Form Modal ───────────────────────────────────────────────────────
function ProjectFormModal({ instId, existing, onSave, onClose, p }) {
  const AAP_ORANGE = "#f59e0b";
  const isEdit = !!existing;

  const empty = {
    name:"", description:"", organization:0, scm_type:"git",
    scm_url:"", scm_branch:"main", scm_clean:false, scm_delete_on_update:false,
    default_environment:0, credential:0, local_path:"",
  };
  const [form, setForm] = useState(existing ? {
    name:                 existing.name||"",
    description:          existing.description||"",
    organization:         existing.org_id||0,
    scm_type:             existing.scm_type||"git",
    scm_url:              existing.scm_url||"",
    scm_branch:           existing.scm_branch||"main",
    scm_clean:            existing.scm_clean||false,
    scm_delete_on_update: existing.scm_delete_on_update||false,
    default_environment:  existing.default_environment||0,
    credential:           existing.credential||0,
    local_path:           existing.local_path||"",
  } : empty);

  const [busy,       setBusy]       = useState(false);
  const [err,        setErr]        = useState(null);
  const [ees,        setEEs]        = useState([]);
  const [creds,      setCreds]      = useState([]);
  const [localPaths, setLocalPaths] = useState([]);
  const [loadingEE,  setLoadingEE]  = useState(true);
  const [loadingCr,  setLoadingCr]  = useState(true);
  const [loadingLP,  setLoadingLP]  = useState(false);

  /* Fetch execution environments + credentials once on mount */
  useEffect(() => {
    setLoadingEE(true);
    fetchAAPExecutionEnvironments(instId)
      .then(r => setEEs(r||[]))
      .catch(() => setEEs([]))
      .finally(() => setLoadingEE(false));

    setLoadingCr(true);
    fetchAAPCredentials(instId)
      .then(r => setCreds(r||[]))
      .catch(() => setCreds([]))
      .finally(() => setLoadingCr(false));
  }, [instId]);

  /* Fetch local paths when SCM type changes to Manual */
  useEffect(() => {
    if (form.scm_type !== "") return;
    setLoadingLP(true);
    fetchAAPProjectLocalPaths(instId)
      .then(r => setLocalPaths(r||[]))
      .catch(() => setLocalPaths([]))
      .finally(() => setLoadingLP(false));
  }, [form.scm_type, instId]);

  const set = k => e => setForm(f => ({
    ...f,
    [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value,
  }));

  async function submit() {
    if (!form.name) { setErr("Name is required."); return; }
    if (form.scm_type !== "" && !form.scm_url) { setErr("SCM URL is required for this SCM type."); return; }
    if (form.scm_type === "" && !form.local_path) { setErr("Playbook directory is required for Manual projects."); return; }
    setBusy(true); setErr(null);
    try {
      const payload = { ...form };
      if (!payload.default_environment) delete payload.default_environment;
      if (!payload.credential)          delete payload.credential;
      if (payload.scm_type !== "")      delete payload.local_path;
      if (isEdit) await updateAAPProject(instId, existing.id, payload);
      else        await createAAPProject(instId, payload);
      onSave();
    } catch(e) { setErr(e.message); }
    setBusy(false);
  }

  /* ─── Styling helpers ─── */
  const label = txt => (
    <div style={{ fontSize:11,fontWeight:700,color:"#64748b",marginBottom:5,
                  letterSpacing:.5,textTransform:"uppercase" }}>{txt}</div>
  );
  const fieldBox = { marginBottom:14 };
  const inputSt = {
    width:"100%", padding:"8px 11px", borderRadius:7, fontSize:13, boxSizing:"border-box",
    border:`1px solid ${p.border}`, background:p.surface, color:p.text,
  };
  const selectSt = { ...inputSt };

  const isGitLike = form.scm_type && form.scm_type !== "";  // git / svn / archive
  const isManual  = form.scm_type === "";
  // Only git-type credentials are relevant for SCM; filter if possible
  const scmCreds = creds.filter(c =>
    isGitLike
      ? /git|source.control|scm|svn|cvs|archive/i.test(c.kind||"")
      : false
  );
  const credList = scmCreds.length > 0 ? scmCreds : creds;  // fallback: show all

  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3100,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background:p.panel,border:`1px solid ${AAP_ORANGE}38`,borderRadius:16,
                    padding:"26px 28px",maxWidth:580,width:"100%",
                    boxShadow:"0 24px 70px #00000090",maxHeight:"92vh",overflowY:"auto" }}>

        {/* Header */}
        <div style={{ display:"flex",alignItems:"center",gap:12,marginBottom:22 }}>
          <div style={{ width:42,height:42,borderRadius:10,fontSize:22,display:"flex",
                        alignItems:"center",justifyContent:"center",flexShrink:0,
                        background:`${AAP_ORANGE}18`,border:`1px solid ${AAP_ORANGE}35` }}>📁</div>
          <div style={{ flex:1 }}>
            <div style={{ fontWeight:800,fontSize:16,color:AAP_ORANGE }}>
              {isEdit ? "Edit Project" : "New Project"}
            </div>
            <div style={{ fontSize:12,color:"#64748b",marginTop:2 }}>
              {isEdit ? `Editing: ${existing.name}` : "Configure a new project in Ansible Automation Platform"}
            </div>
          </div>
          <button onClick={onClose}
            style={{ background:"#ef444412",border:"1px solid #ef444430",color:"#ef4444",
                     borderRadius:7,padding:"4px 12px",cursor:"pointer",fontWeight:700,fontSize:14 }}>✕</button>
        </div>

        {/* ── Name + Description ── */}
        {[["name","Name *"],["description","Description"]].map(([k,lbl]) => (
          <div key={k} style={fieldBox}>
            {label(lbl)}
            <input value={form[k]||""} onChange={set(k)} style={inputSt}
              placeholder={k==="name"?"my-playbooks-project":""}/>
          </div>
        ))}

        {/* ── SCM Type ── */}
        <div style={fieldBox}>
          {label("SCM Type")}
          <select value={form.scm_type} onChange={set("scm_type")} style={selectSt}>
            <option value="git">Git</option>
            <option value="svn">Subversion</option>
            <option value="archive">Remote Archive</option>
            <option value="">Manual</option>
          </select>
        </div>

        {/* ── GIT / SVN / ARCHIVE fields ── */}
        {isGitLike && (<>
          <div style={fieldBox}>
            {label("SCM URL")}
            <input value={form.scm_url||""} onChange={set("scm_url")} style={inputSt}
              placeholder="https://github.com/your-org/playbooks.git"/>
          </div>
          <div style={fieldBox}>
            {label("SCM Branch / Tag / Commit")}
            <input value={form.scm_branch||""} onChange={set("scm_branch")} style={inputSt}
              placeholder="main"/>
          </div>
          {/* ── SCM Credential dropdown ── */}
          <div style={fieldBox}>
            <div style={{ display:"flex",alignItems:"center",gap:8,marginBottom:5 }}>
              {label("SCM Credential")}
              {loadingCr && <div style={{ width:12,height:12,borderRadius:"50%",
                border:"2px solid #f59e0b40",borderTopColor:AAP_ORANGE,
                animation:"spin 1s linear infinite",marginLeft:4 }}/>}
            </div>
            {!loadingCr && credList.length === 0 ? (
              <div style={{ fontSize:12,color:"#94a3b8",padding:"7px 11px",
                border:`1px dashed ${p.border}`,borderRadius:7,background:p.surface }}>
                No credentials found in AAP — add one via the Credentials tab.
              </div>
            ) : (
              <select value={form.credential||0} onChange={set("credential")} style={selectSt}
                disabled={loadingCr}>
                <option value={0}>— None (public repo) —</option>
                {credList.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name}{c.kind ? ` [${c.kind}]` : ""}
                    {c.organization ? ` · ${c.organization}` : ""}
                  </option>
                ))}
              </select>
            )}
            <div style={{ fontSize:11,color:"#64748b",marginTop:4 }}>
              Select the credential used to authenticate with the SCM repository.
            </div>
          </div>
        </>)}

        {/* ── MANUAL fields ── */}
        {isManual && (
          <div style={{ background:`${p.surface}`,border:`1px solid ${p.border}`,
                        borderLeft:`3px solid ${AAP_ORANGE}`,borderRadius:8,
                        padding:"14px 16px",marginBottom:14 }}>
            <div style={{ fontSize:12,fontWeight:600,color:AAP_ORANGE,marginBottom:12,
                          display:"flex",alignItems:"center",gap:6 }}>
              <span>📂</span> Manual Project Configuration
            </div>
            {/* Base path (read-only informational) */}
            <div style={fieldBox}>
              {label("Project Base Path")}
              <div style={{ display:"flex",alignItems:"center",gap:8,padding:"8px 11px",
                            borderRadius:7,border:`1px solid ${p.border}`,background:`${p.border}18` }}>
                <span style={{ fontFamily:"monospace",fontSize:13,color:"#94a3b8",userSelect:"all",flex:1 }}>
                  /var/lib/awx/projects
                </span>
                <span style={{ fontSize:10,color:"#64748b",background:`${p.border}40`,
                               padding:"2px 7px",borderRadius:4,whiteSpace:"nowrap" }}>
                  AAP default
                </span>
              </div>
              <div style={{ fontSize:11,color:"#64748b",marginTop:4 }}>
                Playbook directories must exist at this path on the AAP host.
              </div>
            </div>
            {/* Playbook directory dropdown */}
            <div style={{ marginBottom:0 }}>
              <div style={{ display:"flex",alignItems:"center",gap:8,marginBottom:5 }}>
                {label("Playbook Directory")}
                {loadingLP && <div style={{ width:12,height:12,borderRadius:"50%",
                  border:"2px solid #f59e0b40",borderTopColor:AAP_ORANGE,
                  animation:"spin 1s linear infinite" }}/>}
              </div>
              {!loadingLP && localPaths.length === 0 ? (
                <input value={form.local_path||""} onChange={set("local_path")} style={inputSt}
                  placeholder="my-playbooks-dir"/>
              ) : (
                <select value={form.local_path||""} onChange={set("local_path")} style={selectSt}
                  disabled={loadingLP}>
                  <option value="">— Select directory —</option>
                  {localPaths.map(d => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              )}
              <div style={{ fontSize:11,color:"#64748b",marginTop:4 }}>
                Directory name under <code style={{ fontSize:10 }}>/var/lib/awx/projects</code> on the AAP host.
              </div>
            </div>
          </div>
        )}

        {/* ── Execution Environment ── */}
        <div style={fieldBox}>
          <div style={{ display:"flex",alignItems:"center",gap:8,marginBottom:5 }}>
            {label("Execution Environment")}
            {loadingEE && <div style={{ width:12,height:12,borderRadius:"50%",
              border:"2px solid #6366f140",borderTopColor:"#6366f1",
              animation:"spin 1s linear infinite" }}/>}
          </div>
          {!loadingEE && ees.length === 0 ? (
            <div style={{ fontSize:12,color:"#94a3b8",padding:"7px 11px",
              border:`1px dashed ${p.border}`,borderRadius:7,background:p.surface }}>
              No execution environments found in AAP.
            </div>
          ) : (
            <select value={form.default_environment||0} onChange={set("default_environment")}
              style={selectSt} disabled={loadingEE}>
              <option value={0}>— Use AAP global default —</option>
              {ees.map(ee => (
                <option key={ee.id} value={ee.id}>
                  {ee.name}{ee.managed ? " [Managed]" : ""}
                  {ee.image ? ` · ${ee.image}` : ""}
                </option>
              ))}
            </select>
          )}
          <div style={{ fontSize:11,color:"#64748b",marginTop:4 }}>
            Container image used to run automation for this project.
          </div>
        </div>

        {/* ── SCM Options ── */}
        {!isManual && (
          <div style={{ display:"flex",gap:24,marginBottom:16,padding:"10px 14px",
                        background:`${p.surface}`,border:`1px solid ${p.border}`,borderRadius:8 }}>
            <label style={{ display:"flex",alignItems:"center",gap:8,cursor:"pointer" }}>
              <input type="checkbox" checked={form.scm_clean||false} onChange={set("scm_clean")}
                style={{ accentColor:AAP_ORANGE }}/>
              <div>
                <div style={{ fontSize:13,color:p.text,fontWeight:600 }}>Clean</div>
                <div style={{ fontSize:11,color:"#64748b" }}>Remove local modifications before update</div>
              </div>
            </label>
            <label style={{ display:"flex",alignItems:"center",gap:8,cursor:"pointer" }}>
              <input type="checkbox" checked={form.scm_delete_on_update||false} onChange={set("scm_delete_on_update")}
                style={{ accentColor:AAP_ORANGE }}/>
              <div>
                <div style={{ fontSize:13,color:p.text,fontWeight:600 }}>Delete on Update</div>
                <div style={{ fontSize:11,color:"#64748b" }}>Always delete and re-clone on update</div>
              </div>
            </label>
          </div>
        )}

        {/* ── Error ── */}
        {err && (
          <div style={{ fontSize:12,color:"#ef4444",background:"#ef444412",
                        padding:"9px 12px",borderRadius:7,marginBottom:14,
                        border:"1px solid #ef444428",display:"flex",alignItems:"flex-start",gap:7 }}>
            <span style={{ flexShrink:0 }}>⚠</span> {err}
          </div>
        )}

        {/* ── Actions ── */}
        <div style={{ display:"flex",gap:10,justifyContent:"flex-end",paddingTop:4 }}>
          <button onClick={onClose}
            style={{ padding:"8px 20px",borderRadius:7,border:`1px solid ${p.border}`,
                     background:"transparent",color:p.text,cursor:"pointer",fontSize:13,fontWeight:600 }}>
            Cancel
          </button>
          <button disabled={busy} onClick={submit}
            style={{ padding:"9px 24px",borderRadius:8,border:"none",background:AAP_ORANGE,
                     color:"#fff",cursor:"pointer",fontWeight:800,fontSize:13,
                     opacity:busy?0.65:1,display:"flex",alignItems:"center",gap:7 }}>
            {busy
              ? <><div style={{ width:12,height:12,borderRadius:"50%",border:"2px solid #fff6",
                  borderTopColor:"#fff",animation:"spin 1s linear infinite" }}/>{isEdit?"Saving…":"Creating…"}</>
              : isEdit ? "💾 Save Changes" : "➕ Create Project"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ProjectsTab({ instId, canAct, isAdmin, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [syncTarget, setSyncTarget] = useState(null);
  const [syncBusy, setSyncBusy] = useState(false);
  const [syncErr, setSyncErr] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState(null);
  const [formTarget, setFormTarget] = useState(null); // null=closed, false=add, obj=edit

  const load = useCallback(() => {
    setLoading(true);
    fetchAAPProjects(instId)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);

  async function doSync() {
    setSyncBusy(true); setSyncErr(null);
    try { await syncAAPProject(instId, syncTarget.id); setSyncTarget(null); }
    catch(e) { setSyncErr(e.message); }
    setSyncBusy(false);
  }
  async function doDelete() {
    setDelBusy(true); setDelErr(null);
    try { await deleteAAPProject(instId, delTarget.id); setDelTarget(null); load(); }
    catch(e) { setDelErr(e.message); }
    setDelBusy(false);
  }

  const scmBadge = t => {
    const map={git:{c:"#f59e0b",l:"Git"},svn:{c:"#3b82f6",l:"SVN"},archive:{c:"#6366f1",l:"Archive"}};
    const m = map[t] || {c:"#64748b",l:t||"Manual"};
    return <span style={{ fontSize:11,background:`${m.c}15`,color:m.c,borderRadius:6,padding:"2px 8px",fontWeight:600 }}>{m.l}</span>;
  };

  const cols = [
    { key:"name",         label:"NAME",    maxW:220 },
    { key:"organization", label:"ORG",     maxW:140 },
    { key:"scm_type",     label:"SCM",     render:r=>scmBadge(r.scm_type) },
    { key:"scm_branch",   label:"BRANCH",  render:r=><code style={{ fontSize:11,color:"#a78bfa" }}>{r.scm_branch||"—"}</code> },
    { key:"status",       label:"STATUS",  render:r=><JobStatusBadge status={r.status}/> },
    { key:"last_updated", label:"SYNCED",  render:r=><span style={{ fontSize:12 }}>{_dt(r.last_updated)}</span> },
  ];

  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>📁 Projects <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <div style={{ display:"flex",gap:8 }}>
          {canAct && <button className="btn btn-primary btn-sm" onClick={()=>setFormTarget(false)}>＋ New Project</button>}
          <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
        </div>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No projects found." searchKeys={["name","organization","scm_url","scm_branch"]} p={p}
        actions={row=>(
          <span style={{ display:"flex",gap:4 }}>
            {canAct && <button title="Sync" onClick={()=>{ setSyncErr(null); setSyncTarget(row); }}
              style={{ background:"#eff6ff",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#3b82f6",fontWeight:700 }}>🔄 Sync</button>}
            {canAct && <button title="Edit" onClick={()=>setFormTarget(row)}
              style={{ background:"#fffbeb",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#d97706",fontWeight:700 }}>✏️ Edit</button>}
            {isAdmin && <button title="Delete" onClick={()=>{ setDelErr(null); setDelTarget(row); }}
              style={{ background:"#fff1f2",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#ef4444" }}>🗑️</button>}
          </span>
        )}/>
      {formTarget !== null && (
        <ProjectFormModal instId={instId} existing={formTarget||null} p={p}
          onSave={()=>{ setFormTarget(null); load(); }} onClose={()=>setFormTarget(null)}/>
      )}
      {syncTarget && <ConfirmDialog p={p} busy={syncBusy} err={syncErr} danger={false}
        title="Sync Project?" message={`Pull latest SCM changes for "${syncTarget.name}".`}
        onConfirm={doSync} onCancel={()=>setSyncTarget(null)}/>}
      {delTarget && <ConfirmDialog p={p} busy={delBusy} err={delErr}
        title="Delete Project?" message={`"${delTarget.name}" will be permanently deleted.`}
        onConfirm={doDelete} onCancel={()=>setDelTarget(null)}/>}
    </div>
  );
}

function HostsTab({ instId, canAct, isAdmin, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState(null);
  const [togglingId, setTogglingId] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchAAPHosts(instId)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);

  async function toggle(row) {
    setTogglingId(row.id);
    try { await toggleAAPHost(instId, row.id, !row.enabled); load(); }
    catch(e) { alert(e.message); }
    setTogglingId(null);
  }
  async function doDelete() {
    setDelBusy(true); setDelErr(null);
    try { await deleteAAPHost(instId, delTarget.id); setDelTarget(null); load(); }
    catch(e) { setDelErr(e.message); }
    setDelBusy(false);
  }

  const cols = [
    { key:"name",      label:"HOSTNAME",  maxW:260, wrap:true },
    { key:"inventory", label:"INVENTORY", maxW:180 },
    { key:"enabled",   label:"ENABLED",   render:r=><HealthBadge ok={r.enabled} label={r.enabled?"Enabled":"Disabled"}/> },
    { key:"last_job",  label:"LAST JOB",  render:r=>r.last_job?<JobStatusBadge status={r.last_job}/>:<span style={{ color:"#94a3b8",fontSize:12 }}>Never</span> },
    { key:"last_failed",label:"LAST RESULT",render:r=>r.last_job?(r.last_failed?<span style={{ color:"#ef4444",fontSize:12 }}>✗ Failed</span>:<span style={{ color:"#10b981",fontSize:12 }}>✓ OK</span>):<span style={{ color:"#94a3b8",fontSize:12 }}>—</span> },
    { key:"created",   label:"ADDED",     render:r=><span style={{ fontSize:12 }}>{_age(r.created)}</span> },
  ];

  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>🖥️ Hosts <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No hosts found." searchKeys={["name","inventory"]} p={p}
        actions={row=>(
          <span style={{ display:"flex",gap:4 }}>
            {canAct && <button title={row.enabled?"Disable":"Enable"} disabled={togglingId===row.id}
              onClick={()=>toggle(row)}
              style={{ background:row.enabled?"#fff7ed":"#f0fdf4",border:"none",borderRadius:5,
                       padding:"3px 8px",cursor:"pointer",fontSize:11,
                       color:row.enabled?"#b45309":"#16a34a",fontWeight:700,opacity:togglingId===row.id?0.5:1 }}>
              {togglingId===row.id?"…":row.enabled?"⏸ Disable":"▶ Enable"}
            </button>}
            {isAdmin && <button title="Delete" onClick={()=>{ setDelErr(null); setDelTarget(row); }}
              style={{ background:"#fff1f2",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#ef4444" }}>🗑️</button>}
          </span>
        )}/>
      {delTarget && <ConfirmDialog p={p} busy={delBusy} err={delErr}
        title="Delete Host?" message={`"${delTarget.name}" will be permanently removed from its inventory.`}
        onConfirm={doDelete} onCancel={()=>setDelTarget(null)}/>}
    </div>
  );
}

// ─── Credential Form Modal ────────────────────────────────────────────────────
function CredentialFormModal({ instId, existing, onSave, onClose, p }) {
  const empty = { name:"", description:"", organization:0, credential_type:1, inputs:{} };
  const [form, setForm]     = useState(existing
    ? { name:existing.name||"", description:existing.description||"",
        organization:existing.org_id||0, credential_type:existing.credential_type_id||1,
        inputs:{} }
    : empty);
  const [inputsJson, setInputsJson] = useState("{}");
  const [busy, setBusy] = useState(false);
  const [err,  setErr]  = useState(null);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.type==="number"?Number(e.target.value):e.target.value }));
  async function submit() {
    if (!form.name) { setErr("Name is required."); return; }
    let parsedInputs = {};
    try { parsedInputs = inputsJson ? JSON.parse(inputsJson) : {}; } catch { setErr("Inputs must be valid JSON."); return; }
    const payload = { ...form, inputs: parsedInputs };
    setBusy(true); setErr(null);
    try {
      if (existing) await updateAAPCredential(instId, existing.id, payload);
      else          await createAAPCredential(instId, payload);
      onSave();
    } catch(e) { setErr(e.message); }
    setBusy(false);
  }
  const isEdit = !!existing;
  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3100,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ background:p.panel,border:"1px solid #a78bfa38",borderRadius:16,padding:28,
                    maxWidth:520,width:"100%",maxHeight:"90vh",overflowY:"auto",
                    boxShadow:"0 24px 70px #00000090" }}>
        <div style={{ display:"flex",alignItems:"center",gap:10,marginBottom:22 }}>
          <span style={{ fontSize:26 }}>🔑</span>
          <div>
            <div style={{ fontWeight:800,fontSize:16,color:"#a78bfa" }}>{isEdit?"Edit":"New"} Credential</div>
            <div style={{ fontSize:12,color:"#64748b" }}>{isEdit?`Editing: ${existing.name}`:"Create a new credential in AAP"}</div>
          </div>
          <button onClick={onClose} style={{ marginLeft:"auto",background:"#ef444412",border:"1px solid #ef444430",
                                             color:"#ef4444",borderRadius:6,padding:"3px 10px",cursor:"pointer",fontWeight:700 }}>✕</button>
        </div>
        {[["name","Name *"],["description","Description"]].map(([k,lbl])=>(
          <div key={k} style={{ marginBottom:13 }}>
            <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>{lbl.toUpperCase()}</div>
            <input value={form[k]||""} onChange={set(k)}
              style={{ width:"100%",padding:"8px 11px",borderRadius:7,border:`1px solid ${p.border}`,
                       background:p.surface,color:p.text,fontSize:13,boxSizing:"border-box" }}/>
          </div>
        ))}
        <div style={{ marginBottom:13 }}>
          <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>CREDENTIAL TYPE ID</div>
          <input type="number" min={1} value={form.credential_type||1} onChange={set("credential_type")}
            style={{ width:"100%",padding:"8px 11px",borderRadius:7,border:`1px solid ${p.border}`,
                     background:p.surface,color:p.text,fontSize:13,boxSizing:"border-box" }}/>
          <div style={{ fontSize:11,color:"#94a3b8",marginTop:3 }}>1=Machine, 2=Source Control, 3=Vault, 4=Network, 5=AWS…</div>
        </div>
        {!isEdit && (
          <div style={{ marginBottom:18 }}>
            <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>INPUTS (JSON)</div>
            <textarea value={inputsJson} onChange={e=>setInputsJson(e.target.value)} rows={5}
              placeholder={'{\n  "username": "admin",\n  "password": "secret"\n}'}
              style={{ width:"100%",padding:10,fontSize:12,fontFamily:"monospace",
                       background:"#0f172a",color:"#e2e8f0",border:"1px solid #334155",
                       borderRadius:8,resize:"vertical",outline:"none",boxSizing:"border-box" }}/>
          </div>
        )}
        {err && <div style={{ fontSize:12,color:"#ef4444",background:"#ef444412",padding:"8px 12px",borderRadius:6,marginBottom:12 }}>{err}</div>}
        <div style={{ display:"flex",gap:10,justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{ padding:"8px 18px",borderRadius:7,border:`1px solid ${p.border}`,background:"transparent",color:p.text,cursor:"pointer",fontSize:13 }}>Cancel</button>
          <button disabled={busy} onClick={submit}
            style={{ padding:"9px 22px",borderRadius:8,border:"none",background:"#7c3aed",color:"#fff",
                     cursor:"pointer",fontWeight:800,fontSize:13,opacity:busy?0.6:1 }}>
            {busy?(isEdit?"Saving…":"Creating…"):(isEdit?"💾 Save Changes":"➕ Create Credential")}
          </button>
        </div>
      </div>
    </div>
  );
}

function CredentialsTab({ instId, isAdmin, canAct, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState(null);
  const [formTarget, setFormTarget] = useState(null); // null=closed, false=add, obj=edit

  const load = useCallback(() => {
    setLoading(true);
    fetchAAPCredentials(instId)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);

  async function doDelete() {
    setDelBusy(true); setDelErr(null);
    try { await deleteAAPCredential(instId, delTarget.id); setDelTarget(null); load(); }
    catch(e) { setDelErr(e.message); }
    setDelBusy(false);
  }

  const cols = [
    { key:"name",         label:"NAME",     maxW:220 },
    { key:"kind",         label:"TYPE",     render:r=><span style={{ fontSize:11,background:"#a78bfa15",color:"#a78bfa",borderRadius:6,padding:"2px 8px",fontWeight:600 }}>{r.kind}</span> },
    { key:"organization", label:"ORG",      maxW:160 },
    { key:"created",      label:"CREATED",  render:r=><span style={{ fontSize:12 }}>{_age(r.created)}</span> },
  ];

  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>🔑 Credentials <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <div style={{ display:"flex",gap:8 }}>
          {canAct && <button className="btn btn-primary btn-sm" onClick={()=>setFormTarget(false)}>＋ New Credential</button>}
          <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
        </div>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No credentials found." searchKeys={["name","kind","organization"]} p={p}
        actions={(isAdmin||canAct) ? (row=>(
          <span style={{ display:"flex",gap:4 }}>
            {canAct && <button title="Edit" onClick={()=>setFormTarget(row)}
              style={{ background:"#f5f3ff",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#7c3aed",fontWeight:700 }}>✏️ Edit</button>}
            {isAdmin && <button title="Delete" onClick={()=>{ setDelErr(null); setDelTarget(row); }}
              style={{ background:"#fff1f2",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#ef4444" }}>🗑️</button>}
          </span>
        )) : null}/>
      {formTarget !== null && (
        <CredentialFormModal instId={instId} existing={formTarget||null} p={p}
          onSave={()=>{ setFormTarget(null); load(); }} onClose={()=>setFormTarget(null)}/>
      )}
      {delTarget && <ConfirmDialog p={p} busy={delBusy} err={delErr}
        title="Delete Credential?" message={`"${delTarget.name}" will be permanently deleted.`}
        onConfirm={doDelete} onCancel={()=>setDelTarget(null)}/>}
    </div>
  );
}

function UsersTab({ instId, isAdmin, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [delTarget, setDelTarget] = useState(null);
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchAAPUsers(instId)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);

  async function doDelete() {
    setDelBusy(true); setDelErr(null);
    try { await deleteAAPUser(instId, delTarget.id); setDelTarget(null); load(); }
    catch(e) { setDelErr(e.message); }
    setDelBusy(false);
  }

  const cols = [
    { key:"username",     label:"USERNAME",  maxW:180 },
    { key:"first_name",   label:"FIRST",     maxW:120 },
    { key:"last_name",    label:"LAST",      maxW:120 },
    { key:"email",        label:"EMAIL",     maxW:220 },
    { key:"is_superuser", label:"ROLE",      render:r=>(
        <span style={{ fontSize:11,fontWeight:700,padding:"2px 8px",borderRadius:99,
                       color:r.is_superuser?"#dc2626":"#6366f1",
                       background:r.is_superuser?"#dc262615":"#6366f115" }}>
          {r.is_superuser ? "🔴 Superuser" : r.is_system_auditor ? "🟡 Auditor" : "👤 Normal"}
        </span>
      )},
    { key:"last_login",  label:"LAST LOGIN", render:r=><span style={{ fontSize:12 }}>{_dt(r.last_login)}</span> },
  ];

  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>👥 Users <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <div style={{ display:"flex",gap:8 }}>
          {isAdmin && <button className="btn btn-primary btn-sm" onClick={()=>setShowCreate(true)}>＋ Create User</button>}
          <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
        </div>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No users found." searchKeys={["username","email","first_name","last_name"]} p={p}
        actions={isAdmin ? (row=>(
          <button title="Delete" onClick={()=>{ setDelErr(null); setDelTarget(row); }}
            style={{ background:"#fff1f2",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#ef4444" }}>🗑️</button>
        )) : null}/>
      {showCreate && <UserFormModal instId={instId} p={p} busy={createBusy} setBusy={setCreateBusy}
        onDone={()=>{ setShowCreate(false); load(); }} onClose={()=>setShowCreate(false)}/>}
      {delTarget && <ConfirmDialog p={p} busy={delBusy} err={delErr}
        title="Delete AAP User?" message={`"${delTarget.username}" will be permanently deleted.`}
        onConfirm={doDelete} onCancel={()=>setDelTarget(null)}/>}
    </div>
  );
}

function TeamsTab({ instId, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const load = useCallback(() => {
    setLoading(true);
    fetchAAPTeams(instId)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);
  const cols = [
    { key:"name",         label:"NAME",    maxW:220 },
    { key:"organization", label:"ORG",     maxW:180 },
    { key:"description",  label:"DESCRIPTION", maxW:300, wrap:true },
    { key:"created",      label:"CREATED", render:r=><span style={{ fontSize:12 }}>{_age(r.created)}</span> },
  ];
  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>🏷️ Teams <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No teams found." searchKeys={["name","organization"]} p={p}/>
    </div>
  );
}

function OrganizationsTab({ instId, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const load = useCallback(() => {
    setLoading(true);
    fetchAAPOrganizations(instId)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);
  const cols = [
    { key:"name",        label:"NAME",        maxW:220 },
    { key:"description", label:"DESCRIPTION", maxW:360, wrap:true },
    { key:"created",     label:"CREATED",     render:r=><span style={{ fontSize:12 }}>{_age(r.created)}</span> },
  ];
  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>🏢 Organizations <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No organizations found." searchKeys={["name"]} p={p}/>
    </div>
  );
}

function SchedulesTab({ instId, canAct, isAdmin, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [togglingId, setTogglingId] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    fetchAAPSchedules(instId)
      .then(d=>{ setRows(d); setErr(null); })
      .catch(e=>setErr(e.message))
      .finally(()=>setLoading(false));
  }, [instId]);
  useEffect(()=>{ load(); }, [load]);

  async function toggleSched(row) {
    setTogglingId(row.id);
    try { await toggleAAPSchedule(instId, row.id, !row.enabled); load(); }
    catch(e) { alert(e.message); }
    setTogglingId(null);
  }
  async function doDelete() {
    setDelBusy(true); setDelErr(null);
    try { await deleteAAPSchedule(instId, delTarget.id); setDelTarget(null); load(); }
    catch(e) { setDelErr(e.message); }
    setDelBusy(false);
  }

  const cols = [
    { key:"name",     label:"NAME",     maxW:220 },
    { key:"template", label:"TEMPLATE", maxW:200 },
    { key:"enabled",  label:"STATE",    render:r=><HealthBadge ok={r.enabled} label={r.enabled?"Enabled":"Disabled"}/> },
    { key:"timezone", label:"TIMEZONE", maxW:120 },
    { key:"next_run", label:"NEXT RUN", render:r=><span style={{ fontSize:12 }}>{_dt(r.next_run)}</span> },
  ];

  return (
    <div style={{ padding:"20px 24px" }}>
      <div style={{ display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16 }}>
        <h3 style={{ margin:0,fontSize:16,fontWeight:700,color:p.text }}>🕐 Schedules <span style={{ fontSize:13,fontWeight:400,color:p.textMute }}>({rows.length})</span></h3>
        <button className="btn btn-ghost btn-sm" onClick={load}>↺ Refresh</button>
      </div>
      <ResourceTable columns={cols} rows={rows} loading={loading} err={err} onRetry={load}
        emptyMsg="No schedules found." searchKeys={["name","template"]} p={p}
        actions={row=>(
          <span style={{ display:"flex",gap:4 }}>
            {canAct && <button title={row.enabled?"Disable":"Enable"} disabled={togglingId===row.id}
              onClick={()=>toggleSched(row)}
              style={{ background:row.enabled?"#fff7ed":"#f0fdf4",border:"none",borderRadius:5,
                       padding:"3px 8px",cursor:"pointer",fontSize:11,
                       color:row.enabled?"#b45309":"#16a34a",fontWeight:700,opacity:togglingId===row.id?0.5:1 }}>
              {togglingId===row.id?"…":row.enabled?"⏸ Disable":"▶ Enable"}
            </button>}
            {isAdmin && <button title="Delete" onClick={()=>{ setDelErr(null); setDelTarget(row); }}
              style={{ background:"#fff1f2",border:"none",borderRadius:5,padding:"3px 8px",cursor:"pointer",fontSize:11,color:"#ef4444" }}>🗑️</button>}
          </span>
        )}/>
      {delTarget && <ConfirmDialog p={p} busy={delBusy} err={delErr}
        title="Delete Schedule?" message={`"${delTarget.name}" will be permanently removed.`}
        onConfirm={doDelete} onCancel={()=>setDelTarget(null)}/>}
    </div>
  );
}

// ─── Workflow Form Modal ─────────────────────────────────────────────────────
function WorkflowFormModal({ instId, existing, onSave, onClose, p }) {
  const empty = { name:"", description:"", organization:0, scm_branch:"", extra_vars:"", ask_limit_on_launch:false };
  const [form, setForm] = useState(existing
    ? { name:existing.name||"", description:existing.description||"",
        organization:existing.organization||0,
        scm_branch:existing.scm_branch||"",
        extra_vars:existing.extra_vars||"",
        ask_limit_on_launch:existing.ask_limit_on_launch||false }
    : empty);
  const [busy, setBusy] = useState(false);
  const [err,  setErr]  = useState(null);
  const set = k => e => setForm(f => ({ ...f, [k]: e.target.type==="checkbox"?e.target.checked:e.target.value }));
  async function submit() {
    if (!form.name) { setErr("Name is required."); return; }
    setBusy(true); setErr(null);
    try {
      if (existing) await updateAAPWorkflow(instId, existing.id, form);
      else          await createAAPWorkflow(instId, form);
      onSave();
    } catch(e) { setErr(e.message); }
    setBusy(false);
  }
  const isEdit = !!existing;
  return (
    <div style={{ position:"fixed",inset:0,background:"#00000095",zIndex:3100,
                  display:"flex",alignItems:"center",justifyContent:"center",padding:16 }}
         onClick={e=>e.target===e.currentTarget&&onClose()}>
      <div style={{ background:p.panel,border:"1px solid #6366f138",borderRadius:16,padding:28,
                    maxWidth:540,width:"100%",boxShadow:"0 24px 70px #00000090" }}>
        <div style={{ display:"flex",alignItems:"center",gap:10,marginBottom:22 }}>
          <span style={{ fontSize:26 }}>🔀</span>
          <div>
            <div style={{ fontWeight:800,fontSize:16,color:"#6366f1" }}>{isEdit?"Edit":"New"} Workflow Template</div>
            <div style={{ fontSize:12,color:"#64748b" }}>{isEdit?`Editing: ${existing.name}`:"Create a new workflow job template in AAP"}</div>
          </div>
          <button onClick={onClose} style={{ marginLeft:"auto",background:"#ef444412",border:"1px solid #ef444430",
                                             color:"#ef4444",borderRadius:6,padding:"3px 10px",cursor:"pointer",fontWeight:700 }}>✕</button>
        </div>
        {[["name","Name *"],["description","Description"],["scm_branch","SCM Branch"]].map(([k,lbl])=>(
          <div key={k} style={{ marginBottom:13 }}>
            <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>{lbl.toUpperCase()}</div>
            <input value={form[k]||""} onChange={set(k)}
              style={{ width:"100%",padding:"8px 11px",borderRadius:7,border:`1px solid ${p.border}`,
                       background:p.surface,color:p.text,fontSize:13,boxSizing:"border-box" }}/>
          </div>
        ))}
        <div style={{ marginBottom:13 }}>
          <div style={{ fontSize:11,fontWeight:700,color:"#475569",marginBottom:4,letterSpacing:.3 }}>EXTRA VARIABLES (YAML/JSON)</div>
          <textarea rows={4} value={form.extra_vars||""} onChange={set("extra_vars")} placeholder="---&#10;key: value"
            style={{ width:"100%",padding:"8px 11px",borderRadius:7,border:`1px solid ${p.border}`,
                     background:p.surface,color:p.text,fontSize:12,fontFamily:"monospace",
                     resize:"vertical",boxSizing:"border-box" }}/>
        </div>
        <div style={{ marginBottom:18 }}>
          <label style={{ display:"flex",alignItems:"center",gap:7,cursor:"pointer" }}>
            <input type="checkbox" checked={form.ask_limit_on_launch||false} onChange={set("ask_limit_on_launch")}/>
            <span style={{ fontSize:13,color:p.text }}>Ask for limit on launch</span>
          </label>
        </div>
        {err && <div style={{ fontSize:12,color:"#ef4444",background:"#ef444412",padding:"8px 12px",borderRadius:6,marginBottom:12 }}>{err}</div>}
        <div style={{ display:"flex",gap:10,justifyContent:"flex-end" }}>
          <button onClick={onClose} style={{ padding:"8px 18px",borderRadius:7,border:`1px solid ${p.border}`,background:"transparent",color:p.text,cursor:"pointer",fontSize:13 }}>Cancel</button>
          <button disabled={busy} onClick={submit}
            style={{ padding:"9px 22px",borderRadius:8,border:"none",background:"#6366f1",color:"#fff",
                     cursor:"pointer",fontWeight:800,fontSize:13,opacity:busy?0.6:1 }}>
            {busy?(isEdit?"Saving\u2026":"Creating\u2026"):(isEdit?"\uD83D\uDCBE Save Changes":"\u2795 Create Workflow")}
          </button>
        </div>
      </div>
    </div>
  );
}

function WorkflowsTab({ instId, canAct, isAdmin, p }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [formTarget, setFormTarget] = useState(null);
  const [launchTarget, setLaunchTarget] = useState(null);
  const [launchBusy, setLaunchBusy] = useState(false);
  const [launchErr, setLaunchErr] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState(null);
  const [q, setQ] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setErr(null);
    try { setRows(await fetchAAPWorkflows(instId)); }
    catch(e) { setErr(e.message); }
    setLoading(false);
  }, [instId]);
  useEffect(() => { load(); }, [load]);

  const filtered = rows.filter(r =>
    !q || r.name?.toLowerCase().includes(q.toLowerCase()) || r.description?.toLowerCase().includes(q.toLowerCase())
  );

  async function doLaunch() {
    if (!launchTarget) return;
    setLaunchBusy(true); setLaunchErr(null);
    try {
      await launchAAPWorkflow(instId, launchTarget.id);
      setLaunchTarget(null); load();
    } catch(e) { setLaunchErr(e.message); }
    setLaunchBusy(false);
  }

  async function doDelete() {
    if (!delTarget) return;
    setDelBusy(true); setDelErr(null);
    try {
      await deleteAAPWorkflow(instId, delTarget.id);
      setDelTarget(null); load();
    } catch(e) { setDelErr(e.message); }
    setDelBusy(false);
  }

  if (loading) return <Spinner/>;
  if (err) return <ErrMsg msg={err} onRetry={load}/>;

  return (
    <div style={{ padding:20 }}>
      {formTarget !== null && (
        <WorkflowFormModal instId={instId} existing={formTarget||null}
          onSave={()=>{ setFormTarget(null); load(); }} onClose={()=>setFormTarget(null)} p={p}/>
      )}
      {launchTarget && <ConfirmDialog p={p} busy={launchBusy} err={launchErr} danger={false}
        title="Launch Workflow?" message={`Launch workflow "${launchTarget.name}"?`}
        onConfirm={doLaunch} onCancel={()=>setLaunchTarget(null)}/>}
      {delTarget && <ConfirmDialog p={p} busy={delBusy} err={delErr}
        title="Delete Workflow?" message={`"${delTarget.name}" will be permanently removed.`}
        onConfirm={doDelete} onCancel={()=>setDelTarget(null)}/>}
      <div style={{ display:"flex",alignItems:"center",gap:10,marginBottom:16,flexWrap:"wrap" }}>
        <span style={{ fontWeight:700,fontSize:15,color:"#6366f1",flex:1 }}>🔀 Workflow Job Templates ({rows.length})</span>
        <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search workflows\u2026"
          style={{ padding:"6px 10px",borderRadius:7,border:`1px solid ${p.border}`,background:p.surface,color:p.text,fontSize:12,width:200 }}/>
        {canAct && (
          <button onClick={()=>setFormTarget(false)}
            style={{ padding:"7px 16px",borderRadius:8,border:"none",background:"#6366f1",color:"#fff",
                     cursor:"pointer",fontWeight:700,fontSize:12 }}>
            \u2795 New Workflow
          </button>
        )}
      </div>
      {filtered.length===0
        ? <div style={{ textAlign:"center",padding:40,color:p.textMute,fontSize:13 }}>No workflow templates found</div>
        : <div style={{ overflowX:"auto" }}>
            <table style={{ width:"100%",borderCollapse:"collapse",fontSize:13 }}>
              <thead>
                <tr style={{ background:p.panel }}>
                  {["Name","Status","Created","Last Updated","Actions"].map(h=>(
                    <th key={h} style={{ padding:"10px 12px",textAlign:"left",fontWeight:700,fontSize:11,
                                         color:"#475569",borderBottom:`1px solid ${p.border}`,textTransform:"uppercase",letterSpacing:.4 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((wf,i)=>(
                  <tr key={wf.id} style={{ borderBottom:`1px solid ${p.border}`,background:i%2===0?"transparent":p.panel+"40" }}>
                    <td style={{ padding:"10px 12px" }}>
                      <div style={{ fontWeight:700,color:"#6366f1" }}>{wf.name}</div>
                      {wf.description && <div style={{ fontSize:11,color:"#64748b",marginTop:2 }}>{wf.description}</div>}
                    </td>
                    <td style={{ padding:"10px 12px" }}>
                      <span style={{ fontSize:11,padding:"2px 8px",borderRadius:20,fontWeight:600,
                        background:wf.status==="successful"?"#10b98118":wf.status==="failed"?"#ef444418":"#94a3b818",
                        color:wf.status==="successful"?"#10b981":wf.status==="failed"?"#ef4444":"#94a3b8" }}>
                        {wf.status||"\u2014"}
                      </span>
                    </td>
                    <td style={{ padding:"10px 12px",fontSize:12,color:"#64748b" }}>{_dt(wf.created)}</td>
                    <td style={{ padding:"10px 12px",fontSize:12,color:"#64748b" }}>{_dt(wf.modified)}</td>
                    <td style={{ padding:"10px 12px" }}>
                      <div style={{ display:"flex",gap:6,flexWrap:"wrap" }}>
                        {canAct && (
                          <button onClick={()=>setLaunchTarget(wf)}
                            style={{ padding:"4px 10px",borderRadius:6,border:"none",background:"#10b98118",
                                     color:"#10b981",cursor:"pointer",fontSize:11,fontWeight:600 }}>🚀 Launch</button>
                        )}
                        {canAct && (
                          <button onClick={()=>setFormTarget(wf)}
                            style={{ padding:"4px 10px",borderRadius:6,border:"none",background:"#6366f118",
                                     color:"#6366f1",cursor:"pointer",fontSize:11,fontWeight:600 }}>✏️ Edit</button>
                        )}
                        {isAdmin && (
                          <button onClick={()=>setDelTarget(wf)}
                            style={{ padding:"4px 10px",borderRadius:6,border:"none",background:"#ef444418",
                                     color:"#ef4444",cursor:"pointer",fontSize:11,fontWeight:600 }}>🗑️ Delete</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      }
    </div>
  );
}

// ─── Instance detail view (tabbed) ────────────────────────────────────────────
function InstanceDetail({ inst, onBack, currentUser, p }) {
  const [tab, setTab] = useState("dashboard");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const role = currentUser?.role || "viewer";
  const canAct = role === "admin" || role === "operator";
  const isAdmin = role === "admin";

  const TABS = [
    { id:"dashboard",     label:"Dashboard",      icon:"📊", roles:["admin","operator","viewer"] },
    { id:"jobs",          label:"Jobs",            icon:"🔄", roles:["admin","operator","viewer"] },
    { id:"templates",     label:"Job Templates",   icon:"⚙️", roles:["admin","operator","viewer"] },
    { id:"inventories",   label:"Inventories",     icon:"📦", roles:["admin","operator","viewer"] },
    { id:"projects",      label:"Projects",        icon:"📁", roles:["admin","operator","viewer"] },
    { id:"hosts",         label:"Hosts",           icon:"🖥️", roles:["admin","operator","viewer"] },
    { id:"credentials",   label:"Credentials",     icon:"🔑", roles:["admin","operator","viewer"] },
    { id:"organizations", label:"Organizations",   icon:"🏢", roles:["admin","operator","viewer"] },
    { id:"users",         label:"Users",           icon:"👥", roles:["admin","operator","viewer"] },
    { id:"teams",         label:"Teams",           icon:"🏷️", roles:["admin","operator","viewer"] },
    { id:"schedules",     label:"Schedules",       icon:"🕐", roles:["admin","operator","viewer"] },
    { id:"workflows",     label:"Workflows",       icon:"🔀", roles:["admin","operator","viewer"] },
  ].filter(t => t.roles.includes(role));

  async function runTest() {
    setTesting(true); setTestResult(null);
    try { const r = await testAAPInstance(inst.id); setTestResult(r); }
    catch(e) { setTestResult({ reachable:false, message:e.message }); }
    setTesting(false);
  }

  const envColor = inst.env==="PROD"?"#ef4444":inst.env==="PROD1"?"#f97316":inst.env==="STAGING"?"#f59e0b":"#6366f1";

  return (
    <div style={{ display:"flex",flexDirection:"column",height:"100%" }}>
      {/* Instance header */}
      <div style={{ padding:"16px 24px",background:`linear-gradient(135deg,#1a0000,#2d0808)`,
                    borderBottom:"2px solid #ee000030",flexShrink:0 }}>
        <div style={{ display:"flex",alignItems:"center",gap:12,flexWrap:"wrap" }}>
          <button onClick={onBack}
            style={{ background:"#ffffff15",border:"1px solid #ffffff25",color:"#fff",
                     borderRadius:8,padding:"5px 12px",cursor:"pointer",fontSize:12,fontWeight:600 }}>
            ← Back
          </button>
          <img src="https://logo.clearbit.com/redhat.com" alt="AAP" width={28} height={28}
               style={{ borderRadius:6,flexShrink:0 }} onError={e=>{e.target.style.display="none";}}/>
          <div style={{ flex:1,minWidth:0 }}>
            <div style={{ display:"flex",alignItems:"center",gap:8,flexWrap:"wrap" }}>
              <span style={{ fontWeight:800,fontSize:18,color:"#fff" }}>{inst.name}</span>
              <span style={{ fontSize:11,fontWeight:700,padding:"2px 10px",borderRadius:99,
                             color:"#fff",background:envColor }}>{inst.env}</span>
              <span style={{ fontSize:11,fontWeight:600,padding:"2px 10px",borderRadius:99,
                             color:inst.status==="ok"?"#10b981":"#f59e0b",
                             background:inst.status==="ok"?"#10b98120":"#f59e0b20" }}>
                ● {inst.status||"unknown"}
              </span>
            </div>
            <div style={{ fontSize:12,color:"#94a3b8",marginTop:2 }}>{inst.url}</div>
          </div>
          {/* URL redirect button */}
          <a href={inst.url} target="_blank" rel="noopener noreferrer"
             style={{ display:"inline-flex",alignItems:"center",gap:6,padding:"7px 16px",
                      borderRadius:8,background:"#ee0000",color:"#fff",fontSize:12,fontWeight:700,
                      textDecoration:"none",border:"none",cursor:"pointer",flexShrink:0 }}>
            🔗 Open AAP UI
          </a>
          <button onClick={runTest} disabled={testing}
            style={{ padding:"7px 14px",borderRadius:8,border:"1px solid #ffffff25",
                     background:"#ffffff12",color:"#fff",cursor:"pointer",fontSize:12,fontWeight:600,
                     opacity:testing?0.6:1,flexShrink:0 }}>
            {testing ? "Testing…" : "🔌 Test"}
          </button>
        </div>
        {testResult && (
          <div style={{ marginTop:10,padding:"8px 14px",borderRadius:8,fontSize:12,
                        background:testResult.reachable?"#10b98120":"#ef444420",
                        color:testResult.reachable?"#10b981":"#ef4444",
                        border:`1px solid ${testResult.reachable?"#10b98130":"#ef444430"}` }}>
            {testResult.reachable ? `✅ ${testResult.message}` : `❌ ${testResult.message}`}
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div style={{ display:"flex",gap:2,padding:"10px 20px 0",background:p.panel,
                    borderBottom:`1px solid ${p.border}`,flexShrink:0,overflowX:"auto" }}>
        {TABS.map(t=>(
          <button key={t.id} onClick={()=>setTab(t.id)}
            style={{ padding:"8px 14px",borderRadius:"8px 8px 0 0",border:"none",cursor:"pointer",
                     fontSize:12,fontWeight:tab===t.id?700:500,whiteSpace:"nowrap",
                     background:tab===t.id?p.bg:"transparent",
                     color:tab===t.id?"#ee0000":p.textMute,
                     borderBottom:tab===t.id?"2px solid #ee0000":"2px solid transparent" }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex:1,overflowY:"auto",background:p.bg }}>
        {tab==="dashboard"     && <DashboardTab     instId={inst.id} p={p}/>}
        {tab==="jobs"          && <JobsTab          instId={inst.id} canAct={canAct} isAdmin={isAdmin} p={p}/>}
        {tab==="templates"     && <TemplatesTab     instId={inst.id} canAct={canAct} isAdmin={isAdmin} p={p}/>}
        {tab==="inventories"   && <InventoriesTab   instId={inst.id} canAct={canAct} isAdmin={isAdmin} p={p}/>}
        {tab==="projects"      && <ProjectsTab      instId={inst.id} canAct={canAct} isAdmin={isAdmin} p={p}/>}
        {tab==="hosts"         && <HostsTab         instId={inst.id} canAct={canAct} isAdmin={isAdmin} p={p}/>}
        {tab==="credentials"   && <CredentialsTab   instId={inst.id} isAdmin={isAdmin} canAct={canAct} p={p}/>}
        {tab==="organizations" && <OrganizationsTab instId={inst.id} p={p}/>}
        {tab==="users"         && <UsersTab         instId={inst.id} isAdmin={isAdmin} p={p}/>}
        {tab==="teams"         && <TeamsTab         instId={inst.id} p={p}/>}
        {tab==="schedules"     && <SchedulesTab     instId={inst.id} canAct={canAct} isAdmin={isAdmin} p={p}/>}
        {tab==="workflows"     && <WorkflowsTab     instId={inst.id} canAct={canAct} isAdmin={isAdmin} p={p}/>}
      </div>
    </div>
  );
}

// ─── Instance tile ────────────────────────────────────────────────────────────
function InstanceTile({ inst, onSelect, onEdit, onDelete, isAdmin, p }) {
  const envColors = {
    PROD:    { bg:"#fef2f2", border:"#fee2e2", badge:"#ef4444" },
    PROD1:   { bg:"#fff7ed", border:"#fed7aa", badge:"#f97316" },
    STAGING: { bg:"#fffbeb", border:"#fde68a", badge:"#f59e0b" },
    DR:      { bg:"#f0f9ff", border:"#bae6fd", badge:"#0891b2" },
    DEV:     { bg:"#f5f3ff", border:"#ddd6fe", badge:"#7c3aed" },
    TEST:    { bg:"#f0fdf4", border:"#bbf7d0", badge:"#16a34a" },
  };
  const ec = envColors[inst.env] || { bg:"#f8fafc", border:"#e2e8f0", badge:"#64748b" };
  return (
    <div onClick={()=>onSelect(inst)}
      style={{ background:p.panel,border:`1px solid ${p.border}`,borderRadius:14,padding:"20px 22px",
               cursor:"pointer",transition:"all .18s",position:"relative",overflow:"hidden",
               boxShadow:"0 2px 8px #0000000a" }}
      onMouseEnter={e=>{ e.currentTarget.style.transform="translateY(-2px)"; e.currentTarget.style.boxShadow="0 8px 24px #00000015"; }}
      onMouseLeave={e=>{ e.currentTarget.style.transform=""; e.currentTarget.style.boxShadow="0 2px 8px #0000000a"; }}>

      {/* Env accent strip */}
      <div style={{ position:"absolute",top:0,left:0,right:0,height:4,background:ec.badge,borderRadius:"14px 14px 0 0" }}/>

      <div style={{ display:"flex",alignItems:"flex-start",gap:12,marginTop:4 }}>
        <img src="https://logo.clearbit.com/redhat.com" alt="AAP" width={40} height={40}
             style={{ borderRadius:10,flexShrink:0,border:`1px solid ${p.border}` }}
             onError={e=>{ e.target.outerHTML=`<div style="width:40px;height:40px;border-radius:10px;background:#ee000020;display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0">🤖</div>`; }}/>
        <div style={{ flex:1,minWidth:0 }}>
          <div style={{ display:"flex",alignItems:"center",gap:6,flexWrap:"wrap" }}>
            <span style={{ fontWeight:800,fontSize:15,color:p.text,wordBreak:"break-all" }}>{inst.name}</span>
            <span style={{ fontSize:10,fontWeight:800,padding:"2px 9px",borderRadius:99,
                           color:"#fff",background:ec.badge }}>{inst.env}</span>
          </div>
          <div style={{ fontSize:11,color:p.textMute,marginTop:3,wordBreak:"break-all" }}>{inst.url}</div>
          {inst.description && <div style={{ fontSize:11,color:p.textMute,marginTop:2 }}>{inst.description}</div>}
          <div style={{ display:"flex",alignItems:"center",gap:8,marginTop:8,flexWrap:"wrap" }}>
            <span style={{ display:"inline-flex",alignItems:"center",gap:4,fontSize:11,fontWeight:600,
                           color:inst.status==="ok"?"#10b981":"#f59e0b",
                           background:inst.status==="ok"?"#10b98115":"#f59e0b15",
                           padding:"3px 10px",borderRadius:99 }}>
              <span style={{ width:5,height:5,borderRadius:"50%",
                             background:inst.status==="ok"?"#10b981":"#f59e0b" }}/>
              {inst.status||"unknown"}
            </span>
            {/* URL redirect */}
            <a href={inst.url} target="_blank" rel="noopener noreferrer"
               onClick={e=>e.stopPropagation()}
               style={{ display:"inline-flex",alignItems:"center",gap:4,fontSize:11,padding:"3px 10px",
                        borderRadius:99,background:"#ee000015",color:"#ee0000",fontWeight:700,
                        textDecoration:"none",border:"1px solid #ee000020" }}>
              🔗 Open UI
            </a>
          </div>
        </div>
        {isAdmin && (
          <div style={{ display:"flex",flexDirection:"column",gap:4 }} onClick={e=>e.stopPropagation()}>
            <button title="Edit" onClick={()=>onEdit(inst)}
              style={{ background:"#f1f5f9",border:"none",borderRadius:6,padding:"5px 8px",cursor:"pointer",fontSize:12,color:"#475569" }}>✏️</button>
            <button title="Delete" onClick={()=>onDelete(inst)}
              style={{ background:"#fff1f2",border:"none",borderRadius:6,padding:"5px 8px",cursor:"pointer",fontSize:12,color:"#ef4444" }}>🗑️</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Add tile ─────────────────────────────────────────────────────────────────
function AddTile({ onClick, p }) {
  return (
    <div onClick={onClick}
      style={{ background:p.panel,border:`2px dashed ${p.border}`,borderRadius:14,padding:"20px 22px",
               cursor:"pointer",display:"flex",flexDirection:"column",alignItems:"center",
               justifyContent:"center",gap:10,minHeight:120,
               transition:"all .18s",color:p.textMute }}
      onMouseEnter={e=>{ e.currentTarget.style.borderColor="#ee0000"; e.currentTarget.style.color="#ee0000"; }}
      onMouseLeave={e=>{ e.currentTarget.style.borderColor=p.border; e.currentTarget.style.color=p.textMute; }}>
      <div style={{ fontSize:32 }}>＋</div>
      <div style={{ fontSize:13,fontWeight:700 }}>Add AAP Instance</div>
      <div style={{ fontSize:11,color:"inherit",opacity:0.7 }}>Connect PROD, PROD1, Staging…</div>
    </div>
  );
}

// ─── Main AnsiblePage ─────────────────────────────────────────────────────────
export default function AnsiblePage({ currentUser, p }) {
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [selInst, setSelInst] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editInst, setEditInst] = useState(null);
  const [delTarget, setDelTarget] = useState(null);
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState(null);

  const role = currentUser?.role || "viewer";
  const isAdmin = role === "admin";

  const load = useCallback(() => {
    setLoading(true);
    fetchAAPInstances()
      .then(d => { setInstances(d); setErr(null); })
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  // If an instance is selected, show its detail view
  if (selInst) {
    const fresh = instances.find(i => i.id === selInst.id) || selInst;
    return <InstanceDetail inst={fresh} onBack={()=>setSelInst(null)} currentUser={currentUser} p={p}/>;
  }

  async function doDelete() {
    setDelBusy(true); setDelErr(null);
    try { await deleteAAPInstance(delTarget.id); setDelTarget(null); load(); }
    catch(e) { setDelErr(e.message); }
    setDelBusy(false);
  }

  return (
    <div style={{ padding:"24px 28px",minHeight:"100%",background:p.bg }}>
      {/* Page header */}
      <div style={{ display:"flex",alignItems:"center",gap:16,marginBottom:28,flexWrap:"wrap" }}>
        <div style={{ width:52,height:52,borderRadius:14,background:"linear-gradient(135deg,#ee0000,#b91c1c)",
                       display:"flex",alignItems:"center",justifyContent:"center",fontSize:28,
                       boxShadow:"0 4px 16px #ee000040",flexShrink:0 }}>
          🤖
        </div>
        <div style={{ flex:1,minWidth:0 }}>
          <h1 style={{ margin:0,fontSize:22,fontWeight:800,color:p.text }}>
            Ansible Automation Platform
          </h1>
          <p style={{ margin:"4px 0 0",fontSize:13,color:p.textMute }}>
            Manage AAP instances — jobs, templates, inventories, projects, hosts & more
          </p>
        </div>
        {isAdmin && (
          <button onClick={()=>{ setEditInst(null); setShowForm(true); }}
            style={{ padding:"9px 20px",borderRadius:9,border:"none",
                     background:"linear-gradient(135deg,#ee0000,#b91c1c)",color:"#fff",
                     cursor:"pointer",fontWeight:700,fontSize:13,flexShrink:0,
                     boxShadow:"0 3px 10px #ee000040" }}>
            ＋ Add Instance
          </button>
        )}
      </div>

      {/* Env legend */}
      <div style={{ display:"flex",gap:8,marginBottom:20,flexWrap:"wrap" }}>
        {[["PROD","#ef4444"],["PROD1","#f97316"],["STAGING","#f59e0b"],["DR","#0891b2"],["DEV","#7c3aed"],["TEST","#16a34a"]].map(([env,c])=>(
          <span key={env} style={{ fontSize:11,fontWeight:700,padding:"2px 10px",borderRadius:99,
                                    color:"#fff",background:c,opacity:0.85 }}>{env}</span>
        ))}
        <span style={{ fontSize:11,color:p.textMute,marginLeft:4,alignSelf:"center" }}>— environments</span>
      </div>

      {/* Instance grid */}
      {loading ? <Spinner/> : err ? <ErrMsg msg={err} onRetry={load}/> : (
        <div style={{ display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(320px,1fr))",gap:16 }}>
          {instances.map(inst => (
            <InstanceTile key={inst.id} inst={inst} p={p}
              onSelect={setSelInst}
              onEdit={i=>{ setEditInst(i); setShowForm(true); }}
              onDelete={i=>{ setDelErr(null); setDelTarget(i); }}
              isAdmin={isAdmin}/>
          ))}
          {isAdmin && <AddTile onClick={()=>{ setEditInst(null); setShowForm(true); }} p={p}/>}
          {instances.length===0 && !isAdmin && (
            <div style={{ gridColumn:"1/-1",textAlign:"center",padding:60,color:p.textMute }}>
              <div style={{ fontSize:40,marginBottom:12 }}>🤖</div>
              <div style={{ fontSize:16,fontWeight:700,marginBottom:6 }}>No AAP Instances</div>
              <div style={{ fontSize:13 }}>Contact your administrator to add Ansible Automation Platform instances.</div>
            </div>
          )}
        </div>
      )}

      {/* Add/Edit modal */}
      {showForm && (
        <InstanceFormModal
          existing={editInst}
          p={p}
          onClose={()=>setShowForm(false)}
          onSave={()=>{ setShowForm(false); load(); }}/>
      )}

      {/* Delete confirm */}
      {delTarget && (
        <ConfirmDialog p={p} busy={delBusy} err={delErr}
          title="Remove AAP Instance?"
          message={`"${delTarget.name}" (${delTarget.env}) will be removed from CaaS Dashboard. The AAP platform itself will not be affected.`}
          onConfirm={doDelete}
          onCancel={()=>setDelTarget(null)}/>
      )}
    </div>
  );
}
