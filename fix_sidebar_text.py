path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()
ph = data.find(b'Portal Header')

# Find gap value near sidebar  
gi = data.find(b'gap:', ph, ph+300)
if gi > 0:
    # Read current gap value
    gap_end = data.find(b'}', gi)
    print(f"Current gap area: {data[gi:gi+10]}")

# The text "Solution Sphere" fontSize:22 - make it 18
old_title = b'fontSize:22,lineHeight:1.05'
ti = data.find(old_title, ph, ph+1000)
if ti > 0:
    data = data[:ti] + b'fontSize:18,lineHeight:1.05' + data[ti+len(old_title):]
    print("Title: 22->18")

# CISS-COE text - make smaller
old_ciss = b'fontSize:11.5,color:p.accent,marginTop:3,letterSpacing:"1.5px"'
ci = data.find(old_ciss, ph, ph+1200)
if ci > 0:
    data = data[:ci] + b'fontSize:10.5,color:p.accent,marginTop:2,letterSpacing:"1px"' + data[ci+len(old_ciss):]
    print("CISS text smaller")

# Lab as a Service - smaller
old_lab = b'fontSize:11,color:p.textMute'
li = data.find(old_lab, ph, ph+1400)
if li > 0:
    data = data[:li] + b'fontSize:10,color:p.textMute' + data[li+len(old_lab):]
    print("Lab text smaller")

open(path, 'wb').write(data)
print("Done")
