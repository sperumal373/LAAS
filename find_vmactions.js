const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
// Find VMwarePage / VMware Infrastructure
let si = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('function VMwarePage') || lines[i].includes('function VmwarePage')) { si = i; break; }
}
console.log('VMwarePage at line', si+1);
// Find action menu / VM actions
for (let i = si; i < si + 800; i++) {
  const l = lines[i];
  if (l.includes('Power On') || l.includes('Power Off') || l.includes('Reboot') || l.includes('actMenu') || l.includes('actionMenu') || l.includes('vmAction') || l.includes('VM Actions') || l.includes('vm-actions')) {
    console.log((i+1) + ': ' + l.trim().substring(0, 120));
  }
}
