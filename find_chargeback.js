const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
let hits = [];
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('ChargebackPage') || lines[i].includes('function Chargeback') ||
      (lines[i].includes('inr') && lines[i].includes('usd') && lines[i].includes('toFixed')) ||
      (lines[i].includes('chargeback') && lines[i].includes('USD')) ||
      (lines[i].includes('INR') && lines[i].includes('USD') && lines[i].includes('round'))) {
    hits.push((i+1) + ': ' + lines[i].trim().substring(0, 120));
  }
}
console.log(hits.slice(0, 40).join('\n'));
