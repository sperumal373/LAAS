const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
let changes = 0;

function fixLine(idx, searchPart, replacement, label) {
  if (lines[idx] && lines[idx].includes(searchPart)) {
    lines[idx] = lines[idx].replace(searchPart, replacement);
    console.log('FIX ' + label);
    changes++;
  } else {
    console.log('MISS ' + label + ': ' + (lines[idx]||'').substring(0,80));
  }
}

// #2 Step1 license hint (0-indexed 5660)
fixLine(5660,
  '({Number(inr).toLocaleString("en-IN")}/VM/mo \u00a0/\u00a0 ${(inr/usd).toFixed(0)}/VM/mo)',
  '(${Math.round(inr/usd)}/VM/mo \u2014 \u20b9{Math.round(Math.round(inr/usd)*usd).toLocaleString("en-IN")}/VM/mo)',
  '#2 license hint');

// #4 Disk badge  just replace the rate part (0-indexed 6074)
fixLine(6074,
  '\u20b9{diskRate}/GB/mo',
  '${Math.round(diskRate/usd)}/GB/mo (\u20b9{Math.round(Math.round(diskRate/usd)*usd)}/GB/mo)',
  '#4 disk badge');

// #5 License add-on badge (0-indexed 6078)
fixLine(6078,
  '+\u20b9{licRate.toLocaleString("en-IN")}/mo / ${(licRate/usd).toFixed(0)}/mo',
  '+${Math.round(licRate/usd)}/mo (\u20b9{Math.round(Math.round(licRate/usd)*usd).toLocaleString("en-IN")}/mo)',
  '#5 license badge');

// #6 Internet add-on badge (0-indexed 6082)
fixLine(6082,
  '+\u20b9{inetRate.toLocaleString("en-IN")}/mo / ${(inetRate/usd).toFixed(0)}/mo',
  '+${Math.round(inetRate/usd)}/mo (\u20b9{Math.round(Math.round(inetRate/usd)*usd).toLocaleString("en-IN")}/mo)',
  '#6 internet badge');

// #7a Daily (0-indexed 6086)
fixLine(6086,
  '<span>Daily: <b>\u20b9{Math.round(monthly/30).toLocaleString("en-IN")}</b> / ${(monthly/30/usd).toFixed(2)}</span>',
  '<span>Daily: <b>${Math.round(monthly/30/usd)}</b> / \u20b9{Math.round(Math.round(monthly/30/usd)*usd).toLocaleString("en-IN")}</span>',
  '#7a daily');

// #7b Monthly (0-indexed 6087)
fixLine(6087,
  '<span>Monthly: <b>\u20b9{Math.round(monthly).toLocaleString("en-IN")}</b> / ${(monthly/usd).toFixed(2)}</span>',
  '<span>Monthly: <b>${Math.round(monthly/usd)}</b> / \u20b9{Math.round(Math.round(monthly/usd)*usd).toLocaleString("en-IN")}</span>',
  '#7b monthly');

// #7c Yearly (0-indexed 6088)
fixLine(6088,
  '<span>Yearly: <b>\u20b9{Math.round(monthly*12).toLocaleString("en-IN")}</b> / ${(monthly*12/usd).toFixed(0)}</span>',
  '<span>Yearly: <b>${Math.round(monthly*12/usd)}</b> / \u20b9{Math.round(Math.round(monthly*12/usd)*usd).toLocaleString("en-IN")}</span>',
  '#7c yearly');

// #8c PDF INR (0-indexed 6964)
fixLine(6964,
  'r.chargeback_inr.toFixed(2)}` : "N/A"',
  'Math.round(r.chargeback_usd)*((typeof usdRate!=="undefined"?usdRate:83.5)).toLocaleString("en-IN")}` : "N/A"',
  '#8c pdf inr');

fs.writeFileSync(path, lines.join(EOL));
console.log('\nTotal changes:', changes);
