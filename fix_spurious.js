const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const lines = src.split('\r\n');
const idx = 13120; // 0-indexed = line 13121
console.log('Line 13121:', JSON.stringify(lines[idx]));
if (lines[idx].trim() === ')}') {
  lines.splice(idx, 1);
  console.log('Removed spurious )}');
} else {
  console.error('Unexpected content at 13121:', lines[idx]);
}
fs.writeFileSync(path, lines.join('\r\n'));
console.log('Done. New length:', lines.length);
