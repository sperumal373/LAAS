
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');
let changes = 0;

// ── 1. Update freeClr to read from localStorage ──
let freeclrIdx = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('const freeClr')) { freeclrIdx = i; break; }
}
if (freeclrIdx < 0) { console.log('ERROR: freeClr not found'); process.exit(1); }
if (lines[freeclrIdx].includes('thresh_used_warn')) {
  console.log('[1] freeClr already patched');
} else {
  console.log('[1] Patching freeClr at line', freeclrIdx+1);
  lines[freeclrIdx] = "const freeClr = (pct) => { const _w=100-parseInt(localStorage.getItem('thresh_used_warn')||'60'); const _c=100-parseInt(localStorage.getItem('thresh_used_crit')||'80'); return pct>=_w?'#10b981':pct>=_c?'#f59e0b':'#ef4444'; };";
  changes++;
}

// ── 2. Update snapshot age coloring ──
let snapAgeIdx = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('d>30') && lines[i].includes('d>7') && lines[i].includes('snapAge')) { snapAgeIdx = i; break; }
}
if (snapAgeIdx < 0) {
  console.log('[2] snapAge already patched');
} else {
  console.log('[2] Patching snapAge at line', snapAgeIdx+1);
  lines[snapAgeIdx] = "                {(()=>{const d=snapAge(s.created);if(d===null)return<span style={{color:p.textMute}}>&#8212;</span>;const _sc=parseInt(localStorage.getItem('thresh_snap_crit')||'30');const _sw=parseInt(localStorage.getItem('thresh_snap_warn')||'7');const c=d>_sc?'#ef4444':d>_sw?'#f59e0b':'#10b981';return<span style={{fontSize:11,fontWeight:700,color:c,fontFamily:'monospace'}}>{d}d</span>;})()}";
  changes++;
}

// ── 3. Insert ThresholdModal component before VMwarePage ──
const alreadyHasModal = lines.some(l => l.includes('function ThresholdModal('));
if (alreadyHasModal) {
  console.log('[3] ThresholdModal already exists');
} else {
  let vIdx = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith('function VMwarePage(')) { vIdx = i; break; }
  }
  if (vIdx < 0) { console.log('ERROR: VMwarePage not found'); process.exit(1); }
  console.log('[3] Inserting ThresholdModal before VMwarePage at line', vIdx+1);
  const modal = [
    "// -- Threshold Settings Modal (admin) --",
    "function ThresholdModal({p, onClose}) {",
    "  const get = (k,d) => localStorage.getItem(k) || d;",
    "  const [cpuWarn,  setCpuWarn]  = React.useState(get('thresh_cpu_warn',  '60'));",
    "  const [cpuCrit,  setCpuCrit]  = React.useState(get('thresh_cpu_crit',  '80'));",
    "  const [ramWarn,  setRamWarn]  = React.useState(get('thresh_ram_warn',  '70'));",
    "  const [ramCrit,  setRamCrit]  = React.useState(get('thresh_ram_crit',  '85'));",
    "  const [dsWarn,   setDsWarn]   = React.useState(get('thresh_ds_warn',   '70'));",
    "  const [dsCrit,   setDsCrit]   = React.useState(get('thresh_ds_crit',   '85'));",
    "  const [snapWarn, setSnapWarn] = React.useState(get('thresh_snap_warn', '7'));",
    "  const [snapCrit, setSnapCrit] = React.useState(get('thresh_snap_crit', '30'));",
    "  const [saved,    setSaved]    = React.useState(false);",
    "  function validate(v,min,max){ const n=parseInt(v); return !isNaN(n)&&n>=min&&n<=max; }",
    "  function handleSave(){",
    "    if(!validate(cpuWarn,1,99)||!validate(cpuCrit,1,99)||parseInt(cpuWarn)>=parseInt(cpuCrit)) return alert('CPU: Warning must be less than Critical, both 1-99%');",
    "    if(!validate(ramWarn,1,99)||!validate(ramCrit,1,99)||parseInt(ramWarn)>=parseInt(ramCrit)) return alert('RAM: Warning must be less than Critical, both 1-99%');",
    "    if(!validate(dsWarn,1,99)||!validate(dsCrit,1,99)||parseInt(dsWarn)>=parseInt(dsCrit)) return alert('Datastore: Warning must be less than Critical, both 1-99%');",
    "    if(!validate(snapWarn,1,3650)||!validate(snapCrit,1,3650)||parseInt(snapWarn)>=parseInt(snapCrit)) return alert('Snapshot: Warning must be less than Critical (1-3650 days)');",
    "    localStorage.setItem('thresh_cpu_warn',cpuWarn); localStorage.setItem('thresh_cpu_crit',cpuCrit);",
    "    localStorage.setItem('thresh_ram_warn',ramWarn); localStorage.setItem('thresh_ram_crit',ramCrit);",
    "    localStorage.setItem('thresh_ds_warn',dsWarn);   localStorage.setItem('thresh_ds_crit',dsCrit);",
    "    localStorage.setItem('thresh_snap_warn',snapWarn); localStorage.setItem('thresh_snap_crit',snapCrit);",
    "    localStorage.setItem('thresh_used_warn',dsWarn); localStorage.setItem('thresh_used_crit',dsCrit);",
    "    setSaved(true); setTimeout(()=>{ setSaved(false); onClose(true); }, 900);",
    "  }",
    "  function handleReset(){",
    "    ['thresh_cpu_warn','thresh_cpu_crit','thresh_ram_warn','thresh_ram_crit','thresh_ds_warn','thresh_ds_crit','thresh_snap_warn','thresh_snap_crit','thresh_used_warn','thresh_used_crit'].forEach(k=>localStorage.removeItem(k));",
    "    setCpuWarn('60');setCpuCrit('80');setRamWarn('70');setRamCrit('85');setDsWarn('70');setDsCrit('85');setSnapWarn('7');setSnapCrit('30');",
    "  }",
    "  const rS={display:'flex',gap:8,alignItems:'center',padding:'10px 14px',borderRadius:8,background:'#ffffff06',border:'1px solid #ffffff10',marginBottom:8};",
    "  const iS={width:64,textAlign:'center',padding:'5px 6px',borderRadius:6,border:'1px solid #ffffff20',background:'#ffffff0c',color:'#f1f5f9',fontSize:14,fontWeight:700};",
    "  const Bdg=({label,color})=><span style={{fontSize:9,fontWeight:700,padding:'1px 5px',borderRadius:8,background:color+'20',color,border:'1px solid '+color+'40',display:'block',marginBottom:3}}>{label}</span>;",
    "  const Cat=({lbl,title,sub,warnVal,warnSet,critVal,critSet,unit})=>(",
    "    <div style={rS}>",
    "      <div style={{flex:'0 0 155px',display:'flex',alignItems:'center',gap:8}}>",
    "        <span style={{fontSize:11,fontWeight:800,color:p.textMute,letterSpacing:'.5px',minWidth:34,textAlign:'center',padding:'2px 4px',borderRadius:4,background:p.border+'40'}}>{lbl}</span>",
    "        <div><div style={{fontWeight:700,fontSize:12,color:p.text}}>{title}</div><div style={{fontSize:10,color:p.textMute}}>{sub}</div></div>",
    "      </div>",
    "      <div style={{display:'flex',gap:12,alignItems:'center',flex:1,justifyContent:'center'}}>",
    "        <div style={{textAlign:'center'}}><Bdg label='WARN' color='#f59e0b'/><input style={iS} type='number' min='1' max={unit==='days'?3650:99} value={warnVal} onChange={e=>warnSet(e.target.value)}/><div style={{fontSize:10,color:p.textMute,marginTop:2}}>{unit}</div></div>",
    "        <span style={{color:p.textMute}}>&#8594;</span>",
    "        <div style={{textAlign:'center'}}><Bdg label='CRIT' color='#ef4444'/><input style={iS} type='number' min='1' max={unit==='days'?3650:99} value={critVal} onChange={e=>critSet(e.target.value)}/><div style={{fontSize:10,color:p.textMute,marginTop:2}}>{unit}</div></div>",
    "      </div>",
    "      <div style={{flex:'0 0 80px',textAlign:'right',fontSize:10}}>",
    "        <div style={{color:'#f59e0b',fontWeight:700}}>&#8805;{warnVal}{unit==='days'?'d':'%'} = yellow</div>",
    "        <div style={{color:'#ef4444',fontWeight:700,marginTop:2}}>&#8805;{critVal}{unit==='days'?'d':'%'} = red</div>",
    "      </div>",
    "    </div>",
    "  );",
    "  return(",
    "    <div style={{position:'fixed',inset:0,background:'#00000075',zIndex:9999,display:'flex',alignItems:'center',justifyContent:'center',padding:16}} onClick={e=>{if(e.target===e.currentTarget)onClose(false);}}>",
    "      <div style={{background:p.panel,border:'1px solid #a78bfa40',borderRadius:14,width:'100%',maxWidth:540,boxShadow:'0 24px 80px #0009',overflow:'hidden'}}>",
    "        <div style={{padding:'14px 20px',borderBottom:`1px solid ${p.border}`,background:'linear-gradient(135deg,#a78bfa14,transparent)',display:'flex',alignItems:'center',gap:10}}>",
    "          <div style={{width:36,height:36,borderRadius:9,background:'#a78bfa18',border:'1px solid #a78bfa30',display:'flex',alignItems:'center',justifyContent:'center',fontSize:16,flexShrink:0}}>&#9881;</div>",
    "          <div><div style={{fontWeight:800,fontSize:15,color:p.text}}>Threshold Settings</div>",
    "          <div style={{fontSize:10,color:p.textMute}}>Configure alert thresholds &#8212; drives all VMware colour indicators</div></div>",
    "          <button onClick={()=>onClose(false)} style={{marginLeft:'auto',background:'none',border:'none',color:p.textMute,fontSize:18,cursor:'pointer',padding:'2px 6px'}}>&#10005;</button>",
    "        </div>",
    "        <div style={{padding:'16px 20px'}}>",
    "          <div style={{fontSize:11,color:'#a78bfa',marginBottom:12,padding:'7px 10px',background:'#a78bfa0a',borderRadius:6,border:'1px solid #a78bfa20'}}>",
    "            Set <b>Warning</b> (yellow) and <b>Critical</b> (red) thresholds. Saved in browser &#8212; takes effect next render.",
    "          </div>",
    "          <Cat lbl='CPU'  title='CPU Usage'       sub='% utilised'          warnVal={cpuWarn}  warnSet={setCpuWarn}  critVal={cpuCrit}  critSet={setCpuCrit}  unit='%'/>",
    "          <Cat lbl='RAM'  title='RAM Usage'       sub='% utilised'          warnVal={ramWarn}  warnSet={setRamWarn}  critVal={ramCrit}  critSet={setRamCrit}  unit='%'/>",
    "          <Cat lbl='DS'   title='Datastore'       sub='% capacity used'     warnVal={dsWarn}   warnSet={setDsWarn}   critVal={dsCrit}   critSet={setDsCrit}   unit='%'/>",
    "          <Cat lbl='SNAP' title='Snapshot Age'    sub='days since creation'  warnVal={snapWarn} warnSet={setSnapWarn} critVal={snapCrit} critSet={setSnapCrit} unit='days'/>",
    "        </div>",
    "        <div style={{padding:'12px 20px',borderTop:`1px solid ${p.border}`,display:'flex',gap:8,justifyContent:'space-between',alignItems:'center'}}>",
    "          <button className='btn btn-ghost btn-sm' onClick={handleReset}>Reset Defaults</button>",
    "          <div style={{display:'flex',gap:8}}>",
    "            <button className='btn btn-ghost btn-sm' onClick={()=>onClose(false)}>Cancel</button>",
    "            <button className='btn btn-primary btn-sm' onClick={handleSave} style={{fontWeight:700,minWidth:120}} disabled={saved}>{saved?'Saved!':'Save Thresholds'}</button>",
    "          </div>",
    "        </div>",
    "      </div>",
    "    </div>",
    "  );",
    "}",
    "",
  ];
  lines.splice(vIdx, 0, ...modal);
  changes++;
  console.log('[3] ThresholdModal inserted (' + modal.length + ' lines)');
}

// Re-find VMwarePage (may have shifted after splice)
let vmPageStart = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].startsWith('function VMwarePage(')) { vmPageStart = i; break; }
}
console.log('VMwarePage at line', vmPageStart+1);

// ── 4a. thresholdOpen state ──
const hasState = lines.slice(vmPageStart, vmPageStart+35).some(l => l.includes('thresholdOpen'));
if (hasState) {
  console.log('[4a] thresholdOpen state already exists');
} else {
  let sIdx = -1;
  for (let i = vmPageStart; i < vmPageStart+35; i++) {
    if (lines[i].includes('const [topoTarget,setTopoTarget]')) { sIdx = i; break; }
  }
  if (sIdx < 0) { console.log('ERROR: topoTarget state not found'); process.exit(1); }
  lines.splice(sIdx + 1, 0, "  const [thresholdOpen, setThresholdOpen] = useState(false);");
  changes++;
  console.log('[4a] thresholdOpen state added after line', sIdx+1);
}

// ── 4b. ThresholdModal render ──
const hasRender = lines.slice(vmPageStart, vmPageStart+300).some(l => l.includes('thresholdOpen&&<ThresholdModal'));
if (hasRender) {
  console.log('[4b] ThresholdModal render already exists');
} else {
  let trIdx = -1;
  for (let i = vmPageStart; i < vmPageStart+300; i++) {
    if (lines[i].includes('{topoTarget&&<TopologyModal')) { trIdx = i; break; }
  }
  if (trIdx < 0) { console.log('ERROR: TopologyModal render not found'); process.exit(1); }
  lines.splice(trIdx + 1, 0, "      {thresholdOpen&&<ThresholdModal p={p} onClose={()=>setThresholdOpen(false)}/>}");
  changes++;
  console.log('[4b] ThresholdModal render added after line', trIdx+1);
}

// ── 4c. Threshold card in actions tab ──
const hasCard = lines.some(l => l.includes('Threshold Settings card - admin only'));
if (hasCard) {
  console.log('[4c] Threshold card already exists');
} else {
  let smIdx = -1;
  for (let i = vmPageStart; i < vmPageStart+1000; i++) {
    if (lines[i] && lines[i].toLowerCase().includes('summary of current vmware')) { smIdx = i; break; }
  }
  if (smIdx < 0) { console.log('ERROR: footprint summary not found'); process.exit(1); }
  console.log('[4c] Inserting threshold card before line', smIdx+1);
  const card = [
    "            {/* Threshold Settings card - admin only */}",
    "            {isAdmin&&(",
    "            <div className='card' style={{border:'1px solid #a78bfa30',borderTop:'3px solid #a78bfa'}}>",
    "              <div style={{padding:'16px 18px'}}>",
    "                <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:12}}>",
    "                  <div style={{width:36,height:36,borderRadius:9,background:'#a78bfa18',border:'1px solid #a78bfa30',display:'flex',alignItems:'center',justifyContent:'center',fontSize:16,flexShrink:0}}>&#9881;</div>",
    "                  <div style={{flex:1}}>",
    "                    <div style={{fontWeight:800,fontSize:14,color:'#a78bfa'}}>Threshold Settings</div>",
    "                    <div style={{fontSize:11,color:p.textMute,marginTop:1}}>CPU &#183; RAM &#183; Datastore &#183; Snapshot age alert thresholds</div>",
    "                  </div>",
    "                  <span style={{fontSize:10,fontWeight:700,padding:'2px 8px',borderRadius:10,background:'#a78bfa15',color:'#a78bfa',border:'1px solid #a78bfa30'}}>ADMIN</span>",
    "                </div>",
    "                <div style={{fontSize:12,color:p.textMute,marginBottom:14,padding:'8px 10px',background:'#a78bfa07',borderRadius:6,border:'1px solid #a78bfa18'}}>",
    "                  Configure warning &amp; critical thresholds for CPU, RAM, Datastore usage (%) and Snapshot age (days). Drives all colour indicators across VMware views.",
    "                </div>",
    "                <button className='btn btn-sm' style={{width:'100%',fontWeight:700,background:'#a78bfa18',border:'1px solid #a78bfa40',color:'#a78bfa'}} onClick={()=>setThresholdOpen(true)}>&#9881; Open Threshold Settings</button>",
    "              </div>",
    "            </div>",
    "            )}",
  ];
  lines.splice(smIdx, 0, ...card);
  changes++;
  console.log('[4c] Threshold card inserted');
}

console.log('\nTotal changes:', changes);
fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
