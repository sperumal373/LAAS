const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('Summary of current VMware Footprint')) console.log((i+1) + ': ' + lines[i].trim());
  if (lines[i].includes('ThresholdModal')) console.log('THRESH ' + (i+1) + ': ' + lines[i].trim().substring(0,80));
}
