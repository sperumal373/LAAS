path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()
ph = data.find(b'Portal Header')

# The title div has: fontSize:22,...fontSize:20,lineHeight:1.05
# Replace fontSize:22 first (it comes first)
old1 = b'fontSize:22,lineHeight:1.2'
idx1 = data.find(old1, ph, ph+700)
if idx1 > 0:
    data = data[:idx1] + b'fontSize:17,lineHeight:1.15' + data[idx1+len(old1):]
    print(f"Fixed first fontSize at {idx1}")

# Now find fontSize:20 (second one in same style)
old2 = b'fontSize:20,lineHeight:1.05'
idx2 = data.find(old2, ph, ph+800)
if idx2 > 0:
    data = data[:idx2] + b'fontSize:17,lineHeight:1.05' + data[idx2+len(old2):]
    print(f"Fixed second fontSize at {idx2}")

open(path, 'wb').write(data)
print("Done - title text smaller, logo has more room")
