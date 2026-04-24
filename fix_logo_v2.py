path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'rb').read()

# Find all img tags with wipro in them
import re
pattern = rb'<img src="https://upload\.wikimedia[^"]*Wipro[^"]*"[^/]*/>'
matches = list(re.finditer(pattern, data))
print(f"Found {len(matches)} matches")

wipro_svg = b'<svg viewBox="0 0 40 40" width="28" height="28"><defs><linearGradient id="wg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stopColor="#3b1f8e"/><stop offset="50%" stopColor="#0072bc"/><stop offset="100%" stopColor="#00a4e4"/></linearGradient></defs><rect width="40" height="40" rx="8" fill="white"/><text x="20" y="30" textAnchor="middle" fontFamily="Arial Black,sans-serif" fontWeight="900" fontSize="28" fill="url(#wg)">W</text></svg>'

for m in reversed(matches):
    print(f"  Replacing at {m.start()}: {m.group()[:80]}...")
    data = data[:m.start()] + wipro_svg + data[m.end():]

# Also check for clearbit
pattern2 = rb'<img src="https://logo\.clearbit\.com/wipro\.com"[^/]*/>'
matches2 = list(re.finditer(pattern2, data))
print(f"Found {len(matches2)} clearbit matches")
for m in reversed(matches2):
    data = data[:m.start()] + wipro_svg + data[m.end():]

open(path, 'wb').write(data)
print("Done")
