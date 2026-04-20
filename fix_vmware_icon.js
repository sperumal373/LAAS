
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// ── 1. Add img prop to VMware nav item ──
let vmNavIdx = -1;
for (let i = 11805; i < 11825; i++) {
  if (lines[i] && lines[i].includes('"vms"') && lines[i].includes('VMware')) {
    vmNavIdx = i; break;
  }
}
if (vmNavIdx < 0) { console.log('ERROR: not found'); process.exit(1); }
console.log('VMware nav at line', vmNavIdx+1);

// Remove any previous img prop first, then add fresh
lines[vmNavIdx] = lines[vmNavIdx].replace(/,?\s*img:"[^"]*"/, '');
lines[vmNavIdx] = lines[vmNavIdx].replace(
  'roles:["admin","operator","viewer"]}',
  'img:"/vmware-logo.jpg", roles:["admin","operator","viewer"]}'
);
console.log('Set img prop:', lines[vmNavIdx].trim().substring(0,120));

// ── 2. Update nav rendering: use img as a small icon (22x22) beside label ──
let iconLineIdx = -1;
for (let i = 11840; i < 11870; i++) {
  if (lines[i] && (lines[i].includes('{n.icon}') || lines[i].includes('n.img?'))) {
    iconLineIdx = i; break;
  }
}
if (iconLineIdx < 0) { console.log('ERROR: icon line not found'); process.exit(1); }
console.log('Icon line at', iconLineIdx+1, ':', lines[iconLineIdx].trim().substring(0,80));
console.log('Next line  at', iconLineIdx+2, ':', lines[iconLineIdx+1].trim().substring(0,80));

// Restore to original two clean lines — icon span then label span,
// but icon span now conditionally renders <img> or emoji
lines[iconLineIdx]   = "             <span style={{fontSize:n.sub?13:16,width:22,height:22,textAlign:'center',flexShrink:0,lineHeight:1,display:'flex',alignItems:'center',justifyContent:'center'}}>{n.img?<img src={n.img} alt='' style={{width:20,height:20,objectFit:'contain',borderRadius:2,display:'block'}}/>:n.icon}</span>";
lines[iconLineIdx+1] = "             <span style={{flex:1,fontSize:n.sub?12:undefined,color:n.sub&&page!==n.id?p.textSub:undefined}}>{n.label}</span>";

console.log('Nav icon rendering updated — 20x20 logo icon beside VMware label');

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
