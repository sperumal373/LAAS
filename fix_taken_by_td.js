const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const lines = src.split('\r\n');
const idx = 3227;
console.log('Before:', JSON.stringify(lines[idx]));
// Use unicode escape for em dash U+2014
const emDash = '\u2014';
if (!lines[idx].includes('>' + emDash + '</td>')) { 
  console.error('Static dash not found, trying anyway...'); 
}
lines[idx] = '              <td style={{color:p.textMute,fontSize:11}}>{s.created_by||"' + emDash + '"}</td>';
console.log('After:', JSON.stringify(lines[idx]));
fs.writeFileSync(path, lines.join('\r\n'));
console.log('Done');
