const fs = require('fs');
const path = 'C:\\caas-dashboard\\frontend\\src\\App.jsx';
const lines = fs.readFileSync(path, 'utf8').split('\n');

// Find fallback span line
let fallbackIdx = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes(': <span') && lines[i].includes('n.icon}')) {
    fallbackIdx = i;
    break;
  }
}
if (fallbackIdx === -1) { console.error('Fallback span not found'); process.exit(1); }
console.log('Fallback at line', fallbackIdx + 1);

// Backup SVG: dark circle, white cloud, blue LEFT down-arrow, red RIGHT up-arrow (side by side)
const newEntry = `          : n.id==='backup'
          ? <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="22" height="22" style={{flexShrink:0}}>
              <circle cx="10" cy="10" r="9.5" fill="#37474F"/>
              <path fill="#CFD8DC" d="M5.5 11 Q5 11 4.5 10.5 Q3.5 9.5 4 8.3 Q4.5 7 5.8 7 Q6 5.7 7.2 5.2 Q8.3 4.7 9.3 5.4 Q9.8 4.5 11 4.5 Q12.5 4.5 13 5.8 Q14.3 5.9 14.7 7.2 Q15.8 7.5 15.5 8.9 Q15.1 11 13.5 11 Z"/>
              <polygon fill="#5BA4D4" points="6,9 7.2,9 7.2,7.5 8.8,7.5 8.8,9 10,9 8,12"/>
              <polygon fill="#C0504D" points="10,10.5 11.2,10.5 11.2,12 12.8,12 12.8,10.5 14,10.5 12,7.5"/>
            </svg>`;

lines.splice(fallbackIdx, 0, newEntry);

fs.writeFileSync(path, lines.join('\n'), 'utf8');
console.log('Backup cloud+arrows SVG added to nav ternary chain.');
console.log('Saved.');
