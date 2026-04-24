path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()
ph = data.find(b'Portal Header')

old = b'fontSize:12,color:p.textMute,marginTop:1,letterSpacing:".3px",fontWeight:400,fontStyle:"italic",opacity:0.65'
new = b'fontSize:14,color:p.cyan,marginTop:2,letterSpacing:".5px",fontWeight:700,fontStyle:"normal",opacity:1'

idx = data.find(old, ph, ph+1500)
if idx > 0:
    data = data[:idx] + new + data[idx+len(old):]
    print("Fixed")
else:
    print("Not found, checking...")
    chunk = data[ph+1050:ph+1250]
    print(chunk)

open(path, 'wb').write(data)
print("Done")
