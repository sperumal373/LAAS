
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// ── 1. Remove img prop from VMware nav item ──
let vmNavIdx = -1;
for (let i = 11800; i < 11840; i++) {
  if (lines[i] && lines[i].includes('"vms"') && lines[i].includes('VMware')) {
    vmNavIdx = i; break;
  }
}
if (vmNavIdx < 0) { console.log('ERROR: VMware nav item not found'); process.exit(1); }
console.log('VMware nav at line', vmNavIdx+1);
// Remove img prop (with or without base64 or file path)
lines[vmNavIdx] = lines[vmNavIdx].replace(/,?\s*img:"[^"]*"/, '');
console.log('Removed img prop:', lines[vmNavIdx].trim().substring(0,120));

// ── 2. Restore nav div style (remove n.img padding override) ──
for (let i = vmNavIdx; i < vmNavIdx + 60; i++) {
  if (lines[i] && lines[i].includes("n.img?{padding:'6px 10px'}")) {
    lines[i] = lines[i].replace(/:n\.img\?\{padding:'6px 10px'\}/, '');
    console.log('Restored nav div style at line', i+1);
    break;
  }
}

// ── 3. Restore original icon + label rendering (remove n.img ternary) ──
for (let i = vmNavIdx; i < vmNavIdx + 60; i++) {
  if (lines[i] && lines[i].includes('n.img?') && lines[i].includes('<img')) {
    const nextLine = i + 1;
    // Restore original two lines
    lines[i]      = "             <span style={{fontSize:n.sub?13:16,width:22,textAlign:'center',flexShrink:0,lineHeight:1}}>{n.icon}</span>";
    lines[nextLine] = "             <span style={{flex:1,fontSize:n.sub?12:undefined,color:n.sub&&page!==n.id?p.textSub:undefined}}>{n.label}</span>";
    console.log('Restored icon+label rendering at lines', i+1, '&', nextLine+1);
    break;
  }
}

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Done. All VMware nav changes reverted.');
