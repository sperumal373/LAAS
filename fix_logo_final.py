path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'r', encoding='utf-8-sig').read()

old_img = '<img src="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Wipro_Primary_Logo_Color_RGB.svg/1200px-Wipro_Primary_Logo_Color_RGB.svg.png" alt="Wipro" style={{width:28,height:28,borderRadius:4,objectFit:"contain"}} onError={(e)=>{e.target.style.display="none"}} />'

# Wipro "W" styled logo as inline SVG with brand colors
wipro_svg = '<svg viewBox="0 0 40 40" width="28" height="28"><defs><linearGradient id="wg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#3b1f8e"/><stop offset="50%" stopColor="#0072bc"/><stop offset="100%" stopColor="#00a4e4"/></linearGradient></defs><rect width="40" height="40" rx="8" fill="white"/><text x="20" y="30" textAnchor="middle" fontFamily="Arial Black,sans-serif" fontWeight="900" fontSize="28" fill="url(#wg)">W</text></svg>'

count = data.count(old_img)
print(f"Found {count} Wikipedia img tags")
data = data.replace(old_img, wipro_svg)

# Also check for clearbit version
old_cb = 'src="https://logo.clearbit.com/wipro.com"'
if old_cb in data:
    print("Also found clearbit version")

open(path, 'w', encoding='utf-8').write(data)
print("Done - replaced with inline Wipro SVG")
