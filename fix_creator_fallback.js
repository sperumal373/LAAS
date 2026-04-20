const fs = require('fs');
const path = 'C:/caas-dashboard/backend/main.py';
const src = fs.readFileSync(path, 'utf8');
const crlf = src.includes('\r\n');
const EOL = crlf ? '\r\n' : '\n';
const lines = src.split(EOL);
const idx = 294; // 0-indexed line 295
console.log('Before:', lines[idx]);
// Change: r["created_by"]=creator_map.get(key,"")
// To:     r["created_by"]=r.get("created_by") or creator_map.get(key,"")
lines[idx] = '            r["created_by"]=r.get("created_by") or creator_map.get(key,"")';
console.log('After: ', lines[idx]);
fs.writeFileSync(path, lines.join(EOL));
console.log('Done');
