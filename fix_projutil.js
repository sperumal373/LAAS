const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
let n = 0;

function fix(idx, search, replace, label) {
  if (lines[idx] !== undefined && lines[idx].includes(search)) {
    lines[idx] = lines[idx].replace(search, replace);
    console.log('OK ' + label);
    n++;
  } else {
    console.log('XX ' + label + ': >>>' + (lines[idx]||'').trim().substring(0,80));
  }
}

// 1. fmtUsd: use Math.round for clean whole dollars
fix(6886, 'const u = inr / usdRate;', 'const u = Math.round(inr / usdRate);', 'fmtUsd round');
fix(6887, '(u/1000000).toFixed(2)}M`', '(u/1000000).toFixed(1)}M`', 'fmtUsd M decimals');
fix(6888, '(u/1000).toFixed(1)}K`', 'Math.round(u/1000)}K`', 'fmtUsd K round');
fix(6889, '`$${u.toFixed(0)}`', '`$${u}`', 'fmtUsd base round');

// 2. fmtInr: derive from rounded USD for consistency
fix(6880, '`\u20b9${(v/10000000).toFixed(2)}Cr`', '`\u20b9${Math.round(Math.round(v/usdRate)*usdRate/10000000*10)/10}Cr`', 'fmtInr Cr');
fix(6881, '`\u20b9${(v/100000).toFixed(2)}L`', '`\u20b9${Math.round(Math.round(v/usdRate)*usdRate/100000*10)/10}L`', 'fmtInr L');
fix(6882, '`\u20b9${(v/1000).toFixed(1)}K`', '`\u20b9${Math.round(Math.round(v/usdRate)*usdRate/1000*10)/10}K`', 'fmtInr K');
fix(6883, '`\u20b9${v.toFixed(0)}`', '`\u20b9${Math.round(Math.round(v/usdRate)*usdRate)}`', 'fmtInr base');

// 3. KPI tile  USD bold value, INR as sub
fix(6208, // idx 7209
  'value={fmtInr(totalCbInr)} color={p.green} sub={`${fmtUsd(totalCbInr)} cumulative`}',
  'value={fmtUsd(totalCbInr)} color={p.green} sub={`${fmtInr(totalCbInr)} total  INR`}',
  'KPI chargeback');

// 4. Table header  change CHARGEBACK label to USD / INR
fix(7228,
  '<th>CHARGEBACK</th>',
  '<th>CHARGEBACK (USD / INR)</th>',
  'table header');

// 5. Table cell  flip: USD big green, INR small muted
fix(7264, '{fmtInr(r.chargeback_inr)}', '{fmtUsd(r.chargeback_inr)}', 'table cell USD primary');
fix(7265,
  'r.chargeback_inr>0 && <div style={{fontSize:10,color:p.textMute}}>{fmtUsd(r.chargeback_inr)}</div>',
  'r.chargeback_inr>0 && <div style={{fontSize:10,color:p.textMute}}>{fmtInr(r.chargeback_inr)}</div>',
  'table cell INR secondary');

// 6. Tag popup per-VM cbInr/cbUsd  USD first, INR secondary
fix(6971,
  'const cbInr = r.chargeback_inr != null ? `\u20b9${Number(r.chargeback_inr).toLocaleString(\'en-IN\',{maximumFractionDigits:0})}` : "";',
  'const cbUsdVal = r.chargeback_usd != null ? `$${Math.round(r.chargeback_usd)}` : "";',
  'cbInrcbUsdVal');
fix(6972,
  'const cbUsd = r.chargeback_usd != null ? ` / ${Math.round(r.chargeback_usd)}` : "";',
  'const cbInrVal = r.chargeback_inr != null ? ` / \u20b9${Number(Math.round(r.chargeback_usd||0)*usdRate).toLocaleString("en-IN")}` : "";',
  'cbUsdcbInrVal');

fs.writeFileSync(path, lines.join(EOL));
console.log('\nTotal:', n);
