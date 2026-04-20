const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');
const lines = c.split('\r\n');
for (let i = 3220; i < 3234; i++) console.log((i+1) + ': ' + lines[i]);
