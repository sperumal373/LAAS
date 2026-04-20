const fs = require('fs');
const filePath = 'C:/caas-dashboard/frontend/src/App.jsx';
const raw = fs.readFileSync(filePath, 'utf8');
const lines = raw.split('\r\n');

const idx = 12882; // 0-indexed = line 12883
const l1 = lines[idx];
const l2 = lines[idx+1];
console.log('Line 12883:', l1.substring(0, 100));
console.log('Line 12884:', l2.substring(0, 100));

// Check conditions using actual string content (not JSON escaped)
const l1HasHidden = l1.includes('overflow:');
const l2HasTextOverflow = l2.trim().startsWith('textOverflow:');
console.log('l1 has overflow:', l1HasHidden, '| l2 starts with textOverflow:', l2HasTextOverflow);

if (l1HasHidden && l2HasTextOverflow) {
  const part2 = l2.trim();
  lines[idx] = l1 + ',' + part2;
  lines.splice(idx+1, 1);
  console.log('Joined to:', lines[idx].substring(0, 120));
  fs.writeFileSync(filePath, lines.join('\r\n'), 'utf8');
  console.log('DONE - new total lines:', lines.length);
} else {
  console.error('Conditions not met - skipping');
  process.exit(1);
}
