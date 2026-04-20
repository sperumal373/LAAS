const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
// Find snapshot age coloring
for (let i = 0; i < lines.length; i++) {
  const l = lines[i];
  if (l.includes('snap') && (l.includes('age') || l.includes('Age') || l.includes('days') || l.includes('day'))) {
    if (l.includes('color') || l.includes('Color') || l.includes('clr') || l.includes('#ef') || l.includes('#f59')) {
      console.log((i+1) + ': ' + l.trim().substring(0,120));
    }
  }
}
// Find snap age coloring specifically
for (let i = 0; i < lines.length; i++) {
  const l = lines[i];
  if ((l.includes('>30') || l.includes('>7') || l.includes('>14') || l.includes('>=30') || l.includes('>=7')) && l.includes('snap')) {
    console.log((i+1) + ': ' + l.trim().substring(0,120));
  }
}
