
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// ── 1. Add img prop to VMware nav item (id:"vms") ──
let vmNavIdx = -1;
for (let i = 11800; i < 11840; i++) {
  if (lines[i] && lines[i].includes('id:"vms"') && lines[i].includes('label:"VMware"')) {
    vmNavIdx = i; break;
  }
}
if (vmNavIdx < 0) { console.log('ERROR: VMware nav item not found'); process.exit(1); }
console.log('VMware nav item at line', vmNavIdx + 1, ':', lines[vmNavIdx].trim());

// Add img prop before roles
lines[vmNavIdx] = lines[vmNavIdx].replace(
  'roles:["admin","operator","viewer"]}',
  'img:"/vmware-logo.jpg", roles:["admin","operator","viewer"]}'
);
console.log('Updated to:', lines[vmNavIdx].trim());

// ── 2. Update nav rendering to use image when n.img is set ──
// Find the icon span in nav rendering (around line 11851)
let iconSpanIdx = -1;
for (let i = 11840; i < 11870; i++) {
  if (lines[i] && lines[i].includes('{n.icon}') && lines[i].includes('width:22')) {
    iconSpanIdx = i; break;
  }
}
if (iconSpanIdx < 0) { console.log('ERROR: icon span not found'); process.exit(1); }
console.log('Icon span at line', iconSpanIdx + 1);

// The icon span and label span should be on adjacent lines
const labelSpanIdx = iconSpanIdx + 1;
console.log('Label span at line', labelSpanIdx + 1, ':', lines[labelSpanIdx].trim());

// Replace icon span + label span with conditional rendering
lines[iconSpanIdx] = "             {n.img?(<img src={n.img} alt={n.label} style={{width:'100%',height:26,objectFit:'contain',objectPosition:'left center',borderRadius:4,display:'block'}}/>):(";
lines[labelSpanIdx] = "             <><span style={{fontSize:n.sub?13:16,width:22,textAlign:'center',flexShrink:0,lineHeight:1}}>{n.icon}</span><span style={{flex:1,fontSize:n.sub?12:undefined,color:n.sub&&page!==n.id?p.textSub:undefined}}>{n.label}</span></>)}";

console.log('Nav rendering updated');
fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
