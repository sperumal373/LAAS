with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")

OLD = 'return(<button key={k} onClick={()=>setTab(k)} style={{background:"transparent",border:"none",borderBottom:"2px solid "+(tab===k?s.cyan:"transparent"),color:tab===k?s.cyan:s.textMute,padding:"8px 14px",fontSize:12,fontWeight:tab===k?700:400,cursor:"pointer",transition:"all .15s"}}>{tb}</button>);'
NEW = 'return(<button key={k} onClick={()=>setTab(k)} style={{background:"transparent",border:"none",borderBottom:"3px solid "+(tab===k?s.cyan:"transparent"),color:tab===k?s.cyan:"#e2e8f0",padding:"10px 18px",fontSize:14,fontWeight:tab===k?700:500,cursor:"pointer",transition:"color .15s,border-color .15s"}}>{tb}</button>);'

if OLD in t:
    t = t.replace(OLD, NEW, 1)
    print("Replaced OK")
else:
    print("NOT FOUND")

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(t.encode("utf-8-sig"))