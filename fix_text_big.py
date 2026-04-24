path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()
ph = data.find(b'Portal Header')

# Solution Sphere: fontSize:17 x2 -> 24
data = data[:ph] + data[ph:ph+1000].replace(b'fontSize:17,lineHeight:1.15', b'fontSize:24,lineHeight:1.1', 1) + data[ph+1000:]
ph2 = data.find(b'Portal Header')
data = data[:ph2] + data[ph2:ph2+1000].replace(b'fontSize:17,lineHeight:1.05', b'fontSize:24,lineHeight:1.1', 1) + data[ph2+1000:]

# CISS-COE: fontSize:10 -> 13
ph3 = data.find(b'Portal Header')
chunk = data[ph3:ph3+1400]
old_ciss = b'fontSize:10.5,color:p.accent'
if old_ciss not in chunk:
    old_ciss = b'fontSize:10,color:p.accent'
idx = chunk.find(old_ciss)
if idx >= 0:
    abs_idx = ph3 + idx
    new_ciss = b'fontSize:13,color:p.accent'
    data = data[:abs_idx] + new_ciss + data[abs_idx+len(old_ciss):]
    print("CISS: ->13")

# Lab as a Service: fontSize:10 -> 12
ph4 = data.find(b'Portal Header')
chunk2 = data[ph4:ph4+1500]
old_lab = b'fontSize:10,color:p.textMute'
idx2 = chunk2.find(old_lab)
if idx2 >= 0:
    abs2 = ph4 + idx2
    data = data[:abs2] + b'fontSize:12,color:p.textMute' + data[abs2+len(old_lab):]
    print("Lab: ->12")

open(path, 'wb').write(data)
print("Done")
