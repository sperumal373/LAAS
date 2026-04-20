import sys

f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

#  Step 1: add dnsQ state 
old1 = '  const [createPtr,  setCreatePtr]  = useState(false);'
new1 = (
    '  const [createPtr,  setCreatePtr]  = useState(false);\n'
    '  const [dnsQ,       setDnsQ]       = useState("");'
)
if old1 in content:
    content = content.replace(old1, new1, 1)
    print('Step 1 OK - dnsQ state added')
else:
    print('Step 1 SKIP - already patched or not found')

#  Step 2: Replace the records panel section 
old2 = (
    '            {/* Records panel */}\n'
    '            <div style={{flex:1,minWidth:0}}>\n'
    '              {!selZone ? (\n'
    '                <div style={{textAlign:"center",padding:60,color:p.textMute}}> Loading records</div> : (\n'
    '                  <div style={{overflowX:"auto",borderRadius:8,border:`1px solid ${p.border}`,background:p.panel}}>\n'
    '                    <table style={{width:"100%",borderCollapse:"collapse"}}>\n'
    '                        <thead><tr style={{background:p.surface}}>\n'
    '                          <TH>Hostname</TH><TH w="70px">Type</TH><TH>Data</TH><TH w="90px">TTL</TH>{canWrite&&<TH w="80px">Delete</TH>}'
)
new2 = (
    '            {/* Records panel */}\n'
    '            <div style={{flex:1,minWidth:0}}>\n'
    '              {!selZone ? (\n'
    '                <div style={{textAlign:"center",padding:60,color:p.textMute}}> Loading records</div> : (\n'
    '                  <>\n'
    '                  {/* DNS search + toolbar */}\n'
    '                  <div style={{display:"flex",gap:8,alignItems:"center",marginBottom:10,flexWrap:"wrap"}}>\n'
    '                    <div style={{position:"relative",flex:1,minWidth:160}}>\n'
    '                      <span style={{position:"absolute",left:9,top:"50%",transform:"translateY(-50%)",fontSize:13,color:p.textMute,pointerEvents:"none"}}></span>\n'
    '                      <input\n'
    '                        placeholder="Search hostname, type or data"\n'
    '                        value={dnsQ}\n'
    '                        onChange={e=>setDnsQ(e.target.value)}\n'
    '                        style={{...inp,paddingLeft:30,width:"100%"}}\n'
    '                      />\n'
    '                    </div>\n'
    '                    {dnsQ&&<button onClick={()=>setDnsQ("")} style={btn(p.grey,true)}> Clear</button>}\n'
    '                    <button onClick={()=>loadRecords(selZone)} style={btn(p.cyan,true)}> Refresh</button>\n'
    '                    {canWrite&&<button onClick={()=>{setRecForm({hostname:"",rtype:"A",data:"",ttl:3600});setDNSMsg(null);setCreatePtr(false);setAddRec(true);}} style={btn(p.green,true)}>+ Add Record</button>}\n'
    '                  </div>\n'
    '                  {/* Records table */}\n'
    '                  <div style={{overflowX:"auto",borderRadius:8,border:`1px solid ${p.border}`,background:p.panel}}>\n'
    '                    <table style={{width:"100%",borderCollapse:"collapse"}}>\n'
    '                        <thead><tr style={{background:p.surface}}>\n'
    '                          <TH>Hostname</TH><TH w="70px">Type</TH><TH>Data</TH><TH w="90px">TTL</TH>{canWrite&&<TH w="80px">Delete</TH>}'
)
if old2 in content:
    content = content.replace(old2, new2, 1)
    print('Step 2 OK - search toolbar added')
else:
    print('Step 2 SKIP - not found, trying alternate match...')
    # Try finding just the key anchor
    anchor = '{/* Records panel */}'
    idx = content.find(anchor)
    print(f'  anchor at index: {idx}')
    print(repr(content[idx:idx+400]))

#  Step 3: Replace the records.map to filtered map 
old3 = (
    '                          {records.length===0&&<tr><td colSpan={5} style={{padding:24,textAlign:"center",color:p.textMute}}>No records</td></tr>}\n'
    '                          {records.map((r,i)=>('
)
new3 = (
    '                          {(()=>{ const fRecs=dnsQ?records.filter(r=>[r.hostname,r.type,r.data].some(v=>String(v||"").toLowerCase().includes(dnsQ.toLowerCase()))):records; return fRecs.length===0?(<tr><td colSpan={5} style={{padding:24,textAlign:"center",color:p.textMute}}>{dnsQ?`No records match "${dnsQ}"`:"No records"}</td></tr>):fRecs.map((r,i)=>('
)
if old3 in content:
    content = content.replace(old3, new3, 1)
    print('Step 3 OK - filter logic added')
else:
    print('Step 3 SKIP - not found')

#  Step 4: Close the filtered map IIFE + close new <> fragment 
old4 = (
    '                          ))}\n'
    '                        </tbody>\n'
    '                      </table>\n'
    '                    </div>\n'
    '                  )}\n'
    '                </>\n'
    '              )}\n'
    '            </div>'
)
new4 = (
    '                          )); })()}\n'
    '                        </tbody>\n'
    '                      </table>\n'
    '                    </div>\n'
    '                  </>\n'
    '                )}\n'
    '            </div>'
)
if old4 in content:
    content = content.replace(old4, new4, 1)
    print('Step 4 OK - closing braces fixed')
else:
    print('Step 4 SKIP - not found, checking what is there...')
    idx = content.find('                        </tbody>')
    if idx > 0:
        print(repr(content[idx-100:idx+300]))

with open(f, 'w', encoding='utf-8') as fh:
    fh.write(content)
print('File saved.')
