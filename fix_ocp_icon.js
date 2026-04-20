
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// Find the fallback span line inside the nav icon ternary (currently after VMware SVG)
let fallbackIdx = -1;
for (let i = 11848; i < 11870; i++) {
  if (lines[i] && lines[i].includes(": <span") && lines[i].includes('n.icon}')) {
    fallbackIdx = i; break;
  }
}
if (fallbackIdx < 0) { console.log('ERROR: fallback span not found'); process.exit(1); }
console.log('Fallback span at line', fallbackIdx+1, ':', lines[fallbackIdx].trim().substring(0,80));

// Replace the fallback span with: OpenShift SVG ternary + original fallback span
// OpenShift logo: thick red ring (annulus) with 4 rectangular notch cutouts at 45/135/225/315 deg
// creating two opposing interlocking arc segments
lines[fallbackIdx] = [
  "               : n.id==='openshift'",
  "                 ? <svg viewBox='0 0 100 100' style={{width:20,height:20,flexShrink:0,display:'block'}}>",
  "                     <defs>",
  "                       <mask id='ocp-mask'>",
  "                         <circle cx='50' cy='50' r='44' fill='white'/>",
  "                         <circle cx='50' cy='50' r='27' fill='black'/>",
  "                         <rect x='43' y='5' width='14' height='20' rx='2' fill='black' transform='rotate(45 50 50)'/>",
  "                         <rect x='43' y='5' width='14' height='20' rx='2' fill='black' transform='rotate(135 50 50)'/>",
  "                         <rect x='43' y='5' width='14' height='20' rx='2' fill='black' transform='rotate(225 50 50)'/>",
  "                         <rect x='43' y='5' width='14' height='20' rx='2' fill='black' transform='rotate(315 50 50)'/>",
  "                       </mask>",
  "                     </defs>",
  "                     <circle cx='50' cy='50' r='44' fill='#EE0000' mask='url(#ocp-mask)'/>",
  "                   </svg>",
  "                 : <span style={{fontSize:n.sub?13:16,width:22,textAlign:'center',flexShrink:0,lineHeight:1}}>{n.icon}</span>",
].join('\r\n');

console.log('OpenShift SVG logo inserted into nav ternary chain');

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
