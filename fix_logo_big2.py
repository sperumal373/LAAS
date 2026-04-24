path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# Find the wipro img tag
idx = data.find(b'wipro-logo.jpg')
print(f"wipro-logo at: {idx}")
# Go back to find the container div
chunk = data[max(0,idx-300):idx+100]
print(chunk)
print("---")

# Find the container div start - look for the 40x40 div
start = data.rfind(b'width:40,height:40', max(0,idx-300), idx)
if start < 0:
    start = data.rfind(b'width:48', max(0,idx-300), idx)
print(f"Container style at: {start}")
if start > 0:
    # Go back to find <div
    div_start = data.rfind(b'<div', max(0,start-100), start+1)
    div_end = data.find(b'</div>', idx)
    print(f"div from {div_start} to {div_end+6}")
    old_block = data[div_start:div_end+6]
    
    new_block = b'<div style={{width:48,height:48,borderRadius:12,background:"#fff",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,boxShadow:"0 2px 10px rgba(0,0,0,0.15)",padding:2}}><img src="/wipro-logo.jpg" alt="Wipro" style={{width:44,height:44,borderRadius:10,objectFit:"contain"}} /></div>'
    
    data = data[:div_start] + new_block + data[div_end+6:]
    open(path, 'wb').write(data)
    print("Done - bigger logo, white bg")
