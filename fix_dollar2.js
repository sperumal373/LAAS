const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
// Directly set - avoid replace() dollar interpretation
lines[6889] = '    return `$' + '${u.toLocaleString("en-US")}`;';
console.log('Set:', JSON.stringify(lines[6889]));
fs.writeFileSync(path, lines.join(EOL));
