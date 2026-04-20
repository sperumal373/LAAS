const fs = require('fs');
const raw = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = raw.split('\r\n');

// Find line with isAdmin= inside AuditPage
let si = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('function AuditPage')) { si = i; break; }
}
let target = -1;
for (let i = si; i < si + 20; i++) {
  if (lines[i].includes('const isAdmin=')) { target = i; break; }
}
console.log('Inserting after line', target+1, ':', lines[target]);

// Insert the missing state after isAdmin line
lines.splice(target + 1, 0, '  const [actionFilter, setActionFilter] = useState("all");');

fs.writeFileSync('C:/caas-dashboard/frontend/src/App.jsx', lines.join('\r\n'), 'utf8');
console.log('Done. AuditPage actionFilter state added.');
