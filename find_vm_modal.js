const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
// Find VMRequestModal and platform selector
let hits = [];
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('VMRequestModal') || lines[i].includes('Platform Selector') || 
      lines[i].includes('vmwareOnly') || lines[i].includes('onCreateVM') ||
      (lines[i].includes('platform') && lines[i].includes('openshift') && lines[i].includes('nutanix'))) {
    hits.push((i+1) + ': ' + lines[i].trim());
  }
}
console.log(hits.slice(0, 40).join('\n'));
