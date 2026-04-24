path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# Current: 40x40 container with gradient bg, 32x32 img
old = b'<div style={{width:40,height:40,borderRadius:10,background:`linear-gradient(135deg,${p.accent},${p.cyan})`'
idx = data.find(old)
print(f"Found container at: {idx}")

# Find the full div including the img and closing </div>
end = data.find(b'</div>', idx)
old_block = data[idx:end+6]
print(f"Old block ({len(old_block)} bytes):", old_block[:100])

new_block = b'<div style={{width:48,height:48,borderRadius:12,background:"#fff",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,boxShadow:"0 2px 10px rgba(0,0,0,0.15)",padding:2}}><img src="/wipro-logo.jpg" alt="Wipro" style={{width:44,height:44,borderRadius:10,objectFit:"contain"}} /></div>'

data = data[:idx] + new_block + data[end+6:]
open(path, 'wb').write(data)
print("Done - bigger logo, white background")
