const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);

// Find fmtUsd and fmtInr blocks dynamically
for (let i = 0; i < lines.length; i++) {
  const l = lines[i];
  if (l.includes('const fmtInr') || l.includes('const fmtUsd') || 
      l.includes('1000000).toFixed(2)}M') || l.includes('u/1000).toFixed') ||
      l.includes('u.toFixed(0)') || l.includes('v/100000).toFixed') ||
      l.includes('v/1000).toFixed') || l.includes('v.toFixed(0)') ||
      (l.includes('fmtUsd(totalCbInr)') && l.includes('cumulative')) ||
      (l.includes('fmtInr(totalCbInr)') && l.includes('cumulative'))) {
    console.log((i+1) + ': ' + l.trim().substring(0,100));
  }
}
