path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# Find the eye path signature
eye_path = b'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z'
count = data.count(eye_path)
print(f"Found {count} eye SVG occurrences")

wipro_img = b'<img src="https://logo.clearbit.com/wipro.com" alt="Wipro" style={{width:24,height:24,borderRadius:4,objectFit:"contain"}} />'

idx = 0
replaced = 0
while True:
    idx = data.find(eye_path, idx)
    if idx < 0:
        break
    # Find the <svg that starts this eye
    svg_start = data.rfind(b'<svg', max(0, idx-300), idx)
    # Find the </svg> that ends it
    svg_end = data.find(b'</svg>', idx)
    if svg_start >= 0 and svg_end >= 0:
        svg_end += 6  # include </svg>
        old_svg = data[svg_start:svg_end]
        print(f"  Replacing {len(old_svg)} bytes at {svg_start}")
        data = data[:svg_start] + wipro_img + data[svg_end:]
        replaced += 1
        idx = svg_start + len(wipro_img)
    else:
        idx += 1

open(path, 'wb').write(data)
print(f"Done - replaced {replaced} eye icons with Wipro logo")
