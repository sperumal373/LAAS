const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
// Find VM Actions tab area (around line 1691)
for (let i = 1688; i < 1850; i++) {
  console.log((i+1) + ': ' + lines[i]);
}
