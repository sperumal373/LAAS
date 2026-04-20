const fs = require('fs');
const filePath = 'C:/caas-dashboard/frontend/src/App.jsx';
const raw = fs.readFileSync(filePath, 'utf8');
const lines = raw.split('\r\n');

// Lines 12736-12739 (indexes 12735-12738) are corrupted VMRequestForm render
// Need to replace them with the clean version

console.log('Lines 12736-12739:');
for (let i = 12735; i <= 12739; i++) console.log((i+1)+':', JSON.stringify(lines[i]));

// Verify line 12736 starts with the corrupted fragment
if (!lines[12735].includes('{vvmwareOnly') && !lines[12735].includes('vmwareOnly={vmReqVmwareOnly}')) {
  // Check if these are different lines
  for(let i=12730;i<12745;i++) console.log((i+1)+':', lines[i].substring(0,100));
  process.exit(1);
}

// Replace lines 12736-12739 with clean VMRequestForm render
const cleanRender = [
  '      {vmReqModal&&<VMRequestForm vcenters={vcenters} currentUser={currentUser} ocpData={ocpData} nutData={nutData} p={p}',
  '        vmwareOnly={vmReqVmwareOnly}',
  '        onClose={()=>{ setVmReqModal(false); setVmReqVmwareOnly(false); }}',
  '        onSubmitted={()=>{ setVmReqModal(false); setVmReqVmwareOnly(false); setPage("requests"); }}/>}',
];

// Splice in replacement (lines 12736-12739 = indexes 12735-12738 = 4 lines)
lines.splice(12735, 4, ...cleanRender);

const newContent = lines.join('\r\n');
fs.writeFileSync(filePath + '.bak6', raw, 'utf8');
fs.writeFileSync(filePath, newContent, 'utf8');

console.log('Fixed VMRequestForm render');
console.log('New total lines:', lines.length);

// Verify
const vLines = newContent.split('\r\n');
console.log('Double-checking lines 12735-12740:');
for (let i = 12733; i <= 12740; i++) console.log((i+1)+':', JSON.stringify(vLines[i]));
console.log('DONE');
