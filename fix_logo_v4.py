path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# Just find the eye path and replace by position
ph = data.find(b'Portal Header')
eye = b'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'
eidx = data.find(eye, ph)
print(f"Eye at {eidx}, distance from PH: {eidx-ph}")

# Show exact bytes around
print(repr(data[eidx-5:eidx+50]))

# Find <svg before eye
svg_s = data.rfind(b'<svg', eidx-300, eidx)
svg_e = data.find(b'</svg>', eidx) + 6
print(f"SVG: {svg_s} to {svg_e}")

# Find the container div before svg
div_s = data.rfind(b'<div style={{width:40', svg_s-200, svg_s)
print(f"Container div at: {div_s}")
if div_s > 0:
    # The block is from div_s to svg_e + </div>
    # After </svg> there should be </div>
    after_svg = data[svg_e:svg_e+10]
    print(f"After SVG: {repr(after_svg)}")
    block_end = svg_e + after_svg.find(b'>') + 1
    
    old_block = data[div_s:block_end]
    print(f"Old block: {len(old_block)} bytes")
    
    new_block = (b'<div style={{width:50,height:50,borderRadius:12,background:"#fff",'
                 b'display:"flex",alignItems:"center",justifyContent:"center",'
                 b'flexShrink:0,boxShadow:"0 2px 10px rgba(0,0,0,0.12)",overflow:"hidden"}}>'
                 b'<img src="/wipro-logo.jpg" alt="Wipro" style={{width:44,height:44,objectFit:"contain"}} />'
                 b'</div>')
    
    data = data[:div_s] + new_block + data[block_end:]
    open(path, 'wb').write(data)
    print("SUCCESS - replaced sidebar logo")
