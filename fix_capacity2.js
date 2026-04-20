// fix_capacity2.js — Remove duplicate KPI and extra </div> in CapacityPage
const fs = require('fs');
const filePath = 'C:/caas-dashboard/frontend/src/App.jsx';
const raw = fs.readFileSync(filePath, 'utf8');
const lines = raw.split('\r\n');

// Find the duplicate KPI (the one outside the div, at line ~2744)
let found = false;
for (let i = 2720; i < 2760; i++) {
  if (lines[i] && lines[i].includes('label=\\"Storage Free\\"') && lines[i].includes('<KPI') && !lines[i].includes('const')) {
    console.log('Found duplicate KPI at line', i+1, ':', lines[i].substring(0, 80));
    // Check the next line is </div> and should also be removed
    const nextLine = lines[i+1] || '';
    console.log('Next line:', JSON.stringify(nextLine));
    
    if (nextLine.trim() === '</div>') {
      // Remove both lines
      lines.splice(i, 2);
      console.log('Removed duplicate KPI + extra </div>');
      found = true;
      break;
    } else {
      // Just remove the KPI line
      lines.splice(i, 1);
      console.log('Removed duplicate KPI only');
      found = true;
      break;
    }
  }
}

if (!found) {
  console.error('FAILED: Could not find duplicate KPI line');
  process.exit(1);
}

const newContent = lines.join('\r\n');
fs.writeFileSync(filePath + '.bak5', raw, 'utf8');
fs.writeFileSync(filePath, newContent, 'utf8');
console.log('New total lines:', lines.length);
console.log('DONE');
