const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
let changes = 0;

// Fix extra ) on line 6079 (0-indexed 6078)
const i1 = 6078;
if (lines[i1].includes('+${Math.round(licRate/usd))}/mo')) {
  lines[i1] = lines[i1].replace('+${Math.round(licRate/usd))}/mo', '+${Math.round(licRate/usd)}/mo');
  console.log('FIX extra ) on line 6079'); changes++;
} else { console.log('MISS extra ): ' + lines[i1].trim().substring(0,80)); }

// Fix PDF INR line 6964  use Math.round(chargeback_inr) directly, no rate needed
const i2 = 6964;
const badPDF = 'Math.round(r.chargeback_usd)*((typeof usdRate!=="undefined"?usdRate:83.5)).toLocaleString("en-IN")}`;';
if (lines[i2].includes('Math.round(r.chargeback_usd)')) {
  lines[i2] = lines[i2].replace(
    /Math\.round\(r\.chargeback_usd\)\*\(\(typeof usdRate.*?toLocaleString\("en-IN"\)\)`/,
    'Math.round(r.chargeback_inr).toLocaleString("en-IN")}`'
  );
  console.log('FIX PDF INR line 6965'); changes++;
} else { console.log('MISS PDF INR: ' + lines[i2].trim().substring(0,80)); }

fs.writeFileSync(path, lines.join(EOL));
console.log('Changes:', changes);
