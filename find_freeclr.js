const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
// Find freeClr definition
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('function freeClr') || lines[i].includes('const freeClr') || lines[i].includes('freeClr=')) {
    console.log((i+1) + ': ' + lines[i].trim());
  }
}
// Find where thresholds are actually referenced for colors in datastores/hosts
for (let i = 0; i < lines.length; i++) {
  const l = lines[i];
  if ((l.includes('freeClr') || l.includes('85') || l.includes('75')) && (l.includes('used_pct') || l.includes('cpu') || l.includes('ram'))) {
    if (i < 2500) console.log((i+1) + ': ' + l.trim().substring(0,120));
  }
}
