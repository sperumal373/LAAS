const fs = require('fs');
const filePath = 'C:/caas-dashboard/frontend/src/App.jsx';
const raw = fs.readFileSync(filePath, 'utf8');
const lines = raw.split('\r\n');

const idx = 12882; // 0-indexed = line 12883
console.log('Line 12883:', JSON.stringify(lines[idx]));
console.log('Line 12884:', JSON.stringify(lines[idx+1]));

// Line 12883 ends with: overflow:"hidden"
// Line 12884 starts with spaces then: textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{r.sub}</div>}
// These two lines should be joined into one

if (lines[idx] && lines[idx+1] && 
    lines[idx].includes('overflow:\\"hidden\\"') && 
    lines[idx+1].trim().startsWith('textOverflow:')) {
  // Join the two lines, adding comma separator
  const part1 = lines[idx];
  const part2 = lines[idx+1].trim();
  lines[idx] = part1 + ',' + part2;
  lines.splice(idx+1, 1); // remove line 12884
  console.log('Joined lines:', JSON.stringify(lines[idx]));
  fs.writeFileSync(filePath, lines.join('\r\n'), 'utf8');
  console.log('DONE - new total lines:', lines.length);
} else {
  console.error('Unexpected content');
  for (let i = idx-1; i <= idx+3; i++) console.log((i+1)+':', JSON.stringify(lines[i]));
  process.exit(1);
}
