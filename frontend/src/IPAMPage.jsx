// IPAMPage.jsx – Self-hosted PostgreSQL IPAM (Solarwinds-style)
import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  fetchIPAM2Summary, fetchIPAM2VLANs, createIPAM2VLAN,
  deleteIPAM2VLAN, fetchIPAM2IPs, updateIPAM2IP, bulkUpdateIPAM2IPs,
  pingIPAM2VLAN, pollIPAM2PingStatus, dnsLookupIPAM2VLAN,
  fetchIPAM2Changelog, fetchIPAM2Conflicts
} from "./api";

/* ─── Palette ───────────────────────────────────────────────────────────── */
const C = {
  bg:        "#0d1b2e",
  panel:     "#0f2040",
  card:      "#112244",
  border:    "#1a3a5c",
  text:      "#d0e4f7",
  muted:     "#6b8cae",
  accent:    "#3b82f6",
  green:     "#22c55e",
  yellow:    "#f59e0b",
  purple:    "#a78bfa",
  red:       "#ef4444",
  blue:      "#3b82f6",
};

/* ─── Global CSS ────────────────────────────────────────────────────────── */
const CSS = `
  @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.15} }
  @keyframes pulse { 0%,100%{transform:scale(1);opacity:1} 50%{transform:scale(1.5);opacity:.7} }
  @keyframes spin  { to{transform:rotate(360deg)} }
  .i-blink { animation:blink 1.4s ease-in-out infinite; }
  .i-pulse { animation:pulse 1.2s ease-in-out infinite; }
  .irow:hover { background:#162d4a !important; cursor:pointer; }
  .ivlan:hover { background:#162d4a !important; }
  .ibtn:hover  { filter:brightness(1.15); }
  ::-webkit-scrollbar{width:5px;height:5px}
  ::-webkit-scrollbar-track{background:#0d1b2e}
  ::-webkit-scrollbar-thumb{background:#1a3a5c;border-radius:3px}
`;

function injectCSS() {
  if (!document.getElementById("ipam-g")) {
    const s = document.createElement("style");
    s.id = "ipam-g"; s.textContent = CSS;
    document.head.appendChild(s);
  }
}

/* ─── Status / Ping config ──────────────────────────────────────────────── */
const STATUS = {
  available: { label:"Available", color:C.green,  dot:"blink" },
  used:      { label:"Used",      color:C.yellow, dot:"solid" },
  reserved:  { label:"Reserved",  color:C.purple, dot:"solid" },
  offline:   { label:"Offline",   color:C.red,    dot:"blink" },
  gateway:   { label:"Gateway",   color:C.blue,   dot:"solid" },
};

/* ─── Reusable atoms ────────────────────────────────────────────────────── */
function Dot({ color, anim, size=8 }) {
  const cls = anim==="blink"?"i-blink":anim==="pulse"?"i-pulse":"";
  return (
    <span className={cls} style={{
      display:"inline-block", width:size, height:size,
      borderRadius:"50%", background:color, flexShrink:0,
      verticalAlign:"middle",
    }}/>
  );
}

function StatusChip({ status }) {
  const s = STATUS[status] || { label:status, color:C.muted, dot:"solid" };
  return (
    <span style={{
      display:"inline-flex", alignItems:"center", gap:5,
      padding:"2px 9px", borderRadius:20,
      background:s.color+"28", border:`1px solid ${s.color}55`,
      color:s.color, fontSize:11, fontWeight:700,
    }}>
      <Dot color={s.color} anim={s.dot} size={6}/>
      {s.label}
    </span>
  );
}

function Spin({ size=16 }) {
  return (
    <div style={{
      width:size, height:size, borderRadius:"50%",
      border:`2px solid ${C.border}`, borderTopColor:C.accent,
      animation:"spin .6s linear infinite", flexShrink:0,
    }}/>
  );
}

function Btn({ onClick, disabled, children, color=C.accent, style:sx={} }) {
  return (
    <button onClick={onClick} disabled={disabled} className="ibtn" style={{
      display:"inline-flex", alignItems:"center", gap:5, padding:"5px 12px",
      borderRadius:6, cursor:disabled?"not-allowed":"pointer",
      background:color+"22", border:`1px solid ${color}44`, color,
      fontSize:12, fontWeight:600, opacity:disabled?.6:1,
      transition:"filter .15s", ...sx,
    }}>{children}</button>
  );
}

/* ─── Legend ────────────────────────────────────────────────────────────── */
function Legend() {
  const items = [
    { label:"Gateway",   color:C.blue,   anim:"solid" },
    { label:"Used",      color:C.yellow, anim:"solid" },
    { label:"Available", color:C.green,  anim:"blink" },
    { label:"Reserved",  color:C.purple, anim:"solid" },
    { label:"Offline",   color:C.red,    anim:"blink" },
    { label:"Ping Up",   color:C.green,  anim:"pulse" },
  ];
  return (
    <div style={{
      display:"flex", flexWrap:"wrap", gap:16, alignItems:"center",
      padding:"6px 14px", background:C.card, borderRadius:6,
      border:`1px solid ${C.border}`, marginBottom:8,
    }}>
      <span style={{ fontSize:11, color:C.muted, fontWeight:700 }}>Legend</span>
      {items.map(i => (
        <span key={i.label} style={{ display:"flex", alignItems:"center", gap:5, fontSize:11, color:C.muted }}>
          <Dot color={i.color} anim={i.anim} size={9}/>
          {i.label}
        </span>
      ))}
    </div>
  );
}

/* ─── IP Edit Modal ─────────────────────────────────────────────────────── */
function IPEditModal({ ip, onClose, onSaved }) {
  const [form, setForm] = useState({
    status:      ip.status      || "available",
    hostname:    ip.hostname    || "",
    device_type: ip.device_type || "",
    mac_address: ip.mac_address || "",
    owner:       ip.owner       || "",
    description: ip.description || "",
    remarks:     ip.remarks     || "",
  });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setForm(f=>({...f,[k]:v}));

  const save = async () => {
    setSaving(true);
    try { await updateIPAM2IP(ip.id, form); onSaved(); onClose(); }
    catch(e) { alert("Save failed: "+e.message); }
    finally { setSaving(false); }
  };

  return (
    <div style={{ position:"fixed", inset:0, background:"#0009", zIndex:9999,
      display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:10,
        padding:26, width:460, color:C.text, maxHeight:"88vh", overflowY:"auto" }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:18 }}>
          <div>
            <div style={{ fontSize:15, fontWeight:700 }}>✏️ Edit IP</div>
            <div style={{ fontSize:12, color:C.muted, marginTop:2 }}>{ip.ip_address}</div>
          </div>
          <button onClick={onClose} style={{ background:"none", border:"none", color:C.muted,
            fontSize:22, cursor:"pointer", lineHeight:1, padding:0 }}>×</button>
        </div>

        <label style={{ fontSize:11, color:C.muted, fontWeight:600 }}>Status</label>
        <select value={form.status} onChange={e=>set("status",e.target.value)}
          style={{ width:"100%", background:C.bg, color:C.text, border:`1px solid ${C.border}`,
            borderRadius:6, padding:"7px 10px", fontSize:13, marginTop:4, marginBottom:12 }}>
          {["available","used","reserved","offline"].map(o=><option key={o}>{o}</option>)}
        </select>

        {[
          ["hostname",    "Hostname"],
          ["device_type", "Device Type"],
          ["mac_address", "MAC Address"],
          ["owner",       "Owner"],
          ["description", "Description"],
        ].map(([k,l])=>(
          <div key={k} style={{ marginBottom:12 }}>
            <label style={{ fontSize:11, color:C.muted, fontWeight:600 }}>{l}</label>
            <input value={form[k]} onChange={e=>set(k,e.target.value)}
              placeholder={`Enter ${l.toLowerCase()}…`}
              style={{ display:"block", width:"100%", marginTop:4, background:C.bg, color:C.text,
                border:`1px solid ${C.border}`, borderRadius:6, padding:"7px 10px",
                fontSize:13, boxSizing:"border-box" }}/>
          </div>
        ))}

        <div style={{ marginBottom:12 }}>
          <label style={{ fontSize:11, color:C.muted, fontWeight:600 }}>Remarks / Notes</label>
          <textarea value={form.remarks} onChange={e=>set("remarks",e.target.value)} rows={3}
            placeholder="Add remarks or notes…"
            style={{ display:"block", width:"100%", marginTop:4, background:C.bg, color:C.text,
              border:`1px solid ${C.border}`, borderRadius:6, padding:"7px 10px",
              fontSize:13, resize:"vertical", fontFamily:"inherit", boxSizing:"border-box" }}/>
        </div>

        <div style={{ display:"flex", gap:8, justifyContent:"flex-end", marginTop:4 }}>
          <Btn onClick={onClose} color={C.muted}>Cancel</Btn>
          <Btn onClick={save} disabled={saving} color={C.accent} style={{ background:C.accent, color:"#fff", border:"none" }}>
            {saving ? "Saving…" : "💾 Save"}
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* ─── Bulk Edit Modal ───────────────────────────────────────────────────── */
function BulkModal({ count, onClose, onSave }) {
  const [form, setForm] = useState({ status:"", device_type:"", owner:"", description:"", remarks:"" });
  const set = (k,v) => setForm(f=>({...f,[k]:v}));
  const apply = () => {
    const d = Object.fromEntries(Object.entries(form).filter(([,v])=>v!==""));
    if (!Object.keys(d).length) { alert("Fill at least one field"); return; }
    onSave(d);
  };
  return (
    <div style={{ position:"fixed", inset:0, background:"#0009", zIndex:9999,
      display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:10,
        padding:26, width:420, color:C.text }}>
        <div style={{ fontSize:15, fontWeight:700, marginBottom:4 }}>Bulk Edit</div>
        <div style={{ fontSize:12, color:C.muted, marginBottom:16 }}>{count} IPs selected · only filled fields are updated</div>
        <label style={{ fontSize:11, color:C.muted, fontWeight:600 }}>Status</label>
        <select value={form.status} onChange={e=>set("status",e.target.value)}
          style={{ width:"100%", background:C.bg, color:C.text, border:`1px solid ${C.border}`,
            borderRadius:6, padding:"6px 10px", fontSize:12, marginTop:4, marginBottom:10 }}>
          <option value="">(unchanged)</option>
          {["available","used","reserved","offline"].map(o=><option key={o}>{o}</option>)}
        </select>
        {[["device_type","Device Type"],["owner","Owner"],["description","Description"]].map(([k,l])=>(
          <div key={k} style={{ marginBottom:10 }}>
            <label style={{ fontSize:11, color:C.muted, fontWeight:600 }}>{l}</label>
            <input value={form[k]} onChange={e=>set(k,e.target.value)}
              style={{ display:"block", width:"100%", marginTop:4, background:C.bg, color:C.text,
                border:`1px solid ${C.border}`, borderRadius:6, padding:"6px 10px",
                fontSize:12, boxSizing:"border-box" }}/>
          </div>
        ))}
        <div style={{ marginBottom:10 }}>
          <label style={{ fontSize:11, color:C.muted, fontWeight:600 }}>Remarks / Notes</label>
          <textarea value={form.remarks} onChange={e=>set("remarks",e.target.value)} rows={2}
            style={{ display:"block", width:"100%", marginTop:4, background:C.bg, color:C.text,
              border:`1px solid ${C.border}`, borderRadius:6, padding:"6px 10px",
              fontSize:12, resize:"vertical", fontFamily:"inherit", boxSizing:"border-box" }}/>
        </div>
        <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
          <Btn onClick={onClose} color={C.muted}>Cancel</Btn>
          <Btn onClick={apply} color={C.accent} style={{ background:C.accent, color:"#fff", border:"none" }}>Apply</Btn>
        </div>
      </div>
    </div>
  );
}

/* ─── Add VLAN Modal ────────────────────────────────────────────────────── */
function AddVLANModal({ defaultSite, onClose, onSaved }) {
  const [form, setForm] = useState({ vlan_id:"", name:"", subnet:"", site:defaultSite||"DC", description:"" });
  const [saving, setSaving] = useState(false);
  const set = (k,v) => setForm(f=>({...f,[k]:v}));
  const save = async () => {
    if (!form.vlan_id||!form.subnet) { alert("VLAN ID and Subnet required"); return; }
    setSaving(true);
    try { await createIPAM2VLAN(form); onSaved(); onClose(); }
    catch(e) { alert("Failed: "+e.message); }
    finally { setSaving(false); }
  };
  const inp = {display:"block",width:"100%",marginTop:4,background:C.bg,color:C.text,
    border:`1px solid ${C.border}`,borderRadius:6,padding:"7px 10px",fontSize:13,boxSizing:"border-box"};
  return (
    <div style={{ position:"fixed", inset:0, background:"#0009", zIndex:9999,
      display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div style={{ background:C.panel, border:`1px solid ${C.border}`, borderRadius:10,
        padding:26, width:400, color:C.text }}>
        <div style={{ fontSize:15, fontWeight:700, marginBottom:18 }}>➕ Add VLAN</div>
        {[["vlan_id","VLAN ID","number","e.g. 1101"],["name","Name","text","e.g. Server VLAN"],
          ["subnet","Subnet (CIDR)","text","e.g. 172.17.101.0/24"],["description","Description","text","optional"]
        ].map(([k,l,t,ph])=>(
          <div key={k} style={{ marginBottom:12 }}>
            <label style={{ fontSize:11, color:C.muted, fontWeight:600 }}>{l}</label>
            <input type={t} value={form[k]} placeholder={ph} onChange={e=>set(k,e.target.value)} style={inp}/>
          </div>
        ))}
        <div style={{ marginBottom:14 }}>
          <label style={{ fontSize:11, color:C.muted, fontWeight:600 }}>Site</label>
          <select value={form.site} onChange={e=>set("site",e.target.value)} style={{...inp,marginTop:4}}>
            <option>DC</option><option>DR</option>
          </select>
        </div>
        <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
          <Btn onClick={onClose} color={C.muted}>Cancel</Btn>
          <Btn onClick={save} disabled={saving} color={C.accent} style={{ background:C.accent, color:"#fff", border:"none" }}>
            {saving?"Creating…":"Create"}
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* ─── Left panel VLAN item ──────────────────────────────────────────────── */
function VLANItem({ vlan, selected, onClick, canManage, onDelete }) {
  const total  = vlan.total_ips || 0;
  const used   = vlan.used_ips  || 0;
  const free   = vlan.free_ips  || (total - used);
  const pingUp = vlan.ping_up   || vlan.up_ips || 0;
  const pct    = total > 0 ? Math.round((used / total) * 100) : 0;
  const barCol = pct > 80 ? C.red : pct > 50 ? C.yellow : C.green;
  const siteC  = vlan.site === "DC" ? C.blue : C.yellow;

  return (
    <div className="ivlan" onClick={onClick} style={{
      padding:"9px 10px", borderRadius:7, marginBottom:2,
      background: selected ? "#162d4a" : "transparent",
      borderLeft: `3px solid ${selected ? siteC : "transparent"}`,
      border: selected ? `1px solid ${C.border}` : "1px solid transparent",
      transition:"background .1s",
    }}>
      {/* Row 1: site badge + name + % + delete */}
      <div style={{ display:"flex", alignItems:"center", gap:5, marginBottom:3 }}>
        <span style={{ fontSize:10, fontWeight:800, color:siteC, background:siteC+"22",
          padding:"1px 4px", borderRadius:3, flexShrink:0 }}>{vlan.site}</span>
        <span style={{ fontSize:14, fontWeight:700, color:C.text, flex:1,
          overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
          Vlan{vlan.vlan_id}
        </span>
        <span style={{ fontSize:12, fontWeight:700,
          color: pct>80?C.red:pct>50?C.yellow:C.muted, flexShrink:0 }}>{pct}%</span>
        {canManage && (
          <button title="Delete VLAN" onClick={e=>{e.stopPropagation();onDelete(vlan);}} className="ibtn"
            style={{ padding:"1px 5px", borderRadius:3, fontSize:11, cursor:"pointer",
              background:C.red+"18", border:`1px solid ${C.red}40`,
              color:C.red, fontWeight:800, lineHeight:1.5, flexShrink:0 }}>✕</button>
        )}
      </div>
      {/* Subnet */}
      <div style={{ fontSize:12, color:C.muted, marginBottom:4 }}>{vlan.subnet}</div>
      {/* Progress bar */}
      <div style={{ height:3, background:"#1a3a5c", borderRadius:2, marginBottom:4 }}>
        <div style={{ height:"100%", borderRadius:2, width:`${pct}%`, background:barCol }}/>
      </div>
      {/* Counts */}
      <div style={{ display:"flex", gap:8, fontSize:12 }}>
        <span style={{ color:C.green }}>✓ {free} free</span>
        <span style={{ color:C.yellow }}>{used} used</span>
        {pingUp > 0 && <span style={{ color:C.blue, display:"flex", alignItems:"center", gap:3 }}>
          <Dot color={C.green} anim="pulse" size={6}/>{pingUp} up
        </span>}
      </div>
    </div>
  );
}

/* ─── Stats row ─────────────────────────────────────────────────────────── */
function StatsRow({ ips }) {
  const c = useMemo(() => {
    const r = { available:0, used:0, reserved:0, offline:0 };
    ips.forEach(ip=>{ if(r[ip.status]!==undefined) r[ip.status]++; });
    return r;
  }, [ips]);
  const total = ips.length || 1;
  const pingUp = ips.filter(i=>i.ping_status==="up").length;
  return (
    <div style={{ display:"flex", gap:8, marginBottom:10, flexWrap:"wrap" }}>
      {[
        { k:"available", label:"Free",     color:C.green  },
        { k:"used",      label:"Used",     color:C.yellow },
        { k:"reserved",  label:"Reserved", color:C.purple },
        { k:"offline",   label:"Offline",  color:C.red    },
      ].map(({k,label,color}) => {
        const v = c[k]; const pct = ((v/total)*100).toFixed(0);
        return (
          <div key={k} style={{ flex:1, minWidth:72, background:C.card, border:`1px solid ${C.border}`,
            borderRadius:7, padding:"8px 11px" }}>
            <div style={{ fontSize:10, color:C.muted }}>{label}</div>
            <div style={{ fontSize:20, fontWeight:700, color, lineHeight:1.2 }}>{v}</div>
            <div style={{ fontSize:9, color:"#3a5a7a", marginTop:1 }}>{pct}%</div>
            <div style={{ height:2, background:"#1a3a5c", borderRadius:2, marginTop:4 }}>
              <div style={{ height:"100%", background:color, width:`${pct}%`, borderRadius:2 }}/>
            </div>
          </div>
        );
      })}
      <div style={{ flex:1, minWidth:72, background:C.card, border:`1px solid ${C.border}`,
        borderRadius:7, padding:"8px 11px" }}>
        <div style={{ fontSize:10, color:C.muted }}>Ping Up</div>
        <div style={{ fontSize:20, fontWeight:700, color:C.green, lineHeight:1.2, display:"flex", alignItems:"center", gap:6 }}>
          <Dot color={C.green} anim={pingUp>0?"pulse":"solid"} size={9}/>{pingUp}
        </div>
        <div style={{ fontSize:9, color:"#3a5a7a", marginTop:1 }}>of {ips.length}</div>
      </div>
    </div>
  );
}

/* ─── IP Grid Tab ───────────────────────────────────────────────────────── */
const IPGridTab = React.memo(function IPGridTab({ vlan, canManage, reloadRef }) {
  const [ips, setIps]           = useState([]);
  const [loading, setLoading]   = useState(false);
  const [filter, setFilter]     = useState("all");
  const [q, setQ]               = useState("");
  const [selected, setSelected] = useState([]);
  const [editIP, setEditIP]     = useState(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [lastScan, setLastScan] = useState(null);

  const load = useCallback(async (silent = false) => {
    if (!vlan) return;
    if (!silent) setLoading(true);
    try {
      const d = await fetchIPAM2IPs(vlan.id, filter==="all"?null:filter, q||null);
      if (silent) {
        // Merge in-place: only update changed rows, don't flash/replace the table
        setIps(prev => {
          const map = Object.fromEntries(d.map(r => [r.id, r]));
          const merged = prev.map(r => map[r.id] ? { ...r, ...map[r.id] } : r);
          // add any new rows
          const ids = new Set(prev.map(r => r.id));
          d.forEach(r => { if (!ids.has(r.id)) merged.push(r); });
          return merged;
        });
      } else {
        setIps(d);
      }
    } catch(e) { console.error(e); }
    finally { if (!silent) setLoading(false); }
  }, [vlan, filter, q]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (reloadRef) reloadRef.current = load; }, [load, reloadRef]);

  const doScan = async () => {
    setScanning(true);
    setLastScan(null);
    try {
      await pingIPAM2VLAN(vlan.id);  // starts background scan immediately
      // Poll every 1.5s until done
      let attempts = 0;
      const maxAttempts = 60; // 90s max
      await new Promise(resolve => {
        const interval = setInterval(async () => {
          attempts++;
          try {
            const s = await pollIPAM2PingStatus(vlan.id);
            if (!s.running || attempts >= maxAttempts) {
              clearInterval(interval);
              resolve();
            }
          } catch { clearInterval(interval); resolve(); }
        }, 1500);
      });
      await load(true); // silent – no spinner flash
      setLastScan(new Date().toLocaleTimeString());
    } catch(e) { console.error('Scan error:', e); }
    finally { setScanning(false); }
  };

  const doDNS = async () => {
    setScanning(true);
    try { await dnsLookupIPAM2VLAN(vlan.id); await load(); }
    catch(e) { console.error(e); }
    finally { setScanning(false); }
  };

  const toggleSel = id => setSelected(s=>s.includes(id)?s.filter(x=>x!==id):[...s,id]);
  const toggleAll = () => setSelected(s=>s.length===ips.length?[]:ips.map(x=>x.id));

  const doBulkSave = async (data) => {
    try { await bulkUpdateIPAM2IPs(selected, data); setBulkOpen(false); setSelected([]); await load(); }
    catch(e) { alert("Bulk update failed: "+e.message); }
  };

  const COLS = [
    { key:"ip_address",  label:"Address",      w:130 },
    { key:"status",      label:"Status",        w:110 },
    { key:"ping",        label:"Ping",          w:54  },
    { key:"mac_address", label:"MAC",           w:130 },
    { key:"device_type", label:"Device Type",   w:110 },
    { key:"hostname",    label:"Hostname",       w:160 },
    { key:"owner",       label:"Owner",          w:90  },
    { key:"remarks",     label:"Notes / Desc",   w:200 },
  ];

  const selStyle = { background:C.bg, color:C.text, border:`1px solid ${C.border}`,
    borderRadius:6, padding:"5px 10px", fontSize:12 };

  return (
    <div>
      <Legend />
      <StatsRow ips={ips} />

      {/* Toolbar */}
      <div style={{ display:"flex", gap:7, marginBottom:8, flexWrap:"wrap", alignItems:"center" }}>
        <select value={filter} onChange={e=>setFilter(e.target.value)} style={selStyle}>
          <option value="all">All</option>
          <option value="available">Available</option>
          <option value="used">Used</option>
          <option value="reserved">Reserved</option>
          <option value="offline">Offline</option>
        </select>
        <input value={q} onChange={e=>setQ(e.target.value)}
          placeholder="Search IP, hostname, purpose, device…"
          style={{...selStyle, flex:1, minWidth:160}}/>
        <Btn onClick={load} color={C.muted}>🔄</Btn>
        <Btn onClick={doScan} disabled={scanning} color="#38bdf8">
          {scanning ? <><Spin size={12}/>&nbsp;Scanning…</> : "📡 Scan"}
        </Btn>
        <Btn onClick={doDNS} disabled={scanning} color={C.purple}>🔍 DNS</Btn>
        {lastScan && <span style={{ fontSize:10, color:C.muted }}>synced {lastScan}</span>}
        {selected.length>0 && canManage && (
          <Btn onClick={()=>setBulkOpen(true)} color={C.yellow}>
            ✏️ Edit {selected.length}
          </Btn>
        )}
      </div>

      {/* Table */}
      <div style={{ overflowX:"auto", borderRadius:8, border:`1px solid ${C.border}` }}>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:14, color:C.text }}>
          <colgroup>
            <col style={{ width:34 }}/><col style={{ width:28 }}/>
            {COLS.map(c=><col key={c.key} style={{ width:c.w, minWidth:c.w }}/>)}
            <col style={{ width:54 }}/>
          </colgroup>
          <thead>
            <tr style={{ background:"#0d1e38" }}>
              <th style={{ padding:"8px 8px", borderBottom:`1px solid ${C.border}` }}>
                <input type="checkbox"
                  checked={selected.length===ips.length&&ips.length>0}
                  onChange={toggleAll}/>
              </th>
              <th style={{ borderBottom:`1px solid ${C.border}` }}></th>
              {COLS.map(col=>(
                <th key={col.key} style={{ padding:"8px 10px", textAlign:"left",
                  color:C.muted, fontWeight:600, fontSize:12,
                  borderBottom:`1px solid ${C.border}`, whiteSpace:"nowrap",
                  letterSpacing:.4 }}>{col.label.toUpperCase()}</th>
              ))}
              <th style={{ padding:"8px 10px", color:C.muted, fontWeight:600, fontSize:11,
                borderBottom:`1px solid ${C.border}`, textAlign:"center" }}>EDIT</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={COLS.length+3}
                style={{ textAlign:"center", padding:28 }}>
                <div style={{ display:"flex", justifyContent:"center" }}><Spin size={24}/></div>
              </td></tr>
            ) : ips.length===0 ? (
              <tr><td colSpan={COLS.length+3}
                style={{ textAlign:"center", padding:24, color:C.muted }}>No IPs found</td></tr>
            ) : ips.map((ip, idx) => {
              const pingC = ip.ping_status==="up"?C.green:ip.ping_status==="down"?C.red:C.muted;
              const pingA = ip.ping_status==="up"?"pulse":"solid";
              const rowBg = idx%2===0 ? C.panel : "#0d1e38";
              const remarks = [ip.remarks, ip.description].filter(Boolean).join(" · ") || "–";
              return (
                <tr key={ip.id} className="irow"
                  style={{ background:rowBg }}
                  onClick={canManage ? ()=>setEditIP(ip) : undefined}>
                  <td style={{ textAlign:"center", padding:"5px 8px" }}
                    onClick={e=>e.stopPropagation()}>
                    <input type="checkbox" checked={selected.includes(ip.id)}
                      onChange={()=>toggleSel(ip.id)}/>
                  </td>
                  <td style={{ padding:"5px 5px" }}>
                    <Dot color={pingC} anim={pingA} size={8}/>
                  </td>
                  {COLS.map(col=>(
                    <td key={col.key} style={{ padding:"6px 10px",
                      overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
                      borderBottom:`1px solid ${C.border}18`, maxWidth:col.w }}>
                      {col.key==="status"  ? <StatusChip status={ip.status}/> :
                       col.key==="ping"    ? <span style={{ color:pingC, fontSize:13 }}>{ip.ping_status||"–"}</span> :
                       col.key==="remarks" ? <span style={{ color:C.muted }} title={remarks}>{remarks}</span> :
                       col.key==="last_seen" ? <span style={{ color:C.muted, fontSize:10 }}>
                         {ip.last_seen?new Date(ip.last_seen).toLocaleString():"–"}</span> :
                       <span title={ip[col.key]||""}>{ip[col.key]||"–"}</span>}
                    </td>
                  ))}
                  <td style={{ textAlign:"center", padding:"5px 8px" }}
                    onClick={e=>e.stopPropagation()}>
                    {canManage && (
                      <button onClick={()=>setEditIP(ip)} className="ibtn"
                        title="Edit IP"
                        style={{ padding:"3px 8px", borderRadius:5, fontSize:11, cursor:"pointer",
                          background:C.blue+"22", border:`1px solid ${C.blue}44`,
                          color:C.blue, fontWeight:600 }}>✏</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize:10, color:C.muted, marginTop:5 }}>
        {ips.length} IPs · click any row to edit
      </div>

      {editIP && <IPEditModal ip={editIP} onClose={()=>setEditIP(null)} onSaved={load}/>}
      {bulkOpen && <BulkModal count={selected.length} onClose={()=>setBulkOpen(false)} onSave={doBulkSave}/>}
    </div>
  );
}, (prev, next) => prev.vlan?.id === next.vlan?.id && prev.canManage === next.canManage);

/* ─── Changelog Tab ─────────────────────────────────────────────────────── */
function ChangelogTab({ vlanId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setLoading(true);
    fetchIPAM2Changelog(vlanId, 200).then(setRows).catch(console.error).finally(()=>setLoading(false));
  }, [vlanId]);
  return (
    <div style={{ overflowX:"auto", borderRadius:8, border:`1px solid ${C.border}` }}>
      <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12, color:C.text }}>
        <thead><tr style={{ background:"#0d1e38" }}>
          {["Time","IP","Field","Old Value","New Value","By"].map(h=>(
            <th key={h} style={{ padding:"8px 10px", textAlign:"left", color:C.muted,
              fontWeight:600, fontSize:11, borderBottom:`1px solid ${C.border}`,
              letterSpacing:.4 }}>{h.toUpperCase()}</th>
          ))}
        </tr></thead>
        <tbody>
          {loading?<tr><td colSpan={6} style={{padding:28,textAlign:"center"}}><Spin/></td></tr>
          :rows.map((r,i)=>(
            <tr key={i} className="irow" style={{ background:i%2===0?C.panel:"#0d1e38" }}>
              <td style={{ padding:"6px 10px", whiteSpace:"nowrap", color:C.muted, fontSize:11 }}>
                {new Date(r.changed_at).toLocaleString()}</td>
              <td style={{ padding:"6px 10px" }}>{r.ip_address}</td>
              <td style={{ padding:"6px 10px" }}>{r.field||r.field_name}</td>
              <td style={{ padding:"6px 10px", color:C.red }}>{r.old_value||"–"}</td>
              <td style={{ padding:"6px 10px", color:C.green }}>{r.new_value||"–"}</td>
              <td style={{ padding:"6px 10px", color:C.muted }}>{r.changed_by||"system"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─── Conflicts Tab ─────────────────────────────────────────────────────── */
function ConflictsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    setLoading(true);
    fetchIPAM2Conflicts().then(setData).catch(console.error).finally(()=>setLoading(false));
  }, []);
  if (loading) return <div style={{ padding:28, textAlign:"center" }}><Spin/></div>;
  const dups = data?.duplicate_ips || [];
  const hosts = data?.duplicate_hostnames || [];
  if (!dups.length && !hosts.length)
    return <div style={{ textAlign:"center", padding:36, color:C.green, fontSize:14 }}>✅ No conflicts detected</div>;
  return (
    <div>
      {dups.length > 0 && <div style={{ color:C.yellow, marginBottom:8, fontSize:13 }}>⚠ Duplicate IPs across VLANs: {dups.length}</div>}
      {hosts.length > 0 && <div style={{ color:C.yellow, fontSize:13 }}>⚠ Duplicate Hostnames: {hosts.length}</div>}
    </div>
  );
}

/* ─── Summary top bar ───────────────────────────────────────────────────── */
function TopStats({ summary, autoScanning }) {
  if (!summary) return null;
  const cards = [
    { label:"Total IPs",  value:summary.total_ips,     color:C.blue   },
    { label:"Used",       value:summary.used_ips,      color:C.yellow },
    { label:"Free",       value:summary.available_ips||summary.free_ips, color:C.green  },
    { label:"Reserved",   value:summary.reserved_ips,  color:C.purple },
    { label:"Offline",    value:summary.offline_ips,   color:C.red    },
    { label:"VLANs",      value:summary.total_vlans,   color:C.muted  },
  ];
  return (
    <div style={{ display:"flex", gap:8, marginBottom:12, flexWrap:"wrap", alignItems:"center" }}>
      {cards.map(c=>(
        <div key={c.label} style={{ background:C.panel, border:`1px solid ${C.border}`,
          borderRadius:7, padding:"7px 14px", minWidth:80 }}>
          <div style={{ fontSize:10, color:C.muted }}>{c.label}</div>
          <div style={{ fontSize:20, fontWeight:700, color:c.color }}>{c.value??0}</div>
        </div>
      ))}
      {autoScanning && (
        <div style={{ marginLeft:"auto", background:C.panel, border:`1px solid ${C.border}`,
          borderRadius:7, padding:"7px 14px", fontSize:11, color:C.muted,
          display:"flex", alignItems:"center", gap:6 }}>
          <Spin size={12}/>
          <span style={{ color:"#38bdf8" }}>Auto-scanning…</span>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
═══════════════════════════════════════════════════════════════════════════ */
export default function IPAMPage({ currentUser, p }) {
  injectCSS();
  const role       = currentUser?.role || p?.role || "";
  const canManage  = role==="admin" || role==="operator";

  const [summary, setSummary]       = useState(null);
  const [vlans, setVlans]           = useState([]);
  const [site, setSite]             = useState("DC");
  const [selVlan, setSelVlan]       = useState(null);
  const [tab, setTab]               = useState("ips");
  const [showAdd, setShowAdd]       = useState(false);

  const reloadRef      = useRef(null);
  const autoLoopRef    = useRef(null);
  const selVlanIdRef   = useRef(null);  // always current, no re-render on change
  const [autoScanning, setAutoScanning] = useState(false);

  const loadSummary = useCallback(async () => {
    try { setSummary(await fetchIPAM2Summary()); } catch(e) { console.error(e); }
  }, []);

  const loadVlans = useCallback(async (silent = false) => {
    try {
      const d = await fetchIPAM2VLANs(site);
      setVlans(d);
      if (!silent) {
        setSelVlan(sv => {
          if (!sv || sv.site !== site) return d[0] || null;
          return d.find(v=>v.id===sv.id) || d[0] || null;
        });
      } else {
        // Silent: only refresh counts on selVlan, don't reset selection
        setSelVlan(sv => sv ? (d.find(v=>v.id===sv.id) || sv) : sv);
      }
    } catch(e) { console.error(e); }
  }, [site]);

  const loadAll = useCallback(() => { loadSummary(); loadVlans(); }, [loadSummary, loadVlans]);
  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { selVlanIdRef.current = selVlan?.id ?? null; }, [selVlan?.id]);

  /* Continuous auto-scan loop — runs immediately, then loops forever */
  useEffect(() => {
    if (!selVlan) { setAutoScanning(false); return; }
    const token = { cancelled: false };
    autoLoopRef.current = token;

    const runLoop = async () => {
      while (!token.cancelled) {
        const vid = selVlanIdRef.current;
        if (!vid) break;
        setAutoScanning(true);
        try {
          await pingIPAM2VLAN(vid);
          let a = 0;
          await new Promise(res => {
            const t = setInterval(async () => {
              a++;
              try {
                const s = await pollIPAM2PingStatus(vid);
                if (!s.running || a > 60) { clearInterval(t); res(); }
              } catch { clearInterval(t); res(); }
            }, 1500);
          });
          if (token.cancelled) break;
          // Silent in-place merge — no loading state, no re-mount, no blink
          if (reloadRef.current) await reloadRef.current(true);
          // Update summary counts only (no setVlans/setSelVlan)
          loadSummary();
        } catch(e) { console.error("Auto-scan:", e); }
        if (!token.cancelled) await new Promise(r => setTimeout(r, 5000));
      }
      setAutoScanning(false);
    };

    runLoop();
    return () => { token.cancelled = true; };
  }, [selVlan?.id]);

  const deleteVlan = async (vlan) => {
    if (!window.confirm(`Delete VLAN ${vlan.vlan_id} (${vlan.subnet})?\nAll ${vlan.total_ips} IP records will be removed.`)) return;
    try { await deleteIPAM2VLAN(vlan.id); if (selVlan?.id===vlan.id) setSelVlan(null); loadAll(); }
    catch(e) { alert("Delete failed: "+e.message); }
  };

  const filteredVlans = useMemo(() => vlans.filter(v=>v.site===site), [vlans, site]);
  const TABS = [
    { id:"ips",       label:"IP Grid"    },
    { id:"changelog", label:"Change Log" },
    { id:"conflicts", label:"Conflicts"  },
  ];

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100%",
      background:C.bg, color:C.text, fontFamily:"'Inter',system-ui,sans-serif", minHeight:0 }}>

      {/* ── Top header ── */}
      <div style={{ padding:"11px 18px", borderBottom:`1px solid ${C.border}`,
        display:"flex", alignItems:"center", justifyContent:"space-between", gap:10, flexWrap:"wrap" }}>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          <span style={{ fontSize:16, fontWeight:800 }}>🌐 IP Address Management</span>
        </div>
        <div style={{ display:"flex", gap:7 }}>
          <Btn onClick={loadAll} color={C.muted}>🔄 Refresh</Btn>
        </div>
      </div>

      {/* ── Top stats ── */}
      <div style={{ padding:"10px 18px 0" }}>
        <TopStats summary={summary} autoScanning={autoScanning}/>
      </div>

      {/* ── Body ── */}
      <div style={{ display:"flex", flex:1, minHeight:0, overflow:"hidden" }}>

        {/* LEFT panel */}
        <div style={{ width:225, flexShrink:0, background:C.panel,
          borderRight:`1px solid ${C.border}`, display:"flex", flexDirection:"column" }}>

          {/* DC / DR tabs */}
          <div style={{ display:"flex", borderBottom:`1px solid ${C.border}` }}>
            {["DC","DR"].map(s=>(
              <button key={s} onClick={()=>setSite(s)} className="ibtn" style={{
                flex:1, padding:"9px 0", border:"none", cursor:"pointer",
                fontSize:13, fontWeight:700, background:"transparent",
                color:site===s?(s==="DC"?C.blue:C.yellow):C.muted,
                borderBottom:site===s?`2px solid ${s==="DC"?C.blue:C.yellow}`:"2px solid transparent",
                transition:"color .12s",
              }}>{s} — {s==="DC"?"DATA CENTRE":"DISASTER RECOVERY"}</button>
            ))}
          </div>

          {/* Add VLAN btn */}
          {canManage && (
            <div style={{ padding:"7px 9px", borderBottom:`1px solid ${C.border}` }}>
              <button onClick={()=>setShowAdd(true)} className="ibtn" style={{
                width:"100%", padding:"6px 0", background:C.accent, color:"#fff",
                border:"none", borderRadius:6, fontSize:12, fontWeight:700, cursor:"pointer" }}>
                + VLAN
              </button>
            </div>
          )}

          {/* VLAN list */}
          <div style={{ flex:1, overflowY:"auto", padding:"5px 7px" }}>
            {filteredVlans.length===0
              ? <div style={{ color:C.muted, fontSize:12, textAlign:"center", marginTop:20 }}>No VLANs</div>
              : filteredVlans.map(v=>(
                <VLANItem key={v.id} vlan={v}
                  selected={selVlan?.id===v.id}
                  onClick={()=>{ setSelVlan(v); setTab("ips"); }}
                  canManage={canManage}
                  onDelete={deleteVlan}/>
              ))
            }
          </div>

          {/* Footer */}
          <div style={{ padding:"6px 11px", borderTop:`1px solid ${C.border}`,
            fontSize:10, color:C.muted }}>
            {filteredVlans.length} VLANs · {site}
          </div>
        </div>

        {/* RIGHT panel */}
        <div style={{ flex:1, display:"flex", flexDirection:"column", minWidth:0, overflow:"hidden" }}>
          {selVlan ? (
            <>
              {/* VLAN title */}
              <div style={{ padding:"9px 18px", borderBottom:`1px solid ${C.border}`,
                display:"flex", alignItems:"center", gap:10, flexWrap:"wrap" }}>
                <span style={{ fontSize:11, fontWeight:800, padding:"2px 7px", borderRadius:4,
                  background:(selVlan.site==="DC"?C.blue:C.yellow)+"22",
                  color:selVlan.site==="DC"?C.blue:C.yellow,
                  border:`1px solid ${(selVlan.site==="DC"?C.blue:C.yellow)}44` }}>{selVlan.site}</span>
                <strong style={{ fontSize:14 }}>Vlan{selVlan.vlan_id} — {selVlan.name||`Vlan${selVlan.vlan_id}`}</strong>
                <span style={{ fontSize:11, color:C.muted }}>
                  {selVlan.subnet} · Gateway: {selVlan.gateway||`${selVlan.subnet.replace("/24","").replace(/\.\d+$/,".1")}`}
                </span>
                <div style={{ marginLeft:"auto", display:"flex", gap:14, fontSize:11 }}>
                  <span><strong style={{ color:C.text }}>{selVlan.total_ips||254}</strong> <span style={{ color:C.muted }}>Total</span></span>
                  <span><strong style={{ color:C.yellow }}>{selVlan.used_ips||0}</strong> <span style={{ color:C.muted }}>Used</span></span>
                  <span><strong style={{ color:C.green }}>{selVlan.free_ips||0}</strong> <span style={{ color:C.muted }}>Free</span></span>
                  <span><strong style={{ color:C.green }}>{selVlan.ping_up||selVlan.up_ips||0}</strong> <span style={{ color:C.muted }}>Ping Up</span></span>
                </div>
              </div>

              {/* Tabs */}
              <div style={{ display:"flex", borderBottom:`1px solid ${C.border}`, padding:"0 18px" }}>
                {TABS.map(t=>(
                  <button key={t.id} onClick={()=>setTab(t.id)} className="ibtn" style={{
                    padding:"9px 16px", border:"none", cursor:"pointer", fontSize:12, fontWeight:600,
                    background:"transparent", color:tab===t.id?C.accent:C.muted,
                    borderBottom:tab===t.id?`2px solid ${C.accent}`:"2px solid transparent",
                    transition:"color .12s",
                  }}>{t.label}</button>
                ))}
              </div>

              {/* Content */}
              <div style={{ flex:1, overflowY:"auto", padding:"12px 18px" }}>
                {tab==="ips"       && <IPGridTab vlan={selVlan} canManage={canManage} reloadRef={reloadRef}/>}
                {tab==="changelog" && <ChangelogTab vlanId={selVlan.id}/>}
                {tab==="conflicts" && <ConflictsTab/>}
              </div>
            </>
          ) : (
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center",
              flexDirection:"column", gap:10, color:C.muted }}>
              <div style={{ fontSize:40 }}>🌐</div>
              <div style={{ fontSize:14, fontWeight:600 }}>Select a VLAN from the left panel</div>
            </div>
          )}
        </div>
      </div>

      {showAdd && <AddVLANModal defaultSite={site} onClose={()=>setShowAdd(false)} onSaved={loadAll}/>}
    </div>
  );
}
