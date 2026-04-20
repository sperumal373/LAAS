const fs = require('fs');
const path = 'C:\\caas-dashboard\\frontend\\src\\App.jsx';
const lines = fs.readFileSync(path, 'utf8').split('\n');

let fallbackIdx = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes(': <span') && lines[i].includes('n.icon}')) {
    fallbackIdx = i;
    break;
  }
}
if (fallbackIdx === -1) { console.error('Fallback span not found'); process.exit(1); }
console.log('Fallback at line', fallbackIdx + 1);

// SVG: red left arc (~220deg), blue right arc (~90deg), yellow doc center, green magnifier+gear
const newEntry = `          : n.id==='project_utilization'
          ? <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="22" height="22" style={{flexShrink:0}}>
              {/* red left arc ~220deg */}
              <path fill="none" stroke="#E05A4A" strokeWidth="2" strokeLinecap="round"
                d="M10 2.5 A7.5 7.5 0 1 0 16.5 13" />
              {/* blue right arc ~80deg */}
              <path fill="none" stroke="#5AADE0" strokeWidth="2" strokeLinecap="round"
                d="M10 2.5 A7.5 7.5 0 0 1 16.5 13" />
              {/* yellow document */}
              <rect x="6.5" y="5" width="7" height="8.5" rx="0.5" fill="#F5A623"/>
              <rect x="8" y="7" width="4" height="1" rx="0.3" fill="#FFDEA0"/>
              {/* green magnifier circle */}
              <circle cx="11.5" cy="12.5" r="3" fill="white" stroke="#6AAF2A" strokeWidth="0.5"/>
              <circle cx="11.5" cy="12.5" r="2.4" fill="#6AAF2A"/>
              {/* gear shape */}
              <circle cx="11.5" cy="12.5" r="0.8" fill="#D4E98A"/>
              <path fill="#D4E98A" d="M11.5 10.5 L11.8 11.2 L12.5 11 L12.5 11.8 L11.8 12 L12 12.7 L11.3 12.9 L11.1 12.2 L10.4 12.5 L10 11.9 L10.6 11.5 L10.3 10.8 L11 10.7 Z"/>
              {/* magnifier handle */}
              <line x1="13.6" y1="14.6" x2="15" y2="16" stroke="#4A8A1A" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>`;

lines.splice(fallbackIdx, 0, newEntry);
fs.writeFileSync(path, lines.join('\n'), 'utf8');
console.log('Project Utilization resource icon added.');
console.log('Saved.');
