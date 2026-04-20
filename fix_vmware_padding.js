
const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
let lines = raw.split('\r\n');

// Find the nav item div with style={n.sub?...:{}} so we can add n.img padding override
let navDivStyle = -1;
for (let i = 11845; i < 11858; i++) {
  if (lines[i] && lines[i].includes('style={n.sub?') && lines[i].includes('marginLeft:10')) {
    navDivStyle = i; break;
  }
}
if (navDivStyle < 0) { console.log('nav div style not found'); process.exit(1); }
console.log('nav div style at line', navDivStyle+1);
console.log('current:', lines[navDivStyle].trim());

// Replace style to also handle n.img (reduce vertical padding to 5px, keep horizontal for image items)
lines[navDivStyle] = "             style={n.sub?{marginLeft:10,paddingLeft:8,borderLeft:`2px solid ${p.accent}40`}:n.img?{padding:'6px 10px'}:{}}>"; 

console.log('updated:', lines[navDivStyle].trim());
fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Saved.');
