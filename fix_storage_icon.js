
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// Find the final fallback span line
let fallbackIdx = -1;
for (let i = 11884; i < 11898; i++) {
  if (lines[i] && lines[i].includes(": <span") && lines[i].includes('n.icon}')) {
    fallbackIdx = i; break;
  }
}
if (fallbackIdx < 0) { console.log('ERROR: fallback not found'); process.exit(1); }
console.log('Fallback at line', fallbackIdx+1);

// Storage: 3 stacked cylinders (top disk lighter blue, middle/body medium blue, bottom darker)
// Each cylinder = flat ellipse top + rectangle body
lines[fallbackIdx] = [
  "                     : n.id==='storage'",
  "                       ? <svg viewBox='0 0 100 100' style={{width:20,height:20,flexShrink:0,display:'block'}}>",
  // Bottom cylinder
  "                           <rect x='14' y='62' width='72' height='18' rx='2' fill='#1565C0'/>",
  "                           <ellipse cx='50' cy='80' rx='36' ry='9' fill='#0D47A1'/>",
  "                           <ellipse cx='50' cy='62' rx='36' ry='9' fill='#1976D2'/>",
  // Middle cylinder
  "                           <rect x='14' y='40' width='72' height='18' rx='2' fill='#1976D2'/>",
  "                           <ellipse cx='50' cy='58' rx='36' ry='9' fill='#1565C0'/>",
  "                           <ellipse cx='50' cy='40' rx='36' ry='9' fill='#2196F3'/>",
  // Top cylinder
  "                           <rect x='14' y='18' width='72' height='18' rx='2' fill='#2196F3'/>",
  "                           <ellipse cx='50' cy='36' rx='36' ry='9' fill='#1976D2'/>",
  "                           <ellipse cx='50' cy='18' rx='36' ry='9' fill='#42A5F5'/>",
  // Highlight sheen on top
  "                           <ellipse cx='40' cy='16' rx='16' ry='5' fill='#90CAF9' opacity='0.45'/>",
  "                         </svg>",
  "                       : <span style={{fontSize:n.sub?13:16,width:22,textAlign:'center',flexShrink:0,lineHeight:1}}>{n.icon}</span>",
].join('\r\n');

console.log('Storage stacked-cylinders SVG added to nav ternary chain');
fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
