
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

const b64 = fs.readFileSync('C:/caas-dashboard/vmware_b64.txt', 'utf8').trim();
const dataUri = 'data:image/jpeg;base64,' + b64;

// ── 1. Update VMware nav item: replace img path with base64 data URI ──
let vmNavIdx = -1;
for (let i = 11800; i < 11835; i++) {
  if (lines[i] && lines[i].includes('id:"vms"') && lines[i].includes('label:"VMware"')) {
    vmNavIdx = i; break;
  }
}
if (vmNavIdx < 0) { console.log('ERROR: VMware nav item not found'); process.exit(1); }
console.log('VMware nav item at line', vmNavIdx+1);

// Replace whatever img value is there (or add it if not present) with data URI
if (lines[vmNavIdx].includes('img:')) {
  // Replace existing img value
  lines[vmNavIdx] = lines[vmNavIdx].replace(/img:"[^"]*"/, 'img:"__IMGURI__"');
} else {
  // Add img prop before roles
  lines[vmNavIdx] = lines[vmNavIdx].replace(
    'roles:["admin","operator","viewer"]}',
    'img:"__IMGURI__", roles:["admin","operator","viewer"]}'
  );
}
// Now replace placeholder with actual data URI (avoid any template literal issues)
lines[vmNavIdx] = lines[vmNavIdx].replace('"__IMGURI__"', JSON.stringify(dataUri));
console.log('VMware nav item updated with base64 data URI');

// ── 2. Rewrite nav rendering for image-based items ──
// Find the two lines I modified before (around 11851-11852)
let imgLineIdx = -1;
for (let i = 11840; i < 11870; i++) {
  if (lines[i] && lines[i].includes('n.img?') && lines[i].includes('<img')) {
    imgLineIdx = i; break;
  }
}
if (imgLineIdx < 0) { console.log('ERROR: img render line not found'); process.exit(1); }
console.log('Image render line at', imgLineIdx+1);

// lines[imgLineIdx] = image branch
// lines[imgLineIdx+1] = fallback (text+icon) branch
// Rewrite both lines as a single clean replacement
lines[imgLineIdx] = "             {n.img?(<div style={{width:'100%',padding:'2px 0'}}><img src={n.img} alt={n.label} draggable={false} style={{display:'block',width:'100%',height:28,objectFit:'contain',objectPosition:'left center',borderRadius:3,filter:page===n.id?'none':'brightness(0.82) contrast(1.05)'}} /></div>):(";
lines[imgLineIdx+1] = "             <><span style={{fontSize:n.sub?13:16,width:22,textAlign:'center',flexShrink:0,lineHeight:1}}>{n.icon}</span><span style={{flex:1,fontSize:n.sub?12:undefined,color:n.sub&&page!==n.id?p.textSub:undefined}}>{n.label}</span></>)}";
console.log('Nav image rendering updated — active=full brightness, inactive=dimmed');

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
