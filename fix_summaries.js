const fs = require('fs');
const filePath = 'C:/caas-dashboard/frontend/src/App.jsx';
const raw = fs.readFileSync(filePath, 'utf8');
const lines = raw.split('\r\n');

const idx = 12882; // 0-indexed = line 12883
console.log('Line 12883:', JSON.stringify(lines[idx]));

if (lines[idx] && lines[idx].includes('summaries={summaries}')) {
  // Remove "summaries={summaries} " from the style object
  lines[idx] = lines[idx].replace(',summaries={summaries} ', '');
  // Also handle version without comma before
  lines[idx] = lines[idx].replace('summaries={summaries} ', '');
  console.log('Fixed to:', JSON.stringify(lines[idx]));
  fs.writeFileSync(filePath, lines.join('\r\n'), 'utf8');
  console.log('DONE');
} else {
  console.error('Expected summaries={summaries} in line 12883');
  process.exit(1);
}
