const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/backend/vmware_client.py', 'utf8');
const lines = c.split('\n');
// Check what vim imports exist
for (let i = 0; i < 20; i++) console.log((i+1) + ': ' + lines[i]);
