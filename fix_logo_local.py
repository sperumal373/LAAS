path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

old_svg = b'<svg viewBox="0 0 40 40" width="28" height="28"><defs><linearGradient id="wg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#3b1f8e"/><stop offset="50%" stopColor="#0072bc"/><stop offset="100%" stopColor="#00a4e4"/></linearGradient></defs><rect width="40" height="40" rx="8" fill="white"/><text x="20" y="30" textAnchor="middle" fontFamily="Arial Black,sans-serif" fontWeight="900" fontSize="28" fill="url(#wg)">W</text></svg>'

wipro_img = b'<img src="/wipro-logo.jpg" alt="Wipro" style={{width:32,height:32,borderRadius:6,objectFit:"contain"}} />'

count = data.count(old_svg)
print(f"Found {count} inline W SVGs")
data = data.replace(old_svg, wipro_img)

open(path, 'wb').write(data)
print(f"Replaced {count} with local /wipro-logo.jpg")
