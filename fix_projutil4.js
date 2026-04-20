const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
let n = 0;

// Find fmtInr function dynamically and fix the Cr tier
let fmtInrStart = -1;
for (let i = 6870; i < 6900; i++) {
  if (lines[i] && lines[i].includes('const fmtInr')) { fmtInrStart = i; break; }
}
console.log('fmtInr starts at line', fmtInrStart+1);
for (let i = fmtInrStart; i < fmtInrStart + 10; i++) console.log((i+1)+': '+lines[i]);

// Find the guard line and 10M line
let guardIdx = -1, crIdx = -1;
for (let i = fmtInrStart; i < fmtInrStart + 8; i++) {
  if (lines[i] && lines[i].includes("if (!v || v===0)")) guardIdx = i;
  if (lines[i] && lines[i].includes('10000000') && lines[i].includes('toFixed')) crIdx = i;
}
console.log('guardIdx:', guardIdx+1, 'crIdx:', crIdx+1);

if (crIdx >= 0 && lines[crIdx].includes('toFixed(2)')) {
  // Replace the Cr line to use rounded value
  lines[crIdx] = lines[crIdx].replace(
    '`\u20b9${(v/10000000).toFixed(2)}Cr`',
    '`\u20b9${(Math.round(Math.round(v/usdRate)*usdRate)/10000000).toFixed(1)}Cr`'
  );
  console.log('OK fmtInr Cr fixed');
  n++;
}
// Insert the ru/rv line after guard
if (guardIdx >= 0 && !lines[guardIdx+1].includes('const ru=')) {
  lines.splice(guardIdx + 1, 0, '    const ru=Math.round(v/usdRate), rv=Math.round(ru*usdRate);');
  console.log('OK inserted ru/rv');
  n++;
}

fs.writeFileSync(path, lines.join(EOL));
console.log('Changes:', n);
