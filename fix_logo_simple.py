path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# Find Portal Header, then find the eye SVG nearby
ph = data.find(b'Portal Header')
eye_path = b'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'
eidx = data.find(eye_path, ph, ph+1000)
print(f"Eye at {eidx} (offset {eidx-ph} from Portal Header)")

# Find full svg tag
svg_s = data.rfind(b'<svg ', eidx-300, eidx)
svg_e = data.find(b'</svg>', eidx) + 6
old_svg = data[svg_s:svg_e]
print(f"Old SVG: {len(old_svg)} bytes")
print(f"First 80: {old_svg[:80]}")

# Replace with simple Wipro text (no external image needed)
new_content = b'<span style={{fontSize:18,fontWeight:900,color:"#2d1a6e",fontFamily:"Arial Black"}}>W</span>'

data = data[:svg_s] + new_content + data[svg_e:]

# Now change the container bg from gradient to white
# Container is before the SVG
chunk_before = data[ph:ph+800]
old_bg = b'background:`linear-gradient(135deg,${p.accent},${p.cyan})`'
idx = chunk_before.find(old_bg)
if idx >= 0:
    abs_idx = ph + idx
    new_bg = b'background:"#fff"'
    data = data[:abs_idx] + new_bg + data[abs_idx+len(old_bg):]
    print("Changed bg to white")

    # Make container bigger
    chunk2 = data[ph:ph+800]
    old_sz = b'width:40,height:40'
    si = chunk2.find(old_sz)
    if si >= 0:
        abs_si = ph + si
        data = data[:abs_si] + b'width:50,height:50' + data[abs_si+len(old_sz):]
        print("Made container 50x50")

open(path, 'wb').write(data)
print("Saved - now test build")
