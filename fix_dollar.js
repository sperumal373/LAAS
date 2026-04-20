const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
const idx = 6889; // line 6890
console.log('Before:', lines[idx]);
lines[idx] = lines[idx].replace('return `${u.toLocaleString("en-US")}`;', 'return `$${u.toLocaleString("en-US")}`;');
console.log('After: ', lines[idx]);
fs.writeFileSync(path, lines.join(EOL));
