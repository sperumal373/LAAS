
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// Find the final fallback span line
let fallbackIdx = -1;
for (let i = 11876; i < 11892; i++) {
  if (lines[i] && lines[i].includes(": <span") && lines[i].includes('n.icon}')) {
    fallbackIdx = i; break;
  }
}
if (fallbackIdx < 0) { console.log('ERROR: fallback not found'); process.exit(1); }
console.log('Fallback at line', fallbackIdx+1);

// Red Hat fedora logo SVG:
//  - Black ellipse base (brim of hat)
//  - Red dome (crown) on top using a path
//  - Small black band between brim and crown
lines[fallbackIdx] = [
  "                   : n.id==='ansible'",
  "                     ? <svg viewBox='0 0 100 100' style={{width:20,height:20,flexShrink:0,display:'block'}}>",
  // Crown: red dome — large arc
  "                         <path d='M18,52 Q18,18 50,18 Q82,18 82,52 Z' fill='#EE0000'/>",
  // Hat band: thin dark stripe
  "                         <rect x='18' y='50' width='64' height='9' rx='0' fill='#1a1a1a'/>",
  // Brim: wide flat ellipse
  "                         <ellipse cx='50' cy='62' rx='42' ry='11' fill='#1a1a1a'/>",
  // White highlight on crown
  "                         <path d='M28,46 Q32,28 50,26 Q38,30 34,46 Z' fill='#ff4444' opacity='0.4'/>",
  "                       </svg>",
  "                     : <span style={{fontSize:n.sub?13:16,width:22,textAlign:'center',flexShrink:0,lineHeight:1}}>{n.icon}</span>",
].join('\r\n');

console.log('Ansible AAP Red Hat logo added to nav ternary chain');
fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
