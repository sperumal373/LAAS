// Line-number based fix  more reliable with CRLF/emoji
const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');

// Detect line ending
const crlf = src.includes('\r\n');
const EOL = crlf ? '\r\n' : '\n';

const lines = src.split(EOL);
console.log(`Total lines: ${lines.length}, EOL: ${crlf ? 'CRLF' : 'LF'}`);

// Find the key lines dynamically
let tagConditionalLine = -1;
let tagLabelSpanLine = -1;
let tagChipsCondLine = -1;
let tagOuterCloseLine = -1;

for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('availTags.length>0||tagsLoading')) tagConditionalLine = i;
  if (tagConditionalLine > 0 && lines[i].includes('optional') && lines[i].includes('tags to apply')) tagLabelSpanLine = i;
  if (tagConditionalLine > 0 && lines[i].includes('!tagsLoading&&(') && i > tagConditionalLine + 3) tagChipsCondLine = i;
  if (tagConditionalLine > 0 && i > tagConditionalLine + 20 && lines[i].trim() === ')}' && 
      tagOuterCloseLine === -1 && tagChipsCondLine > 0 && i > (tagChipsCondLine + 15)) tagOuterCloseLine = i;
}

console.log(`Found: conditional=${tagConditionalLine+1} span=${tagLabelSpanLine+1} chips=${tagChipsCondLine+1} close=${tagOuterCloseLine+1}`);

if (tagConditionalLine < 0) { console.error('Already fixed or not found'); process.exit(0); }

// Fix 1: Remove outer conditional wrapper line
lines.splice(tagConditionalLine, 1);
console.log('Removed conditional wrapper line');
if (tagLabelSpanLine > tagConditionalLine) tagLabelSpanLine--;
if (tagChipsCondLine > tagConditionalLine) tagChipsCondLine--;
if (tagOuterCloseLine > tagConditionalLine) tagOuterCloseLine--;

// Fix 2: Replace the static optional span with two conditional spans
const oldSpan = lines[tagLabelSpanLine];
const indent2 = oldSpan.match(/^(\s*)/)[1];
const p1 = indent2 + '{!tagsLoading&&availTags.length===0&&<span style={{fontSize:10,color:"#94a3b8",marginLeft:4}}> No tags configured for this vCenter</span>}';
const p2 = indent2 + '{!tagsLoading&&availTags.length>0&&<span style={{fontSize:10,color:"#94a3b8",fontWeight:400,marginLeft:4}}>optional \u2014 select tags to apply on this VM</span>}';
lines.splice(tagLabelSpanLine, 1, p1, p2);
console.log('Replaced optional span with two conditional spans');
if (tagChipsCondLine >= tagLabelSpanLine) tagChipsCondLine++;
if (tagOuterCloseLine >= tagLabelSpanLine) tagOuterCloseLine++;

// Fix 3: Add availTags.length>0 guard to chips section
const oldChips = lines[tagChipsCondLine];
if (oldChips && oldChips.includes('!tagsLoading&&(')) {
  lines[tagChipsCondLine] = oldChips.replace('!tagsLoading&&(', '!tagsLoading&&availTags.length>0&&(');
  console.log('Fixed chips condition');
} else { console.log('Chips: ' + (oldChips||'')?.trim()); }

// Fix 4: Remove orphan )} closing the old outer conditional
const orphan = lines[tagOuterCloseLine];
if (orphan && orphan.trim() === ')}') {
  lines.splice(tagOuterCloseLine, 1);
  console.log('Removed orphan )}');
} else {
  console.log('Scanning for orphan )}: ' + (orphan||'')?.trim());
  for (let i = tagChipsCondLine + 15; i < tagChipsCondLine + 35 && i < lines.length; i++) {
    if (lines[i] && lines[i].trim() === ')}') {
      lines.splice(i, 1);
      console.log('Removed orphan )} at scan line ' + (i+1));
      break;
    }
  }
}

fs.writeFileSync(path, lines.join(EOL));
console.log('Done  tag selector fix applied');
