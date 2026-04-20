const fs = require('fs');
const content = fs.readFileSync('C:/caas-dashboard/backend/vmware_client.py', 'utf8');
const lines = content.split('\n');
let hits = [];
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('"snap') || lines[i].includes("'snap")) {
    hits.push((i + 1) + ': ' + lines[i].trim());
  }
}
console.log('=== Snapshot fields ===');
console.log(hits.slice(0, 40).join('\n'));

// Also look for the snapshot list function
let inSnap = false;
let blockStart = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('def list_snapshots') || lines[i].includes('def get_snapshots')) {
    blockStart = i;
    console.log('\n=== Found snapshot list function at line ' + (i + 1));
    for (let j = i; j < i + 60; j++) {
      console.log((j + 1) + ': ' + lines[j]);
    }
    break;
  }
}

// Search main.py for snapshot endpoint
const main = fs.readFileSync('C:/caas-dashboard/backend/main.py', 'utf8');
const mlines = main.split('\n');
for (let i = 0; i < mlines.length; i++) {
  if (mlines[i].includes('snapshot') && mlines[i].includes('def ') && mlines[i].includes('@')) {
    console.log('\n=== Snapshot endpoint at line ' + (i + 1) + ': ' + mlines[i].trim());
    for (let j = i; j < i + 5; j++) console.log((j + 1) + ': ' + mlines[j]);
  }
}
