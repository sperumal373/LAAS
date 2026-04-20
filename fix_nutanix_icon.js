
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// Find the final fallback span in the nav icon ternary chain
let fallbackIdx = -1;
for (let i = 11860; i < 11885; i++) {
  if (lines[i] && lines[i].includes(": <span") && lines[i].includes('n.icon}')) {
    fallbackIdx = i; break;
  }
}
if (fallbackIdx < 0) { console.log('ERROR: fallback not found'); process.exit(1); }
console.log('Fallback at line', fallbackIdx+1);

// Insert Nutanix SVG ternary before the fallback span
// Nutanix logo: green chevron ">" on left + blue "X" on right
lines[fallbackIdx] = [
  "                 : n.id==='nutanix'",
  "                   ? <svg viewBox='0 0 100 100' style={{width:20,height:20,flexShrink:0,display:'block'}}>",
  // Green chevron (left side) — polygon making a ">" arrow shape
  "                       <polygon points='8,12 22,12 62,50 22,88 8,88 48,50' fill='#6EBE44'/>",
  // Blue X (right side) — two rotated rectangles
  "                       <g transform='translate(72,50)'>",
  "                         <rect x='-28' y='-7' width='56' height='14' rx='4' fill='#1E66AE' transform='rotate(45)'/>",
  "                         <rect x='-28' y='-7' width='56' height='14' rx='4' fill='#1E66AE' transform='rotate(-45)'/>",
  "                       </g>",
  "                     </svg>",
  "                   : <span style={{fontSize:n.sub?13:16,width:22,textAlign:'center',flexShrink:0,lineHeight:1}}>{n.icon}</span>",
].join('\r\n');

console.log('Nutanix SVG logo added to nav ternary chain');
fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
