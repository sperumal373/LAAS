const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);

let changes = 0;

// Fix 1: Header button (line 13052, 0-indexed 13051)
// onClick={()=>setVmReqModal(true)}  onClick={()=>{ setVmReqVmwareOnly(page==="vms"); setVmReqModal(true); }}
const idx1 = 13051;
if (lines[idx1].includes('setVmReqModal(true)') && lines[idx1].includes('Request VM') && lines[idx1].includes('btn-primary')) {
  lines[idx1] = lines[idx1].replace(
    'onClick={()=>setVmReqModal(true)}',
    'onClick={()=>{ setVmReqVmwareOnly(page==="vms"); setVmReqModal(true); }}'
  );
  console.log(' Fix 1 (header button):', lines[idx1].trim().substring(0, 100));
  changes++;
} else {
  console.log(' Fix 1 not matched. Line:', lines[idx1].trim());
}

// Fix 2: VMwarePage onCreateVM callback (line 13098, 0-indexed 13097)
const idx2 = 13097;
if (lines[idx2].includes('VMwarePage') && lines[idx2].includes('onCreateVM={()=>setVmReqModal(true)}')) {
  lines[idx2] = lines[idx2].replace(
    'onCreateVM={()=>setVmReqModal(true)}',
    'onCreateVM={()=>{ setVmReqVmwareOnly(true); setVmReqModal(true); }}'
  );
  console.log(' Fix 2 (VMwarePage onCreateVM):', 'replaced');
  changes++;
} else {
  console.log(' Fix 2 not matched. Searching...');
  // Scan for the exact line
  for (let i = 13090; i < 13110; i++) {
    if (lines[i].includes('VMwarePage') && lines[i].includes('onCreateVM')) {
      lines[i] = lines[i].replace(
        'onCreateVM={()=>setVmReqModal(true)}',
        'onCreateVM={()=>{ setVmReqVmwareOnly(true); setVmReqModal(true); }}'
      );
      console.log(' Fix 2 found at line', i+1);
      changes++;
      break;
    }
  }
}

if (changes === 2) {
  fs.writeFileSync(path, lines.join(EOL));
  console.log('\n Both fixes applied');
} else {
  console.log('\n Only', changes, 'of 2 fixes applied  writing anyway');
  fs.writeFileSync(path, lines.join(EOL));
}
