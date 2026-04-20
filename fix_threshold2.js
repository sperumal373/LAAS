const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = raw.split('\r\n');

let changes = 0;

//  1. Update freeClr to read from localStorage 
let freeclrIdx = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('const freeClr') && lines[i].includes('"#10b981"')) { freeclrIdx = i; break; }
}
if (freeclrIdx < 0) { console.log('ERROR: freeClr not found'); process.exit(1); }
console.log('freeClr at line', freeclrIdx+1, ':', lines[freeclrIdx].trim().substring(0,60));
lines[freeclrIdx] = 'const freeClr = (pct) => { const _w=100-parseInt(localStorage.getItem("thresh_used_warn")||"60"); const _c=100-parseInt(localStorage.getItem("thresh_used_crit")||"80"); return pct>=_w?"#10b981":pct>=_c?"#f59e0b":"#ef4444"; };';
changes++;

//  2. Update snapshot age coloring 
let snapAgeIdx = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('d>30') && lines[i].includes('d>7') && lines[i].includes('#ef4444') && lines[i].includes('snapAge')) { snapAgeIdx = i; break; }
}
if (snapAgeIdx < 0) { console.log('ERROR: snapAge coloring not found'); process.exit(1); }
console.log('snapAge color at line', snapAgeIdx+1);
lines[snapAgeIdx] = '                {(()=>{const d=snapAge(s.created);if(d===null)return<span style={{color:p.textMute}}></span>;const _sc=parseInt(localStorage.getItem("thresh_snap_crit")||"30");const _sw=parseInt(localStorage.getItem("thresh_snap_warn")||"7");const c=d>_sc?"#ef4444":d>_sw?"#f59e0b":"#10b981";return<span style={{fontSize:11,fontWeight:700,color:c,fontFamily:"monospace"}}>{d}d</span>;})()}';
changes++;

//  3. Insert ThresholdModal component before VMwarePage 
let vmwarePageIdx = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].startsWith('function VMwarePage(')) { vmwarePageIdx = i; break; }
}
if (vmwarePageIdx < 0) { console.log('ERROR: VMwarePage not found'); process.exit(1); }
console.log('VMwarePage at line', vmwarePageIdx+1);

const threshModal = [
  '//  Threshold Settings Modal ',
  'function ThresholdModal({p, onClose}) {',
  '  const get = (k,d) => localStorage.getItem(k) || d;',
  '  const [cpuWarn,  setCpuWarn]  = React.useState(get("thresh_cpu_warn",  "60"));',
  '  const [cpuCrit,  setCpuCrit]  = React.useState(get("thresh_cpu_crit",  "80"));',
  '  const [ramWarn,  setRamWarn]  = React.useState(get("thresh_ram_warn",  "70"));',
  '  const [ramCrit,  setRamCrit]  = React.useState(get("thresh_ram_crit",  "85"));',
  '  const [dsWarn,   setDsWarn]   = React.useState(get("thresh_ds_warn",   "70"));',
  '  const [dsCrit,   setDsCrit]   = React.useState(get("thresh_ds_crit",   "85"));',
  '  const [snapWarn, setSnapWarn] = React.useState(get("thresh_snap_warn", "7"));',
  '  const [snapCrit, setSnapCrit] = React.useState(get("thresh_snap_crit", "30"));',
  '  const [saved,    setSaved]    = React.useState(false);',
  '  function validate(v,min,max){ const n=parseInt(v); return !isNaN(n)&&n>=min&&n<=max; }',
  '  function handleSave(){',
  '    if(!validate(cpuWarn,1,99)||!validate(cpuCrit,1,99)||parseInt(cpuWarn)>=parseInt(cpuCrit))',
  '      return alert("CPU: Warning must be less than Critical, both between 1-99%");',
  '    if(!validate(ramWarn,1,99)||!validate(ramCrit,1,99)||parseInt(ramWarn)>=parseInt(ramCrit))',
  '      return alert("RAM: Warning must be less than Critical, both between 1-99%");',
  '    if(!validate(dsWarn,1,99)||!validate(dsCrit,1,99)||parseInt(dsWarn)>=parseInt(dsCrit))',
  '      return alert("Datastore: Warning must be less than Critical, both between 1-99%");',
  '    if(!validate(snapWarn,1,3650)||!validate(snapCrit,1,3650)||parseInt(snapWarn)>=parseInt(snapCrit))',
  '      return alert("Snapshot: Warning days must be less than Critical days (1-3650)");',
  '    localStorage.setItem("thresh_cpu_warn",  cpuWarn);',
  '    localStorage.setItem("thresh_cpu_crit",  cpuCrit);',
  '    localStorage.setItem("thresh_ram_warn",  ramWarn);',
  '    localStorage.setItem("thresh_ram_crit",  ramCrit);',
  '    localStorage.setItem("thresh_ds_warn",   dsWarn);',
  '    localStorage.setItem("thresh_ds_crit",   dsCrit);',
  '    localStorage.setItem("thresh_snap_warn", snapWarn);',
  '    localStorage.setItem("thresh_snap_crit", snapCrit);',
  '    localStorage.setItem("thresh_used_warn", dsWarn);',
  '    localStorage.setItem("thresh_used_crit", dsCrit);',
  '    setSaved(true); setTimeout(()=>{ setSaved(false); onClose(true); }, 900);',
  '  }',
  '  function handleReset(){',
  '    ["thresh_cpu_warn","thresh_cpu_crit","thresh_ram_warn","thresh_ram_crit",',
  '     "thresh_ds_warn","thresh_ds_crit","thresh_snap_warn","thresh_snap_crit",',
  '     "thresh_used_warn","thresh_used_crit"].forEach(k=>localStorage.removeItem(k));',
  '    setCpuWarn("60"); setCpuCrit("80"); setRamWarn("70"); setRamCrit("85");',
  '    setDsWarn("70");  setDsCrit("85"); setSnapWarn("7"); setSnapCrit("30");',
  '  }',
  '  const rowStyle = {display:"flex",gap:8,alignItems:"center",padding:"10px 14px",borderRadius:8,background:"#ffffff06",border:"1px solid #ffffff10",marginBottom:8};',
  '  const inpStyle = {width:68,textAlign:"center",padding:"5px 8px",borderRadius:6,border:"1px solid #ffffff20",background:"#ffffff0c",color:"#f1f5f9",fontSize:14,fontWeight:700};',
  '  const Bdg = ({label,color})=><span style={{fontSize:9,fontWeight:700,padding:"1px 6px",borderRadius:8,background:color+"20",color,border:"1px solid "+color+"40",letterSpacing:".3px",display:"block",marginBottom:3}}>{label}</span>;',
  '  const Cat = ({icon,title,sub,warnVal,warnSet,critVal,critSet,unit}) => (',
  '    <div style={rowStyle}>',
  '      <div style={{flex:"0 0 160px",display:"flex",alignItems:"center",gap:9}}>',
  '        <span style={{fontSize:18}}>{icon}</span>',
  '        <div><div style={{fontWeight:700,fontSize:12,color:p.text}}>{title}</div>',
  '          <div style={{fontSize:10,color:p.textMute}}>{sub}</div></div>',
  '      </div>',
  '      <div style={{display:"flex",gap:16,alignItems:"center",flex:1,justifyContent:"center"}}>',
  '        <div style={{textAlign:"center"}}><Bdg label="WARN" color="#f59e0b"/>',
  '          <input style={inpStyle} type="number" min="1" max={unit==="days"?3650:99} value={warnVal} onChange={e=>warnSet(e.target.value)}/>',
  '          <div style={{fontSize:10,color:p.textMute,marginTop:3}}>{unit}</div></div>',
  '        <span style={{color:p.textMute,fontSize:18}}></span>',
  '        <div style={{textAlign:"center"}}><Bdg label="CRIT" color="#ef4444"/>',
  '          <input style={inpStyle} type="number" min="1" max={unit==="days"?3650:99} value={critVal} onChange={e=>critSet(e.target.value)}/>',
  '          <div style={{fontSize:10,color:p.textMute,marginTop:3}}>{unit}</div></div>',
  '      </div>',
  '      <div style={{flex:"0 0 90px",textAlign:"right",fontSize:11,color:p.textMute}}>',
  '        <div style={{color:"#f59e0b",fontWeight:600}}>  {warnVal}{unit==="days"?"d":"%"}</div>',
  '        <div style={{color:"#ef4444",fontWeight:600,marginTop:2}}>  {critVal}{unit==="days"?"d":"%"}</div>',
  '      </div>',
  '    </div>',
  '  );',
  '  return(',
  '    <div style={{position:"fixed",inset:0,background:"#00000075",zIndex:9999,display:"flex",alignItems:"center",justifyContent:"center",padding:16}} onClick={e=>{if(e.target===e.currentTarget)onClose(false);}}>',
  '      <div style={{background:p.panel,border:"1px solid #a78bfa40",borderRadius:14,width:"100%",maxWidth:560,boxShadow:"0 24px 80px #0009",overflow:"hidden"}}>',
  '        <div style={{padding:"14px 20px",borderBottom:`1px solid ${p.border}`,background:"linear-gradient(135deg,#a78bfa14,transparent)",display:"flex",alignItems:"center",gap:10}}>',
  '          <div style={{width:36,height:36,borderRadius:9,background:"#a78bfa18",border:"1px solid #a78bfa30",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18}}></div>',
  '          <div>',
  '            <div style={{fontWeight:800,fontSize:15,color:p.text}}>Threshold Settings</div>',
  '            <div style={{fontSize:10,color:p.textMute}}>Alert thresholds  drives all color indicators across VMware pages</div>',
  '          </div>',
  '          <button onClick={()=>onClose(false)} style={{marginLeft:"auto",background:"none",border:"none",color:p.textMute,fontSize:20,cursor:"pointer",lineHeight:1,padding:"2px 6px"}}></button>',
  '        </div>',
  '        <div style={{padding:"16px 20px"}}>',
  '          <div style={{fontSize:11,color:"#a78bfa",marginBottom:14,padding:"8px 10px",background:"#a78bfa0a",borderRadius:6,border:"1px solid #a78bfa20"}}>',
  '            ℹ Set <b>Warning</b> ( yellow) and <b>Critical</b> ( red) thresholds. Values persist in browser and apply immediately.',
  '          </div>',
  '          <Cat icon="" title="CPU Usage"       sub="% utilised"        warnVal={cpuWarn}  warnSet={setCpuWarn}  critVal={cpuCrit}  critSet={setCpuCrit}  unit="%"/>',
  '          <Cat icon="" title="RAM Usage"       sub="% utilised"        warnVal={ramWarn}  warnSet={setRamWarn}  critVal={ramCrit}  critSet={setRamCrit}  unit="%"/>',
  '          <Cat icon="" title="Datastore Usage" sub="% utilised"        warnVal={dsWarn}   warnSet={setDsWarn}   critVal={dsCrit}   critSet={setDsCrit}   unit="%"/>',
  '          <Cat icon="" title="Snapshot Age"    sub="days since created" warnVal={snapWarn} warnSet={setSnapWarn} critVal={snapCrit} critSet={setSnapCrit} unit="days"/>',
  '        </div>',
  '        <div style={{padding:"12px 20px",borderTop:`1px solid ${p.border}`,display:"flex",gap:8,justifyContent:"space-between",alignItems:"center"}}>',
  '          <button className="btn btn-ghost btn-sm" onClick={handleReset} title="Restore all defaults"> Reset Defaults</button>',
  '          <div style={{display:"flex",gap:8}}>',
  '            <button className="btn btn-ghost btn-sm" onClick={()=>onClose(false)}>Cancel</button>',
  '            <button className="btn btn-primary btn-sm" onClick={handleSave} style={{fontWeight:700,minWidth:130}}',
  '              disabled={saved}>{saved?" Saved!":" Save Thresholds"}</button>',
  '          </div>',
  '        </div>',
  '      </div>',
  '    </div>',
  '  );',
  '}',
  '',
];

lines.splice(vmwarePageIdx, 0, ...threshModal);
changes++;
console.log('ThresholdModal inserted (', threshModal.length, 'lines)');

// Re-find VMwarePage after splice
let vmPageStart = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].startsWith('function VMwarePage(')) { vmPageStart = i; break; }
}
console.log('VMwarePage now at line', vmPageStart+1);

//  4a. Add thresholdOpen state in VMwarePage 
let stateInsertIdx = -1;
for (let i = vmPageStart; i < vmPageStart + 30; i++) {
  if (lines[i].includes('const [topoTarget,setTopoTarget]')) { stateInsertIdx = i; break; }
}
if (stateInsertIdx < 0) { console.log('ERROR: topoTarget state not found'); process.exit(1); }
console.log('Inserting thresholdOpen state after line', stateInsertIdx+1);
lines.splice(stateInsertIdx + 1, 0, '  const [thresholdOpen, setThresholdOpen] = useState(false);');
changes++;

//  4b. Render ThresholdModal in VMwarePage return 
let topoRenderIdx = -1;
for (let i = vmPageStart; i < vmPageStart + 250; i++) {
  if (lines[i].includes('{topoTarget&&<TopologyModal')) { topoRenderIdx = i; break; }
}
if (topoRenderIdx < 0) { console.log('ERROR: TopologyModal render not found'); process.exit(1); }
console.log('TopologyModal render at line', topoRenderIdx+1);
lines.splice(topoRenderIdx + 1, 0, '      {thresholdOpen&&<ThresholdModal p={p} onClose={(saved)=>setThresholdOpen(false)}/>}');
changes++;

//  4c. Add Threshold Settings card in VM Actions tab 
let summaryIdx = -1;
for (let i = vmPageStart; i < vmPageStart + 900; i++) {
  if (lines[i].includes('Summary of current VMware footprint') || lines[i].includes('Summary of current VMware Footprint')) {
    summaryIdx = i; break;
  }
}
if (summaryIdx < 0) { console.log('ERROR: footprint summary not found'); process.exit(1); }
console.log('Footprint summary at line', summaryIdx+1);

const threshCard = [
  '            {/* Threshold Settings card  admin only */}',
  '            {isAdmin&&(',
  '            <div className="card" style={{border:"1px solid #a78bfa30",borderTop:"3px solid #a78bfa"}}>',
  '              <div style={{padding:"16px 18px"}}>',
  '                <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12}}>',
  '                  <div style={{width:36,height:36,borderRadius:9,background:"#a78bfa18",border:"1px solid #a78bfa30",display:"flex",alignItems:"center",justifyContent:"center",fontSize:18,flexShrink:0}}></div>',
  '                  <div style={{flex:1}}>',
  '                    <div style={{fontWeight:800,fontSize:14,color:"#a78bfa"}}>Threshold Settings</div>',
  '                    <div style={{fontSize:11,color:p.textMute,marginTop:1}}>CPU  RAM  Datastore  Snapshot age alert thresholds</div>',
  '                  </div>',
  '                  <span style={{fontSize:10,fontWeight:700,padding:"2px 8px",borderRadius:10,background:"#a78bfa15",color:"#a78bfa",border:"1px solid #a78bfa30"}}>ADMIN</span>',
  '                </div>',
  '                <div style={{fontSize:12,color:p.textMute,marginBottom:14,padding:"8px 10px",background:"#a78bfa07",borderRadius:6,border:"1px solid #a78bfa18"}}>',
  '                  Configure warning and critical % thresholds for CPU, RAM, and Datastore usage, plus snapshot age thresholds. Drives colour indicators across all VMware views.',
  '                </div>',
  '                <button className="btn btn-sm" style={{width:"100%",fontWeight:700,background:"#a78bfa18",border:"1px solid #a78bfa40",color:"#a78bfa"}}',
  '                  onClick={()=>setThresholdOpen(true)}>',
  '                   Open Threshold Settings',
  '                </button>',
  '              </div>',
  '            </div>',
  '            )}',
];

lines.splice(summaryIdx, 0, ...threshCard);
changes++;
console.log('Threshold card inserted before footprint summary. Total changes:', changes);

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('File saved successfully.');
