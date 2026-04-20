const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/backend/vmware_client.py', 'utf8');
const lines = c.split('\n');
let si = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('snapshot_name') && lines[i].includes(':')) si = i;
}
for (let i = si - 15; i < si + 25; i++) console.log((i+1) + ': ' + lines[i]);
