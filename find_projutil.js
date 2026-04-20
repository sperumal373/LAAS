const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
let hits = [];
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('ProjectUtilization') || lines[i].includes('function ProjectUtil')) {
    hits.push((i+1) + ': ' + lines[i].trim().substring(0,100));
  }
}
console.log(hits.slice(0,20).join('\n'));
