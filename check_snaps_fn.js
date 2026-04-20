const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/backend/vmware_client.py', 'utf8');
const lines = c.split('\n');
// Find _snapshots function and its end
let start = -1, end = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('def _snapshots(')) start = i;
  if (start > 0 && end < 0 && i > start + 3 && lines[i].match(/^def /)) { end = i; break; }
}
console.log('_snapshots: lines', start+1, '-', end);
for (let i = start; i < end; i++) console.log((i+1) + ': ' + lines[i]);
