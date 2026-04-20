const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
// Read VMwarePage function definition and early state
for (let i = 1392; i < 1470; i++) {
  console.log((i+1) + ': ' + lines[i]);
}
