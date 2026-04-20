const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
// Find VMwarePage and check its area for the footprint section
let si = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].startsWith('function VMwarePage(')) { si = i; break; }
}
console.log('VMwarePage at', si+1);
// Search for footprint section 
for (let i = si; i < si + 900; i++) {
  const l = lines[i];
  if (l.includes('Footprint') || l.includes('footprint') || l.includes('Current VMware') || l.includes('Actions tab')) {
    console.log((i+1) + ': ' + l.trim().substring(0,100));
  }
}
