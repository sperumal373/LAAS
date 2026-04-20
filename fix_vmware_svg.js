
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// ── 1. Remove img prop from VMware nav item (clean up previous attempt) ──
let vmNavIdx = -1;
for (let i = 11805; i < 11825; i++) {
  if (lines[i] && lines[i].includes('"vms"') && lines[i].includes('VMware')) {
    vmNavIdx = i; break;
  }
}
if (vmNavIdx < 0) { console.log('ERROR: nav item not found'); process.exit(1); }
lines[vmNavIdx] = lines[vmNavIdx].replace(/,?\s*img:"[^"]*"/, '');
console.log('[1] VMware nav item cleaned at line', vmNavIdx+1);

// ── 2. Find icon rendering lines ──
let iconLineIdx = -1;
for (let i = vmNavIdx + 30; i < vmNavIdx + 70; i++) {
  if (lines[i] && (lines[i].includes('{n.icon}') || lines[i].includes('n.img?'))) {
    iconLineIdx = i; break;
  }
}
if (iconLineIdx < 0) { console.log('ERROR: icon line not found'); process.exit(1); }
console.log('[2] Icon line at', iconLineIdx+1);
console.log('    ', lines[iconLineIdx].trim().substring(0,80));
console.log('[3] Next line  at', iconLineIdx+2);
console.log('    ', lines[iconLineIdx+1].trim().substring(0,80));

// ── 3. Rewrite: n.id==='vms' renders inline SVG VMware logo, others render emoji ──
// The VMware interlocking rings logo as inline SVG:
// - Blue ring (upper-right): mask cuts out hole
// - Orange ring (lower-left): mask cuts out hole
// - Blue "front" slice painted over orange for interlocking effect
lines[iconLineIdx] = [
  "             {n.id==='vms'",
  "               ? <svg viewBox='0 0 100 100' style={{width:20,height:20,flexShrink:0,display:'block'}}>",
  "                   <defs>",
  "                     <mask id='vm-bm'><rect width='100' height='100' fill='white'/><rect x='37' y='20' width='32' height='32' rx='7' fill='black'/></mask>",
  "                     <mask id='vm-om'><rect width='100' height='100' fill='white'/><rect x='31' y='48' width='32' height='32' rx='7' fill='black'/></mask>",
  "                   </defs>",
  "                   <rect x='23' y='7' width='58' height='58' rx='13' fill='#7BAFD4' mask='url(#vm-bm)'/>",
  "                   <rect x='19' y='35' width='58' height='58' rx='13' fill='#F2964A' mask='url(#vm-om)'/>",
  "                   <rect x='19' y='35' width='26' height='30' rx='0' fill='#7BAFD4' mask='url(#vm-bm)'/>",
  "                 </svg>",
  "               : <span style={{fontSize:n.sub?13:16,width:22,textAlign:'center',flexShrink:0,lineHeight:1}}>{n.icon}</span>",
  "             }",
].join('\r\n');

// ── 4. Fix the label line (next line after icon) ──
lines[iconLineIdx + 1] = "             <span style={{flex:1,fontSize:n.sub?12:undefined,color:n.sub&&page!==n.id?p.textSub:undefined}}>{n.label}</span>";

console.log('[3] Nav VMware icon updated with inline SVG rings');

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
