const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
// Check imports
for (let i = 0; i < 10; i++) {
  if (lines[i].includes('fetchProjectUtilization') || lines[i].includes('import')) {
    console.log((i+1)+':', lines[i].substring(0, 200));
  }
}
// Search for fetchProjectUtilization
const hasFetch = lines.some(l => l.includes('fetchProjectUtilization'));
console.log('fetchProjectUtilization found:', hasFetch);
