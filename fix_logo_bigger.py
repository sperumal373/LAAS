path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# Make container bigger and image bigger
old_container = b'width:50,height:50,borderRadius:12,background:"#fff",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,boxShadow:"0 2px 10px rgba(0,0,0,0.12)",overflow:"hidden"'
new_container = b'width:56,height:56,borderRadius:12,background:"#fff",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,boxShadow:"0 2px 10px rgba(0,0,0,0.12)",overflow:"hidden"'

old_img = b'width:44,height:44,objectFit:"contain"'
new_img = b'width:52,height:52,objectFit:"contain"'

# Reduce gap between logo and text, shrink text slightly to fit
old_gap = b'gap:11'
new_gap = b'gap:8'

ph = data.find(b'Portal Header')
# Only replace near Portal Header (sidebar)
ci = data.find(old_container, ph, ph+600)
if ci > 0:
    data = data[:ci] + new_container + data[ci+len(old_container):]
    print("Container: 50->56")

ii = data.find(old_img, ph, ph+700)
if ii > 0:
    data = data[:ii] + new_img + data[ii+len(old_img):]
    print("Image: 44->52")

gi = data.find(old_gap, ph, ph+400)
if gi > 0:
    data = data[:gi] + new_gap + data[gi+len(old_gap):]
    print("Gap: 11->8")

# Make Solution Sphere text slightly smaller
old_fs = b'fontSize:26,lineHeight:1.05'
fi = data.find(old_fs, ph, ph+1000)
if fi > 0:
    data = data[:fi] + b'fontSize:22,lineHeight:1.05' + data[fi+len(old_fs):]
    print("Title font: 26->22")

open(path, 'wb').write(data)
print("Done")
