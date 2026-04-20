const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);

const idx = 5383; // 0-indexed line 5384
console.log('Before:', lines[idx].trim());
if (!lines[idx].includes("d?.projects")) { console.error("Pattern not found"); process.exit(1); }
lines[idx] = lines[idx].replace("(d?.projects||[]).map(pr=>pr.tag||pr.name)", "(d?.tags||[]).map(t=>t.tag)");
console.log('After: ', lines[idx].trim());
fs.writeFileSync(path, lines.join(EOL));
console.log('Done');
