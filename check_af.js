const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
let si = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('function AuditPage')) { si = i; break; }
}
// Check if actionFilter is declared in AuditPage
let found = false;
for (let i = si; i < si + 20; i++) {
  if (lines[i].includes('actionFilter')) { console.log('FOUND at line', i+1, ':', lines[i].trim()); found=true; }
}
if (!found) console.log('actionFilter NOT declared in first 20 lines of AuditPage');
// Search more broadly
for (let i = si; i < si + 100; i++) {
  if (lines[i].includes('actionFilter')) { console.log('Line', i+1, ':', lines[i].trim()); }
}
