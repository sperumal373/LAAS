f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

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

# Replace with pre-computed fRecs using an outer IIFE wrapping the whole loading/table block
new = (
    '                  {(()=>{\n'
    '                    const qLow=dnsQ.toLowerCase();\n'
    '                    const fRecs=dnsQ?records.filter(r=>[r.hostname,r.type,r.data].some(v=>String(v||"").toLowerCase().indexOf(qLow)>=0)):records;\n'
    '                    return rLoad ? <div style={{textAlign:"center",padding:40,color:p.textMute}}>\u23f3 Loading records\u2026</div> : (\n'
    '                    <div style={{overflowX:"auto",borderRadius:8,border:`1px solid ${p.border}`,background:p.panel}}>\n'
    '                      <table style={{width:"100%",borderCollapse:"collapse"}}>\n'
    '                        <thead><tr style={{background:p.surface}}>\n'
    '                          <TH>Hostname</TH><TH w="70px">Type</TH><TH>Data</TH><TH w="90px">TTL</TH>{canWrite&&<TH w="80px">Delete</TH>}\n'
    '                        </tr></thead>\n'
    '                        <tbody>\n'
    '                          {fRecs.length===0&&<tr><td colSpan={5} style={{padding:24,textAlign:"center",color:p.textMute}}>{dnsQ?"No records match your search":"No records"}</td></tr>}\n'
    '                          {fRecs.map((r,i)=>('
)

if old in content:
    content = content.replace(old, new, 1)
    print('Step 1 OK')
else:
    print('Step 1 FAILED')

# Also fix the closing - was just ))}, now needs to close the IIFE: )); })()}
old_close = (
    '                          ))}\n'
    '                        </tbody>\n'
    '                      </table>\n'
    '                    </div>\n'
    '                  </>\n'
)
new_close = (
    '                          ))}\n'
    '                        </tbody>\n'
    '                      </table>\n'
    '                    </div>\n'
    '                    );\n'
    '                  })()}\n'
    '                  </>\n'
)

if old_close in content:
    content = content.replace(old_close, new_close, 1)
    print('Step 2 OK - closing IIFE fixed')
else:
    print('Step 2 SKIP - checking...')
    idx = content.find('                        </tbody>')
    print(repr(content[max(0,idx-20):idx+200]))

with open(f, 'w', encoding='utf-8') as fh:
    fh.write(content)
print('File saved.')
