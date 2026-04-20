f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

# Step A: Remove the IIFE filter from inside JSX tbody and replace with simple filtered map
old_iife = (
    '                          {(()=>{ const fRecs=dnsQ?records.filter'
    '(r=>[r.hostname,r.type,r.data].some(v=>String(v||"").toLowerCase()'
    '.includes(dnsQ.toLowerCase()))):records; return fRecs.length===0?'
    '(<tr><td colSpan={5} style={{padding:24,textAlign:"center",color:p'
    '.textMute}}>{dnsQ?("No records match \u201c"+dnsQ+"\u201d"):"No records"}'
    '</td></tr>):fRecs.map((r,i)=>('
)
new_inline = (
    '                          {records.filter(r=>!dnsQ||[r.hostname,r.type,r.data]'
    '.some(v=>String(v||"").toLowerCase().includes(dnsQ.toLowerCase())))'
    '.length===0&&<tr><td colSpan={5} style={{padding:24,textAlign:"center",color:p.textMute}}>No matching records</td></tr>}\n'
    '                          {records.filter(r=>!dnsQ||[r.hostname,r.type,r.data]'
    '.some(v=>String(v||"").toLowerCase().includes(dnsQ.toLowerCase())))'
    '.map((r,i)=>('
)

if old_iife in content:
    content = content.replace(old_iife, new_inline, 1)
    print('Step A OK - IIFE replaced with simple filter')
else:
    print('Step A SKIP - checking alternatives...')
    idx = content.find('fRecs=dnsQ')
    if idx > 0:
        print(repr(content[max(0,idx-30):idx+200]))

# Step B: Fix the closing - was )); })()}, now just ))}
old_close = '                          )); })()}'
new_close = '                          ))}'

if old_close in content:
    content = content.replace(old_close, new_close, 1)
    print('Step B OK - closing fixed')
else:
    print('Step B SKIP')
    # check what exists
    idx = content.find('})()}')
    print('})()}  found:', idx)
    idx2 = content.find(')); })()')
    print(')); })() found:', idx2)

with open(f, 'w', encoding='utf-8') as fh:
    fh.write(content)
print('Saved.')
