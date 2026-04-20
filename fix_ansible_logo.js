const fs = require('fs');
const path = 'C:\\caas-dashboard\\frontend\\src\\App.jsx';
const lines = fs.readFileSync(path, 'utf8').split('\n');

// Find the ansible ternary start line
let ansibleStart = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes("n.id==='ansible'")) {
    ansibleStart = i;
    break;
  }
}
if (ansibleStart === -1) { console.error('ansible line not found'); process.exit(1); }
console.log('Ansible ternary at line', ansibleStart + 1);

// Find the end of the ansible SVG block — next ternary branch or fallback
let ansibleEnd = -1;
for (let i = ansibleStart + 1; i < lines.length; i++) {
  // next branch starts with ": n.id===" or ": <span"
  if ((lines[i].includes(": n.id===") || (lines[i].includes(": <span") && lines[i].includes("n.icon}"))) ) {
    ansibleEnd = i;
    break;
  }
}
if (ansibleEnd === -1) { console.error('ansible end not found'); process.exit(1); }
console.log('Ansible SVG block ends before line', ansibleEnd + 1);

// New ansible entry: red circle with white Ansible "A"
const newAnsible = `          : n.id==='ansible'
          ? <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="22" height="22" style={{flexShrink:0}}>
              <circle cx="10" cy="10" r="9.5" fill="#CC0000"/>
              <path fill="white" fillRule="evenodd"
                d="M10 2.5 L16.5 17 L13.8 17 L11.6 11.8 L8.4 11.8 L6.2 17 L3.5 17 Z
                   M10 6.2 L11.2 11.8 L8.8 11.8 Z"/>
            </svg>`;

// Replace lines from ansibleStart to ansibleEnd-1 (inclusive) with new block
lines.splice(ansibleStart, ansibleEnd - ansibleStart, newAnsible);

fs.writeFileSync(path, lines.join('\n'), 'utf8');
console.log('Ansible nav icon updated to red-circle + white-A logo.');
console.log('Saved.');
