
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// Find VMware nav item
let vmNavIdx = -1;
for (let i = 11800; i < 11840; i++) {
  if (lines[i] && lines[i].includes('"vms"') && lines[i].includes('VMware')) {
    vmNavIdx = i; break;
  }
}
if (vmNavIdx < 0) { console.log('ERROR'); process.exit(1); }
console.log('at line', vmNavIdx+1, ':', lines[vmNavIdx].trim().substring(0,200));

// Strip any existing base64 data URI and set clean file path
const cur = lines[vmNavIdx];
if (cur.includes('data:image')) {
  // Replace data URI with clean file path
  lines[vmNavIdx] = cur.replace(/img:"data:image\/jpeg;base64,[^"]*"/, 'img:"/vmware-logo.jpg"');
  console.log('Replaced base64 with file path');
} else if (!cur.includes('img:')) {
  // Add img prop
  lines[vmNavIdx] = cur.replace(
    'roles:["admin","operator","viewer"]}',
    'img:"/vmware-logo.jpg", roles:["admin","operator","viewer"]}'
  );
  console.log('Added img prop');
} else {
  console.log('img prop already present (file path), no change needed');
}

// Fix the rendering to a full-width image tile with proper fitting
let imgLineIdx = -1;
for (let i = 11840; i < 11870; i++) {
  if (lines[i] && lines[i].includes('n.img?')) { imgLineIdx = i; break; }
}
if (imgLineIdx < 0) { console.log('ERROR: img render not found'); process.exit(1); }
console.log('Image render at line', imgLineIdx+1);

// Replace the image branch with clean full-width rendering
lines[imgLineIdx] = "             {n.img?(<div style={{width:'100%',lineHeight:0}}><img src={n.img} alt='VMware' draggable={false} style={{display:'block',width:'100%',height:32,objectFit:'contain',objectPosition:'left center',borderRadius:3,opacity:page===n.id?1:0.75}} /></div>):(";

lines[imgLineIdx+1] = "             <><span style={{fontSize:n.sub?13:16,width:22,textAlign:'center',flexShrink:0,lineHeight:1}}>{n.icon}</span><span style={{flex:1,fontSize:n.sub?12:undefined,color:n.sub&&page!==n.id?p.textSub:undefined}}>{n.label}</span></>)}";

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved OK');
