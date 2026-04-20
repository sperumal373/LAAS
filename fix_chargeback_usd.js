const fs = require('fs');
const path = 'C:/caas-dashboard/frontend/src/App.jsx';
const src = fs.readFileSync(path, 'utf8');
const EOL = '\r\n';
const lines = src.split(EOL);
let changes = 0;

function fix(idx, from, to, label) {
  if (lines[idx] && lines[idx].includes(from)) {
    lines[idx] = lines[idx].replace(from, to);
    console.log('FIX ' + label + ' at line ' + (idx+1));
    changes++;
  } else {
    console.log('MISS ' + label + ' at line ' + (idx+1) + ': ' + (lines[idx]||'').trim().substring(0,80));
  }
}

// 1. PricingFieldRow USD display (line 2370, idx 2369)
fix(2369,
  '${((val)/(usdRate||83.5)).toFixed(2)}/mo',
  '${Math.round(val/(usdRate||83.5))}/mo',
  '#1 PricingFieldRow USD');

// 2. Step1 license price hint (line 5661, idx 5660)
fix(5660,
  '({Number(inr).toLocaleString("en-IN")}/VM/mo &nbsp;/&nbsp; ${(inr/usd).toFixed(0)}/VM/mo)',
  '(${Math.round(inr/usd)}/VM/mo  {Math.round(Math.round(inr/usd)*usd).toLocaleString("en-IN")}/VM/mo)',
  '#2 Step1 license');

// 3. Internet checkbox price (line 6018, idx 6017)
fix(6017,
  '{Number(inr).toLocaleString("en-IN")} / ${(inr/usd).toFixed(0)} per VM/mo',
  '${Math.round(inr/usd)}/VM/mo  {Math.round(Math.round(inr/usd)*usd).toLocaleString("en-IN")}/VM/mo',
  '#3 Internet checkbox');

// 4. Disk type badge (line 6075, idx 6074)
fix(6074,
  '{diskType==="SSD"?" SSD":" HDD"} @ {diskRate}/GB/mo',
  '{diskType==="SSD"?" SSD":" HDD"} @ ${Math.round(diskRate/usd)}/GB/mo ({Math.round(Math.round(diskRate/usd)*usd)}/GB/mo)',
  '#4 Disk badge');

// 5. License add-on badge (line 6079, idx 6078)
fix(6078,
  '+{licRate.toLocaleString("en-IN")}/mo / ${(licRate/usd).toFixed(0)}/mo',
  '+${Math.round(licRate/usd)}/mo ({Math.round(Math.round(licRate/usd)*usd).toLocaleString("en-IN")}/mo)',
  '#5 License badge');

// 6. Internet add-on badge (line 6083, idx 6082)
fix(6082,
  ' Internet +{inetRate.toLocaleString("en-IN")}/mo / ${(inetRate/usd).toFixed(0)}/mo',
  ' Internet +${Math.round(inetRate/usd)}/mo ({Math.round(Math.round(inetRate/usd)*usd).toLocaleString("en-IN")}/mo)',
  '#6 Internet badge');

// 7a. Weekly estimate (line 6087, idx 6086) - Daily
fix(6086,
  '<span>Daily: <b>{Math.round(monthly/30).toLocaleString("en-IN")}</b> / ${(monthly/30/usd).toFixed(2)}</span>',
  '<span>Daily: <b>${Math.round(monthly/30/usd)}</b> / {Math.round(Math.round(monthly/30/usd)*usd).toLocaleString("en-IN")}</span>',
  '#7a Daily');

// 7b. Monthly estimate (line 6088, idx 6087)
fix(6087,
  '<span>Monthly: <b>{Math.round(monthly).toLocaleString("en-IN")}</b> / ${(monthly/usd).toFixed(2)}</span>',
  '<span>Monthly: <b>${Math.round(monthly/usd)}</b> / {Math.round(Math.round(monthly/usd)*usd).toLocaleString("en-IN")}</span>',
  '#7b Monthly');

// 7c. Yearly estimate (line 6089, idx 6088)
fix(6088,
  '<span>Yearly: <b>{Math.round(monthly*12).toLocaleString("en-IN")}</b> / ${(monthly*12/usd).toFixed(0)}</span>',
  '<span>Yearly: <b>${Math.round(monthly*12/usd)}</b> / {Math.round(Math.round(monthly*12/usd)*usd).toLocaleString("en-IN")}</span>',
  '#7c Yearly');

// 8a. Project utilization CSV (line 6946, idx 6945) - INR col
fix(6945,
  'r.chargeback_inr != null ? r.chargeback_inr.toFixed(2) : ""',
  'r.chargeback_inr != null ? Math.round(r.chargeback_inr).toString() : ""',
  '#8a CSV INR');

// 8b. Project utilization CSV (line 6947, idx 6946) - USD col
fix(6946,
  'r.chargeback_usd != null ? r.chargeback_usd.toFixed(2) : ""',
  'r.chargeback_usd != null ? Math.round(r.chargeback_usd).toString() : ""',
  '#8b CSV USD');

// 8c. PDF export INR (line 6965, idx 6964)
fix(6964,
  'r.chargeback_inr != null ? `${r.chargeback_inr.toFixed(2)}` : "N/A"',
  'r.chargeback_inr != null ? `${Math.round(r.chargeback_inr).toLocaleString("en-IN")}` : "N/A"',
  '#8c PDF INR');

// 8d. PDF export USD (line 6966, idx 6965)
fix(6965,
  'r.chargeback_usd != null ? `$${r.chargeback_usd.toFixed(2)}` : "N/A"',
  'r.chargeback_usd != null ? `$${Math.round(r.chargeback_usd)}` : "N/A"',
  '#8d PDF USD');

// 8e. Display cbUsd in VM popup (line 6973, idx 6972)
fix(6972,
  'const cbUsd = r.chargeback_usd != null ? ` / $${Number(r.chargeback_usd).toFixed(0)}` : "";',
  'const cbUsd = r.chargeback_usd != null ? ` / $${Math.round(r.chargeback_usd)}` : "";',
  '#8e cbUsd display');

fs.writeFileSync(path, lines.join(EOL));
console.log('\nTotal changes:', changes);
