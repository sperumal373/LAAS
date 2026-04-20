const fs = require('fs');
const path = 'C:/caas-dashboard/backend/main.py';
const src = fs.readFileSync(path, 'utf8');
const crlf = src.includes('\r\n');
const EOL = crlf ? '\r\n' : '\n';
const lines = src.split(EOL);
const idx = 293; // 0-indexed line 294
console.log('Before:', JSON.stringify(lines[idx]));
lines[idx] = '            key=(r.get("vm_name") or "")+"::"+(r.get("snapshot_name") or "")';
console.log('After:', JSON.stringify(lines[idx]));
fs.writeFileSync(path, lines.join(EOL));
console.log('Done');
