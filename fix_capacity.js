// fix_capacity.js — Fix CapacityPage issues:
// 1. Add summaries prop to function signature (line 2613)
// 2. Fix corrupted KPI div at lines 2727-2742
// 3. Add summaries={summaries} to render call

const fs = require('fs');
const path = require('path');
const filePath = path.resolve('C:/caas-dashboard/frontend/src/App.jsx');

const raw = fs.readFileSync(filePath, 'utf8');
let content = raw;

// ---- FIX 1: Add summaries to function signature ----
const oldSig = 'function CapacityPage({hosts,datastores,vcenters,selectedVC,currentUser,onRefresh,loading,error,onRetry,ocpData,nutData,p}){';
const newSig = 'function CapacityPage({hosts,datastores,vcenters,selectedVC,currentUser,onRefresh,loading,error,onRetry,ocpData,nutData,summaries,p}){';

if (content.includes(oldSig)) {
  content = content.replace(oldSig, newSig);
  console.log('FIX 1: Added summaries to CapacityPage signature');
} else {
  console.error('FIX 1 FAILED: Could not find signature');
}

// ---- FIX 2: Fix corrupted KPI section ----
// The corrupted section is lines 2727-2742 (0-indexed: 2726-2741)
// Original should be: <div style={{display:"flex",...}}> with KPI components
// It was corrupted to: <d{(()=>{ ... })()}
// After the IIFE ends at line 2741: })()}, line 2742 has a duplicate KPI

const lines = content.split('\r\n');
const N = lines.length;

// Find the corrupted line
let corruptLine = -1;
for (let i = 0; i < N; i++) {
  if (lines[i].includes('<d{(()=>')) {
    corruptLine = i;
    break;
  }
}

if (corruptLine === -1) {
  console.error('FIX 2 FAILED: Could not find corrupted line <d{(()=>');
} else {
  console.log('FIX 2: Found corrupted line at', corruptLine + 1);
  
  // Find the end of the IIFE block (})()})
  let iifeEnd = -1;
  let duplicateKPI = -1;
  for (let i = corruptLine; i < Math.min(corruptLine + 30, N); i++) {
    if (lines[i].includes('})()}')){
      iifeEnd = i;
    }
    // The duplicate KPI line after the IIFE
    if (i > corruptLine && lines[i].includes('label=\\"Storage Free\\"') && lines[i].includes('<KPI')) {
      duplicateKPI = i;
    }
  }
  
  console.log('IIFE ends at:', iifeEnd + 1);
  console.log('Duplicate KPI at:', duplicateKPI + 1);
  
  // Extract the IIFE content (the new KPI computations + components)
  // Lines between corruptLine+1 and iifeEnd-1 contain: const totalCPU, usedCPU, cpuFreePct, totalVMs, runVMs, return(<>...)
  // We want to keep the existing KPIs + add the new ones in a proper div
  
  // Build the replacement lines
  // The corrupted section (corruptLine to duplicateKPI, inclusive) should be replaced with:
  const kpiDivStyle = 'style={{display:"flex",flexWrap:"wrap",gap:10,marginBottom:16}}';
  
  const endLine = duplicateKPI !== -1 ? duplicateKPI : iifeEnd;
  
  // Build clean replacement
  const newKPIBlock = [
    `          <div ${kpiDivStyle}>`,
    `            {(()=>{`,
    `              const totalCPU=hosts.reduce((s,h)=>s+(h.cpu_total_mhz||0),0);`,
    `              const usedCPU=hosts.reduce((s,h)=>s+(h.cpu_used_mhz||0),0);`,
    `              const cpuFreePct=totalCPU>0?Math.round(((totalCPU-usedCPU)/totalCPU)*100):0;`,
    `              const totalVMs=summaries?summaries.reduce((s,v)=>s+(v.total_vms||0),0):0;`,
    `              const runVMs=summaries?summaries.reduce((s,v)=>s+(v.running_vms||0),0):0;`,
    `              return(<>`,
    `                <KPI icon="\uD83D\uDCCC\uFE0F" label="Total Hosts"  value={hosts.length} color={p.accent}/>`,
    `                <KPI icon="\uD83E\uDDE0" label="Memory Free"  value={fmtGB(fR)} color={freeClr((fR/tR)*100)} sub={\`of \${fmtGB(tR)}\`}/>`,
    `                <KPI icon="\uD83D\uDCBE" label="Datastores"   value={datastores.length} color={p.purple}/>`,
    `                <KPI icon="\uD83D\uDCE6" label="Storage Free" value={fmtGB(fD)} color={freeClr((fD/tD)*100)} sub={\`of \${fmtGB(tD)}\`}/>`,
    `                {totalVMs>0&&<KPI icon="\uD83D\uDDA5\uFE0F" label="VMs (On/Total)" value={\`\${runVMs}/\${totalVMs}\`} color={p.cyan} sub={\`\${totalVMs-runVMs} off\`}/>}`,
    `                {totalCPU>0&&<KPI icon="\u26A1" label="CPU Free" value={\`\${cpuFreePct}%\`} color={freeClr(cpuFreePct)} sub={\`\${Math.round(usedCPU/1000)}/\${Math.round(totalCPU/1000)} GHz\`}/>}`,
    `              </>);`,
    `            })()}`,
    `          </div>`,
  ];
  
  // Replace lines from corruptLine to endLine (inclusive)
  lines.splice(corruptLine, endLine - corruptLine + 1, ...newKPIBlock);
  content = lines.join('\r\n');
  console.log('FIX 2: Replaced corrupted KPI section with clean div+IIFE');
}

// ---- FIX 3: Add summaries to render call ----
const oldRender = 'initSearch={searchHL?.page===\"capacity\"?searchHL.term:\"\"} {...cp}/>}';
const newRender = 'initSearch={searchHL?.page===\"capacity\"?searchHL.term:\"\"} summaries={summaries} {...cp}/>}';

if (content.includes(oldRender)) {
  content = content.replace(oldRender, newRender);
  console.log('FIX 3: Added summaries={summaries} to CapacityPage render call');
} else {
  // Try alternate — the summaries prop might already be there
  if (content.includes('summaries={summaries}')) {
    console.log('FIX 3: summaries prop already present in render call');
  } else {
    console.error('FIX 3 FAILED: Could not find render call');
    // Debug: show what the render call looks like
    const rLines = content.split('\r\n');
    for (let i = 0; i < rLines.length; i++) {
      if (rLines[i].includes('CapacityPage') && rLines[i].includes('page===')) {
        console.log('Found at line', i+1, ':', rLines[i].substring(0, 200));
      }
    }
  }
}

// ---- Backup and write ----
fs.writeFileSync(filePath + '.bak4', fs.readFileSync(filePath, 'utf8'), 'utf8');
fs.writeFileSync(filePath, content, 'utf8');

// ---- Verify ----
const vLines = content.split('\r\n');
console.log('\nNew total lines:', vLines.length);

const countOf = (str) => { let c=0; for(const l of vLines) if(l.includes(str)) c++; return c; };
console.log('function CapacityPage (with summaries):', vLines[2612] ? vLines[2612].substring(0, 100) : 'N/A');
console.log('summaries prop in signature:', content.includes('summaries,p}){'));
console.log('summaries prop in render:', content.includes('summaries={summaries}'));
console.log('<d{(()=> corrupted lines:', countOf('<d{(()=>'));
console.log('KPI IIFE in vmware section:', countOf('totalCPU=hosts.reduce'));

console.log('\nDONE');
