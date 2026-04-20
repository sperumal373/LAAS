const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
let si = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('function AuditPage')) { si = i; break; }
}
console.log('AuditPage at line', si+1);
for (let i = si; i < si + 120; i++) console.log((i+1) + ': ' + lines[i]);
