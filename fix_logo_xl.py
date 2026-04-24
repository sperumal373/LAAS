path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()
ph = data.find(b'Portal Header')

# Container 56->64, image 52->58, gap 8->6, title font smaller
changes = [
    (b'width:56,height:56', b'width:64,height:64'),
    (b'width:52,height:52', b'width:58,height:58'),
    (b'gap:8', b'gap:6'),
    (b'fontSize:22,lineHeight:1.05', b'fontSize:20,lineHeight:1.05'),
]
for old, new in changes:
    idx = data.find(old, ph, ph+1000)
    if idx > 0:
        data = data[:idx] + new + data[idx+len(old):]
        print(f"  {old[:30]} -> {new[:30]}")

open(path, 'wb').write(data)
print("Done")
