path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# There are multiple wipro-logo.jpg references - find all
idx = 0
positions = []
while True:
    idx = data.find(b'wipro-logo.jpg', idx)
    if idx < 0: break
    positions.append(idx)
    idx += 1
print(f"Found {len(positions)} wipro-logo references")

# For each, find the container div and replace
# Work in reverse to preserve positions
for pos in reversed(positions):
    # Find the <div that contains the img
    div_start = data.rfind(b'<div style={{', max(0, pos-300), pos)
    div_end = data.find(b'</div>', pos) + 6
    old = data[div_start:div_end]
    
    new = (b'<div style={{width:48,height:48,borderRadius:12,background:"#fff",'
           b'display:"flex",alignItems:"center",justifyContent:"center",'
           b'flexShrink:0,boxShadow:"0 2px 10px rgba(0,0,0,0.15)",overflow:"hidden"}}>'
           b'<img src="/wipro-logo.jpg" alt="Wipro" style={{width:44,height:44,'
           b'borderRadius:10,objectFit:"contain"}} /></div>')
    
    data = data[:div_start] + new + data[div_end:]
    print(f"  Fixed at {pos}")

open(path, 'wb').write(data)
print("Done")
