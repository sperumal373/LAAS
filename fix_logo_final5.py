path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

ph = data.find(b'Portal Header')
eye = b'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'
eye_idx = data.find(eye, ph, ph+1000)
print(f"Portal Header at {ph}, Eye at {eye_idx}")

svg_start = data.rfind(b'<svg', eye_idx-200, eye_idx)
svg_end = data.find(b'</svg>', eye_idx) + 6

wipro = b'<img src="/wipro-logo.jpg" alt="Wipro" style={{width:40,height:40,borderRadius:6,objectFit:"contain"}} />'
data = data[:svg_start] + wipro + data[svg_end:]

# Fix container: remove gradient, white bg, bigger
old_c = b'width:40,height:40,borderRadius:10,background:`linear-gradient(135deg,${p.accent},${p.cyan})`'
new_c = b'width:50,height:50,borderRadius:12,background:"#fff"'
ci = data.find(old_c, ph, ph+800)
if ci > 0:
    data = data[:ci] + new_c + data[ci+len(old_c):]
    print("Fixed container")

open(path, 'wb').write(data)
print("Done")
