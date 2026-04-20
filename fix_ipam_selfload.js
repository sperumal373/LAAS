// fix_ipam_page_selfload.js
// Fix the IPAMPage function to load its own data (no external data prop needed)
// Also fix the <div className="content"> corruption at line 12983

const fs = require('fs');
const filePath = 'C:/caas-dashboard/frontend/src/App.jsx';
const raw = fs.readFileSync(filePath, 'utf8');
const lines = raw.split('\r\n');

// ---- FIX 1: Fix <div className="content"> at line 12983 ----
// Remove the injected JS code from the div opening tag
const divIdx = 12982; // 0-indexed
console.log('Line 12983:', lines[divIdx] ? lines[divIdx].substring(0, 100) : 'N/A');
if (lines[divIdx] && lines[divIdx].includes('className="content">') && lines[divIdx].includes('setVmReqVmwareOnly')) {
  lines[divIdx] = '          <div className="content">';
  console.log('FIX 1: Cleaned <div className="content"> line');
} else {
  console.error('FIX 1 FAILED: unexpected content at line 12983');
  console.log(lines[divIdx]);
}

// ---- FIX 2: Fix IPAMPage render call to not need data prop ----
// Line 12996: {page==="ipam"      &&<IPAMPage currentUser={currentUser} p={p}/>}
// This is actually fine if IPAMPage loads its own data - no changes needed

// ---- FIX 3: Update IPAMPage function to load its own data ----
// Find the IPAMPage function
let ipamPageStart = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('function IPAMPage(')) {
    ipamPageStart = i;
    break;
  }
}
console.log('IPAMPage starts at line:', ipamPageStart + 1);

if (ipamPageStart === -1) {
  console.error('Could not find IPAMPage function');
  process.exit(1);
}

// Check current signature
console.log('IPAMPage signature:', lines[ipamPageStart].substring(0, 100));

// Change signature from ({data, loading, error, cachedAt, currentUser, p}) to ({currentUser, p})
// and add internal state for data loading
if (lines[ipamPageStart].includes('function IPAMPage({data, loading, error, cachedAt, currentUser, p})')) {
  lines[ipamPageStart] = 'function IPAMPage({currentUser, p}) {';
  
  // Now we need to add the data loading state after the opening brace
  // The next few lines should have the existing state declarations
  // Insert: const [data, setData] = useState(null); const [loading, setLoading] = useState(true); const [error, setError] = useState(null); const [cachedAt, setCachedAt] = useState("—");
  // Find the line with "const subnets" to insert after the function declaration
  const insertIdx = ipamPageStart + 1;
  const newStateLines = [
    '  const [data,    setData]    = useState(null);',
    '  const [loading, setLoading] = useState(true);',
    '  const [error,   setError]   = useState(null);',
    '  const [cachedAt, setCachedAt] = useState("—");',
    '  // Load IPAM data on mount',
    '  useEffect(() => {',
    '    setLoading(true); setError(null);',
    '    fetchIPAMSubnets()',
    '      .then(d => { setData(d); setCachedAt(d?.cached_at ? new Date(d.cached_at).toLocaleTimeString() : new Date().toLocaleTimeString()); })',
    '      .catch(e => setError(e.message))',
    '      .finally(() => setLoading(false));',
    '  }, []);',
    '',
  ];
  lines.splice(insertIdx, 0, ...newStateLines);
  console.log('FIX 3: Added data loading state to IPAMPage');
  
  // Also need to update the load function to actually reload data
  // Find "const load = async () => {" in IPAMPage
  for (let i = ipamPageStart; i < ipamPageStart + 60; i++) {
    if (lines[i] && lines[i].includes('const load = async () => {')) {
      // Replace the dummy load function with a real one
      const loadEnd = i + 4; // find the closing }
      for (let j = i; j < i + 10; j++) {
        if (lines[j] && lines[j].trim() === '};') {
          // Replace all load function lines
          const realLoadLines = [
            '  const load = async () => {',
            '    setLoading(true); setError(null);',
            '    try { const d = await fetchIPAMSubnets(); setData(d); setCachedAt(d?.cached_at ? new Date(d.cached_at).toLocaleTimeString() : new Date().toLocaleTimeString()); }',
            '    catch(e) { setError(e.message); }',
            '    finally { setLoading(false); }',
            '  };',
          ];
          lines.splice(i, j - i + 1, ...realLoadLines);
          console.log('FIX 3b: Updated load function to actually load data');
          break;
        }
      }
      break;
    }
  }
  
  // Also need to remove the dummy useEffect that does nothing
  for (let i = ipamPageStart; i < ipamPageStart + 80; i++) {
    if (lines[i] && lines[i].includes('useEffect(() => { load(); }, []);')) {
      // This is good - keep it
      console.log('Found useEffect calling load at line', i+1, '- keeping it');
      break;
    }
  }
  
} else if (lines[ipamPageStart].includes('function IPAMPage({currentUser, p})')) {
  console.log('FIX 3: IPAMPage signature already self-loading');
} else {
  console.log('FIX 3: Unexpected IPAMPage signature:', lines[ipamPageStart]);
}

// ---- Write file ----
const newContent = lines.join('\r\n');
fs.writeFileSync(filePath + '.bak7', raw, 'utf8');
fs.writeFileSync(filePath, newContent, 'utf8');

// ---- Verify ----
const vLines = newContent.split('\r\n');
console.log('New total lines:', vLines.length);
console.log('Line 12983:', vLines[12982] ? vLines[12982].substring(0, 80) : 'N/A');

// Find IPAMPage again
for (let i = 0; i < vLines.length; i++) {
  if (vLines[i].includes('function IPAMPage(')) {
    console.log('IPAMPage at line', i+1, ':', vLines[i].substring(0, 100));
    // Show next 5 lines
    for (let j = i+1; j < i+6; j++) console.log('  +', (j+1), ':', vLines[j] ? vLines[j].substring(0, 80) : '');
    break;
  }
}

console.log('\nDONE');
