const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
// Find threshold usage
for (let i = 0; i < lines.length; i++) {
  const l = lines[i];
  if (l.includes('threshold') || l.includes('Threshold') || l.includes('warn_pct') || l.includes('crit_pct') || l.includes('warnPct') || l.includes('critPct')) {
    console.log((i+1) + ': ' + l.trim().substring(0, 120));
  }
}
