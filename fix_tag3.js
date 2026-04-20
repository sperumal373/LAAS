const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const lines = src.split('\r\n');

// Exact lines (0-indexed):
// 5699 (0-indexed) = line 5700 (1-indexed): "                  </div>"  <- inner selTags div close
// 5700 (0-indexed) = line 5701 (1-indexed): "              </div>"       <- outer div close
// 5701 (0-indexed) = line 5702 (1-indexed): "            )}"              <- orphan

const idx5700 = 5699; // 0-indexed line 5700 = inner div close
const idx5701 = 5700; // 0-indexed line 5701 = outer div close  
const idx5702 = 5701; // 0-indexed line 5702 = orphan

console.log('Line 5700:', JSON.stringify(lines[idx5700]));
console.log('Line 5701:', JSON.stringify(lines[idx5701]));
console.log('Line 5702:', JSON.stringify(lines[idx5702]));

// Verify
if (!lines[idx5700].includes('</div>')) { console.error('Line 5700 not </div>!'); process.exit(1); }
if (!lines[idx5701].includes('</div>')) { console.error('Line 5701 not </div>!'); process.exit(1); }
if (!lines[idx5702].includes(')}')) { console.error('Line 5702 not )}!'); process.exit(1); }

// Step 1: Insert )} between 5700 (inner div close) and 5701 (outer div close)
lines.splice(idx5701, 0, '                )}');
console.log('Inserted )} at', idx5701 + 1);

// Step 2: After insertion, the orphan )} is now at idx5702+1 = 5703 (0-indexed) = line 5703+1 = 5703
const orphanIdx = idx5702 + 1; // shifted by 1
console.log('Orphan now at 0-indexed', orphanIdx, ':', JSON.stringify(lines[orphanIdx]));
if (lines[orphanIdx].trim() === ')}') {
  lines.splice(orphanIdx, 1);
  console.log('Removed orphan at', orphanIdx + 1);
} else {
  console.error('Orphan not found at', orphanIdx + 1, ':', lines[orphanIdx]);
}

fs.writeFileSync(path, lines.join('\r\n'));
console.log('Done');
