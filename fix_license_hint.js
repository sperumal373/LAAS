const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
const idx = 5660;
console.log('Line:', JSON.stringify(lines[idx]).substring(0,150));
// Replace the specific part
const before = '\u20b9{Number(inr).toLocaleString("en-IN")}/VM/mo &nbsp;/&nbsp; ${(inr/usd).toFixed(0)}/VM/mo';
const after   = '${Math.round(inr/usd)}/VM/mo \u2014 \u20b9{Math.round(Math.round(inr/usd)*usd).toLocaleString("en-IN")}/VM/mo';
if (lines[idx].includes(before)) {
  lines[idx] = lines[idx].replace(before, after);
  console.log('Fixed!');
  fs.writeFileSync(path, lines.join(EOL));
} else {
  // Try finding the &nbsp; encoded as HTML entity in source
  const idx2 = lines.findIndex((l,i) => i > 5650 && i < 5680 && l.includes('inr/usd') && l.includes('toFixed(0)') && l.includes('VM/mo'));
  console.log('Alt search at:', idx2+1, JSON.stringify(lines[idx2]).substring(0,150));
  if (idx2 >= 0) {
    lines[idx2] = lines[idx2].replace(
      /\u20b9\{Number\(inr\)\.toLocaleString\("en-IN"\)\}\/VM\/mo.*\$\{\(inr\/usd\)\.toFixed\(0\)\}\/VM\/mo/,
      '${Math.round(inr/usd)}/VM/mo \u2014 \u20b9{Math.round(Math.round(inr/usd)*usd).toLocaleString("en-IN")}/VM/mo'
    );
    fs.writeFileSync(path, lines.join(EOL));
    console.log('Fixed via regex!');
  }
}
