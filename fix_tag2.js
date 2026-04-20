const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const lines = src.split('\r\n');

// Working with 0-indexed lines
// Current state (1-indexed shown):
// 5696: {selTags.length>0&&(  <- opens, no close
// 5700: </div>
// 5701: </div>                <- outer div close (WRONG  selTags not closed)
// 5702: )}                    <- orphan

// We need to:
// 1) Insert )} at line 5701 (before the outer </div>) to close {selTags.length>0&&(
// 2) Remove line 5703 which is the orphan

let selTagsOpen = -1, outerDivClose = -1, orphanClose = -1;
for (let i = 5690; i < 5720; i++) {
  if (lines[i] && lines[i].includes('selTags.length>0&&(')) selTagsOpen = i;
  if (selTagsOpen > 0 && lines[i] && lines[i].trim() === '</div>' && i > selTagsOpen + 5 && outerDivClose === -1) outerDivClose = i;
  if (selTagsOpen > 0 && lines[i] && lines[i].trim() === ')}' && i > selTagsOpen + 5) { orphanClose = i; break; }
}
console.log('selTagsOpen:', selTagsOpen+1, 'outerDivClose:', outerDivClose+1, 'orphan:', orphanClose+1);

// Insert )} before outerDivClose to close {selTags.length>0&&(
const idnt = lines[selTagsOpen].match(/^(\s*)/)[1];
lines.splice(outerDivClose, 0, idnt + '  )}');
console.log('Inserted )} closing selTags before outerDivClose');
if (orphanClose >= outerDivClose) orphanClose++;

// Remove orphan
if (lines[orphanClose] && lines[orphanClose].trim() === ')}') {
  lines.splice(orphanClose, 1);
  console.log('Removed orphan )} at', orphanClose + 1);
} else {
  console.log('Orphan not at', orphanClose+1, ':', lines[orphanClose]);
}

fs.writeFileSync(path, lines.join('\r\n'));
console.log('Done');
