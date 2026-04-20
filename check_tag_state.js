const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const lines = src.split('\r\n');

// Find the comment and g2 div boundaries
let startLine = -1, endLine = -1;
for (let i = 5660; i < 5730; i++) {
  if (lines[i] && lines[i].includes('Tag selector') && lines[i].includes('VMware tags')) startLine = i;
  if (startLine > 0 && lines[i] && lines[i].includes('g2')) { endLine = i; break; }
}
console.log('startLine:', startLine+1, 'endLine:', endLine+1);
for (let i = startLine; i < endLine + 2; i++) console.log((i+1) + ': ' + JSON.stringify(lines[i]));
