const fs = require('fs');
const c = fs.readFileSync('C:/caas-dashboard/frontend/src/App.jsx', 'utf8');

// Check #7
const s1 = 'const vcErrorCount = vcSums.filter(s=>s.status==="error").length;';
console.log('#7 vcErrorCount found:', c.includes(s1));

// Check #1a — includeLicense/includeInternet block
const s2 = '  const [includeLicense, setIncludeLicense] = useState(false);  // OS license\r\n  const [includeInternet, setIncludeInternet] = useState(false); // internet access';
console.log('#1a includeLicense block found:', c.includes(s2));

// Check indented version (4 spaces vs 2 spaces)
const s2b = '  const [includeLicense, setIncludeLicense] = useState(false);  // OS license';
const idx2b = c.indexOf(s2b);
if (idx2b >= 0) {
  console.log('  Found at char:', idx2b);
  console.log('  Next 200 chars:', JSON.stringify(c.substring(idx2b, idx2b+200)));
}

// Check Step 3 network 
const s3 = '  // Step 3 — Network & IP\r\n  const [network,   setNetwork]  = useState("");';
console.log('#1b Step3 found:', c.includes(s3));

// Try variants
const s3alt = '  // Step 3';
const idx3 = c.indexOf(s3alt);
if (idx3 >= 0) {
  console.log('  Step3 alt found at:', idx3);
  console.log('  Context:', JSON.stringify(c.substring(idx3, idx3+100)));
}

// Check license in payload
const s4 = '        include_license:includeLicense,\r\n        license_type:includeLicense?detectedLicType:"",';
console.log('#1d license payload found:', c.includes(s4));

// Check EnvironmentChartsPanel end
const s5 = '      </div>\r\n    </div>\r\n  );\r\n}\r\n\r\n// \u2500\u2500\u2500 OVERVIEW \u2500\u2500\u2500';
console.log('#11 chart panel end found:', c.includes(s5));

// Check platform pill animation line
const s6 = '                      <div style={{width:8,height:8,borderRadius:"50%",background:sc,boxShadow:`0 0 6px ${sc}70`,animation:pl.status==="loading"||pl.status==="healthy"?"pulse 2s infinite":"none"}}/>'; 
console.log('#11 platform pill found:', c.includes(s6));

// Check "Duration" step label context
const durIdx = c.indexOf('<div><label>Duration</label>');
if (durIdx >= 0) {
  console.log('\nDuration section context (before):');
  console.log(JSON.stringify(c.substring(durIdx - 150, durIdx + 50)));
}
