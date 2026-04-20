f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

# Strategy: inject fRecs computation right after </div> closing of toolbar
# and before the {rLoad ? ...} table section, using a JS expression block
# We'll wrap the entire (rLoad ? loading : table) block in an IIFE so we can
# declare fRecs once cleanly, without the broken double-filter

# Find the rLoad section and the broken filter, and replace with clean approach
old = (
    '                  {rLoad ? <div style={{textAlign:"center",padding:40,color:p.textMute}}>\u23f3 Loading records\u2026</div> : (\n'
    '                    <div style={{overflowX:"auto",borderRadius:8,border:`1px solid ${p.border}`,background:p.panel}}>\n'
    '                      <table style={{width:"100%",borderCollapse:"collapse"}}>\n'
    '                        <thead><tr style={{background:p.surface}}>\n'
    '                          <TH>Hostname</TH><TH w="70px">Type</TH><TH>Data</TH><TH w="90px">TTL</TH>{canWrite&&<TH w="80px">Delete</TH>}\n'
    '                        </tr></thead>\n'
    '                        <tbody>\n'
    '                          {records.filter(r=>!dnsQ||[r.hostname,r.type,r.data].some(v=>String(v||"").toLowerCase().includes(dnsQ.toLowerCase()))).length===0&&<tr><td colSpan={5} style={{padding:24,textAlign:"center",color:p.textMute}}>No matching records</td></tr>}\n'
    '                          {records.filter(r=>!dnsQ||[r.hostname,r.type,r.data].some(v=>String(v||"").toLowerCase().includes(dnsQ.toLowerCase()))).map((r,i)=>('
)

if old in content:
    print('Old found!')
else:
    print('Not found - checking parts...')
    parts = [
        '                  {rLoad ? <div',
        'Loading records\u2026</div> : (',
        'No matching records</td></tr>}',
        'records.filter(r=>!dnsQ',
    ]
    for p in parts:
        print(f'  [{p[:50]}]: {p in content}')
