const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
let n = 0;

// fmtInr: add the ru/rv variables right after the guard line
// Line 6879 (0-indexed 6878) is "const fmtInr = (v)=>{"
// Line 6880 (0-indexed 6879) is "if (!v || v===0) return "";"
// Line 6881 (0-indexed 6880) is the 10000000 line
// We need to insert after line 6880 (0-indexed 6879): two new lines
const guardIdx = 6879; // 0-indexed
if (lines[guardIdx].includes('if (!v || v===0)')) {
  // Insert ru/rv computation after the guard
  lines.splice(guardIdx + 1, 0,
    '    const ru=Math.round(v/usdRate), rv=Math.round(ru*usdRate);',
    '    if (rv>=10000000) return `\u20b9${(rv/10000000).toFixed(1)}Cr`;'
  );
  // Remove the old 10000000 line (now shifted by 2)
  const crLineIdx = guardIdx + 3; // was guardIdx+1, now shifted +2
  if (lines[crLineIdx] && lines[crLineIdx].includes('10000000') && lines[crLineIdx].includes('toFixed(2)')) {
    lines.splice(crLineIdx, 1);
    console.log('OK fmtInr Cr line replaced');
    n++;
  } else {
    console.log('Cr line at ' + (crLineIdx+1) + ': ' + (lines[crLineIdx]||'').trim());
  }
  console.log('OK fmtInr ru/rv inserted');
  n++;
} else {
  console.log('XX fmtInr guard not at 6880: ' + lines[guardIdx].trim());
}

// PDF row USD primary/secondary - check actual content
for (let i = 7100; i < 7130; i++) {
  if (lines[i] && lines[i].includes('fmtInr(r.chargeback_inr)') && lines[i].includes('color:#16a34a')) {
    console.log('Found PDF INR row at ' + (i+1) + ': ' + lines[i].trim().substring(0,80));
    lines[i] = lines[i]
      .replace('color:#16a34a;font-weight:600', 'color:#16a34a;font-weight:700')
      .replace('fmtInr(r.chargeback_inr)', 'fmtUsd(r.chargeback_inr)');
    console.log('OK PDF row USD primary');
    n++;
  }
  if (lines[i] && lines[i].includes('fmtUsd(r.chargeback_inr)') && lines[i].includes('color:#6b7280')) {
    console.log('Found PDF USD row at ' + (i+1) + ': ' + lines[i].trim().substring(0,80));
    lines[i] = lines[i].replace('fmtUsd(r.chargeback_inr)', 'fmtInr(r.chargeback_inr)');
    console.log('OK PDF row INR secondary');
    n++;
  }
}

fs.writeFileSync(path, lines.join(EOL));
console.log('\nTotal:', n);
