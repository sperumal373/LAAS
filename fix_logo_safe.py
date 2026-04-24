path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# Find sidebar Portal Header section
ph = data.find(b'Portal Header')
print(f"Portal Header at: {ph}")

# Find the eye SVG path near it
eye = b'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'
eye_idx = data.find(eye, ph)
print(f"Eye path at: {eye_idx}")

if eye_idx > 0 and eye_idx - ph < 500:
    # Find the <svg start and </svg> end
    svg_start = data.rfind(b'<svg', max(0, eye_idx-200), eye_idx)
    svg_end = data.find(b'</svg>', eye_idx) + 6
    print(f"SVG from {svg_start} to {svg_end}")
    
    # Replace just the SVG with a bigger Wipro img
    wipro = b'<img src="/wipro-logo.jpg" alt="Wipro" style={{width:36,height:36,borderRadius:6,objectFit:"contain"}} />'
    data = data[:svg_start] + wipro + data[svg_end:]
    
    # Now fix the container: change gradient bg to white, make bigger
    # Find the container div (has borderRadius:10,background:linear-gradient)
    container_bg = b'background:`linear-gradient(135deg,${p.accent},${p.cyan})`'
    ci = data.rfind(container_bg, max(0, ph), ph+600)
    if ci > 0:
        data = data.replace(
            b'width:40,height:40,borderRadius:10,background:`linear-gradient(135deg,${p.accent},${p.cyan})`,display:"flex",alignItems:"center",justifyContent:"center",fontSize:25,flexShrink:0,boxShadow:`0 4px 14px ${p.accent}50`',
            b'width:48,height:48,borderRadius:12,background:"#fff",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,boxShadow:"0 2px 10px rgba(0,0,0,0.15)",overflow:"hidden"',
            1
        )
        print("Fixed container")
    else:
        print("Container bg not found, trying alternate")
        # Just the width/height
        wh = data.find(b'width:40,height:40', max(0,ph), ph+600)
        if wh > 0:
            print(f"Found 40x40 at {wh}")

    open(path, 'wb').write(data)
    print("Done - sidebar logo fixed")
else:
    print("Eye not found near Portal Header")
    # Check if already replaced
    wi = data.find(b'wipro-logo', ph, ph+600)
    if wi > 0:
        print("Already has wipro-logo, just need to make bigger")
        # Find the img style
        old_style = b'style={{width:32,height:32,borderRadius:6,objectFit:"contain"}}'
        new_style = b'style={{width:36,height:36,borderRadius:6,objectFit:"contain"}}'
        si = data.find(old_style, ph, ph+600)
        if si > 0:
            data = data[:si] + new_style + data[si+len(old_style):]
        # Fix container bg
        old_bg = b'background:`linear-gradient(135deg,${p.accent},${p.cyan})`'
        new_bg = b'background:"#fff"'
        bi = data.find(old_bg, ph, ph+500)
        if bi > 0:
            data = data[:bi] + new_bg + data[bi+len(old_bg):]
            # Also fix container size
            old_sz = b'width:38,height:38'
            new_sz = b'width:48,height:48'
            szi = data.find(old_sz, ph, ph+500)
            if szi > 0:
                data = data[:szi] + new_sz + data[szi+len(old_sz):]
        open(path, 'wb').write(data)
        print("Done - made bigger + white bg")
