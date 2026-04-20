const fs = require('fs');
const filePath = 'C:/caas-dashboard/frontend/src/App.jsx';
const raw = fs.readFileSync(filePath, 'utf8');
const lines = raw.split('\r\n');
console.log('Line 2744:', JSON.stringify(lines[2743]));
console.log('Line 2745:', JSON.stringify(lines[2744]));
// Verify and remove lines 2744 and 2745 (indexes 2743 and 2744)
const l1 = lines[2743] || '';
const l2 = lines[2744] || '';
if (l1.includes('Storage Free') && l1.includes('<KPI') && l2.trim() === '</div>') {
  lines.splice(2743, 2);
  console.log('Removed 2 lines (duplicate KPI + extra </div>)');
  fs.writeFileSync(filePath, lines.join('\r\n'), 'utf8');
  console.log('New total:', lines.length);
  console.log('DONE');
} else {
  console.error('Unexpected content at 2744/2745:');
  for (let i = 2740; i < 2750; i++) console.log((i+1)+':', JSON.stringify(lines[i]));
  process.exit(1);
}
