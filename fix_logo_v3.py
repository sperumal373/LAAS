path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# Exact old block in sidebar (container div + eye SVG + closing div)
old = (b'<div style={{width:40,height:40,borderRadius:10,background:`linear-gradient(135deg,${p.accent},${p.cyan})`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:25,flexShrink:0,boxShadow:`0 4px 14px ${p.accent}50`}}>'
       b'<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{filter:"drop-shadow(0 0 3px rgba(255,255,255,0.6))"}}>'
       b'<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>'
       b'<circle cx="12" cy="12" r="3.5"/>'
       b'<circle cx="12" cy="12" r="1" fill="white"/>'
       b'</svg></div>')

new = (b'<div style={{width:50,height:50,borderRadius:12,background:"#fff",'
       b'display:"flex",alignItems:"center",justifyContent:"center",'
       b'flexShrink:0,boxShadow:"0 2px 10px rgba(0,0,0,0.12)",overflow:"hidden"}}>'
       b'<img src="/wipro-logo.jpg" alt="Wipro" style={{width:44,height:44,objectFit:"contain"}} />'
       b'</div>')

count = data.count(old)
print(f"Found {count} exact matches")

# Replace only near Portal Header (first occurrence)
idx = data.find(old)
if idx > 0:
    data = data[:idx] + new + data[idx+len(old):]
    open(path, 'wb').write(data)
    print(f"Replaced at byte {idx}")
else:
    print("Not found - dumping nearby bytes for debug")
