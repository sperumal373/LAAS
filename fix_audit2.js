const fs = require('fs');
const filePath = 'C:/caas-dashboard/frontend/src/App.jsx';
const raw = fs.readFileSync(filePath, 'utf8');
const lines = raw.split('\r\n');

// The issue:
// Line 8188 (idx 8187): "                  );"    <- closes return()
// Line 8189 (idx 8188): "                }"       <- closes map callback
// Line 8190 (idx 8189): "                ))}"     <- this is wrong: should be ")}" not "))}"

// The structure is:
//   {filtered.map((l,i) => {   <- opens JSX expression + map + arrow function
//     return ( <tr>...</tr> ); <- return statement
//   })}                         <- closes: arrow fn body "}", map call ")", JSX expr "}"
//
// So line 8190 should be "})" or it needs to be restructured.
// Actually the pattern is:
//   Line 8188:  ");   "     <- closes return(...)
//   Line 8189:  "}"         <- closes the arrow function body
//   Line 8190:  ")}"        <- closes the .map() call and the JSX {} expression
//
// Currently line 8190 has "))}", which would be one extra ")"

console.log('Line 8188:', JSON.stringify(lines[8187]));
console.log('Line 8189:', JSON.stringify(lines[8188]));
console.log('Line 8190:', JSON.stringify(lines[8189]));

if (lines[8189] && lines[8189].trim() === '))}') {
  lines[8189] = lines[8189].replace('))}', ')}');
  console.log('Fixed line 8190 from ")  )}" to ")}"');
  fs.writeFileSync(filePath, lines.join('\r\n'), 'utf8');
  console.log('DONE');
} else {
  console.error('Unexpected content at line 8190:', JSON.stringify(lines[8189]));
  process.exit(1);
}
