const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const lines = src.split('\r\n');

// 0-indexed:
// 3207 (1-indexed 3208): DESCRIPTION + CREATED headers
// 3208 (1-indexed 3209): AGE header
// 3209 (1-indexed 3210): TAKEN BY header
// Need to swap: put AGE+TAKEN BY before DESCRIPTION+CREATED

const descCreated = lines[3207];  // DESCRIPTION CREATED
const ageHeader = lines[3208];    // AGE
const takenBy = lines[3209];      // TAKEN BY

console.log('descCreated:', descCreated.trim());
console.log('ageHeader:', ageHeader.trim());
console.log('takenBy:', takenBy.trim());

if (!descCreated.includes('DESCRIPTION') || !ageHeader.includes('AGE') || !takenBy.includes('TAKEN BY')) {
  console.error('Unexpected content'); process.exit(1);
}

// Reorder: AGE, TAKEN BY, DESCRIPTION CREATED
lines[3207] = ageHeader;
lines[3208] = takenBy;
lines[3209] = descCreated;

console.log('Reordered headers');
fs.writeFileSync(path, lines.join('\r\n'));
console.log('Done');
