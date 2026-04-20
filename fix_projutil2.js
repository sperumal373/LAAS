const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
let n = 0;

function fix(lineNum1, search, replace, label) {
  const idx = lineNum1 - 1;
  if (lines[idx] !== undefined && lines[idx].includes(search)) {
    lines[idx] = lines[idx].replace(search, replace);
    console.log('OK ' + label);
    n++;
  } else {
    console.log('XX ' + label + ': "' + (lines[idx]||'').trim().substring(0,80) + '"');
  }
}

// fmtInr (lines 6879-6884): keep INR values but derive from rounded USD
fix(6880, 'if (!v || v===0) return "";', 'if (!v || v===0) return "";\n    const ru=Math.round(v/usdRate), rv=Math.round(ru*usdRate);', 'fmtInr guard + round');
fix(6881, '`\u20b9${(v/100000).toFixed(2)}L`', '`\u20b9${(rv/100000).toFixed(1)}L`', 'fmtInr L');
fix(6882, '`\u20b9${(v/1000).toFixed(1)}K`', '`\u20b9${Math.round(rv/1000)}K`', 'fmtInr K');
fix(6883, '`\u20b9${v.toFixed(0)}`', '`\u20b9${rv.toLocaleString("en-IN")}`', 'fmtInr base');

// fmtUsd (lines 6886-6890): round u to whole dollars
fix(6886, 'const u = inr / usdRate;', 'const u = Math.round(inr / usdRate);', 'fmtUsd round');
fix(6887, '(u/1000000).toFixed(2)}M`', '(u/1000000).toFixed(1)}M`', 'fmtUsd M');
fix(6888, '(u/1000).toFixed(1)}K`', 'Math.round(u/1000)}K`', 'fmtUsd K');
fix(6889, '`$${u.toFixed(0)}`', '`$${u.toLocaleString("en-US")}`', 'fmtUsd base');

// KPI tile - USD as primary value, INR as sub
fix(7209,
  'value={fmtInr(totalCbInr)} color={p.green} sub={`${fmtUsd(totalCbInr)} cumulative`}',
  'value={fmtUsd(totalCbInr)} color={p.green} sub={`${fmtInr(totalCbInr)}  INR equiv.`}',
  'KPI value flip');

// PDF tag popup sub-header - flip Chargeback order
fix(7035,
  '\u20b9${tagCbInr.toLocaleString(\'en-IN\',{maximumFractionDigits:0})} / $${tagCbUsd.toFixed(2)}',
  '$${Math.round(tagCbUsd)} / \u20b9${Math.round(Math.round(tagCbUsd)*usdRate).toLocaleString("en-IN")}',
  'tag popup sub-header');

// Overall PDF table - flip column header order
fix(7168,
  '<th>Chargeback (INR)</th><th>Chargeback (USD)</th>',
  '<th>Chargeback (USD)</th><th>Chargeback (INR)</th>',
  'PDF table header order');

// Overall PDF table rows - flip INR/USD order (line 7111/7112)
fix(7111,
  '<td style="color:#16a34a;font-weight:600">${r.chargeback_inr>0?fmtInr(r.chargeback_inr):""}</td>',
  '<td style="color:#16a34a;font-weight:700">${r.chargeback_inr>0?fmtUsd(r.chargeback_inr):""}</td>',
  'PDF row USD primary');
fix(7112,
  '<td style="color:#6b7280;font-size:11px">${r.chargeback_inr>0?fmtUsd(r.chargeback_inr):""}</td>',
  '<td style="color:#6b7280;font-size:11px">${r.chargeback_inr>0?fmtInr(r.chargeback_inr):""}</td>',
  'PDF row INR secondary');

// Overall PDF KPI tile - flip
fix(7165,
  '<div class="kpi-val" style="color:#16a34a">${totInr}</div><div class="kpi-lbl">Total Chargeback</div>',
  '<div class="kpi-val" style="color:#16a34a">${totUsd}</div><div style="font-size:10px;color:#16a34a">${totInr}</div><div class="kpi-lbl">Total Chargeback</div>',
  'PDF KPI flip');

// tag popup per-VM: flip cbInr/cbUsd references in td
fix(7002,
  '${cbInr}${cbUsd}',
  '${cbUsdVal}${cbInrVal}',
  'popup VM row chargeback');

fs.writeFileSync(path, lines.join(EOL));
console.log('\nTotal fixes:', n);
