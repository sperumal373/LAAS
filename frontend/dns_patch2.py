f = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(f, encoding='utf-8') as fh:
    content = fh.read()

# Add search bar between title and buttons in the DNS records toolbar
old = (
    '                  <div style={{display:"flex",alignItems:"center",'
    'justifyContent:"space-between",marginBottom:10,flexWrap:"wrap",gap:6}}>\n'
    '                    <span style={{fontWeight:700,fontSize:14,color:p.text}}>'
    '\U0001f4cb Records: <span style={{color:p.accent}}>{selZone}</span></span>\n'
    '                    <div style={{display:"flex",gap:6}}>\n'
    '                      <button onClick={()=>loadRecords(selZone)} style={btn(p.grey,true)}>'
    '\u21ba Refresh</button>'
)

new = (
    '                  <div style={{display:"flex",alignItems:"center",'
    'justifyContent:"space-between",marginBottom:10,flexWrap:"wrap",gap:6}}>\n'
    '                    <span style={{fontWeight:700,fontSize:14,color:p.text,flexShrink:0}}>'
    '\U0001f4cb Records: <span style={{color:p.accent}}>{selZone}</span></span>\n'
    '                    {/* Search bar */}\n'
    '                    <div style={{position:"relative",flex:1,minWidth:160,maxWidth:320,margin:"0 8px"}}>\n'
    '                      <span style={{position:"absolute",left:9,top:"50%",transform:"translateY(-50%)",fontSize:12,color:p.textMute,pointerEvents:"none"}}>\U0001f50d</span>\n'
    '                      <input\n'
    '                        placeholder="Search hostname, type or data\u2026"\n'
    '                        value={dnsQ}\n'
    '                        onChange={e=>setDnsQ(e.target.value)}\n'
    '                        style={{...inp,paddingLeft:28,paddingRight:dnsQ?28:10,height:30,fontSize:12,width:"100%"}}\n'
    '                      />\n'
    '                      {dnsQ&&<button onClick={()=>setDnsQ("")} title="Clear search"\n'
    '                        style={{position:"absolute",right:6,top:"50%",transform:"translateY(-50%)",background:"none",border:"none",color:p.textMute,cursor:"pointer",fontSize:13,padding:0,lineHeight:1}}>\u2715</button>}\n'
    '                    </div>\n'
    '                    <div style={{display:"flex",gap:6,flexShrink:0}}>\n'
    '                      <button onClick={()=>loadRecords(selZone)} style={btn(p.grey,true)}>'
    '\u21ba Refresh</button>'
)

if old in content:
    content = content.replace(old, new, 1)
    print('Search bar added successfully!')
else:
    print('ERROR: target string not found')
    idx = content.find('\U0001f4cb Records:')
    if idx > 0:
        print('Found Records: at index', idx)
        print(repr(content[idx-100:idx+200]))

with open(f, 'w', encoding='utf-8') as fh:
    fh.write(content)
print('File saved.')
