const fs = require('fs');
const lines = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8').split('\r\n');
for (let i = 12980; i < 13010; i++) {
  if (lines[i] && lines[i].includes('content')) console.log((i+1)+':', lines[i].substring(0,100));
}
