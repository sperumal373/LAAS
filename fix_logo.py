path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'r', encoding='utf-8').read()

# The eye SVG in sidebar
old_eye = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{filter:"drop-shadow(0 0 4px rgba(255,255,255,0.5))"}}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3.5"/><circle cx="12" cy="12" r="1" fill="white"/></svg>'

# Also check the first eye (header)
old_eye2 = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{filter:"drop-shadow(0 0 3px rgba(255,255,255,0.6))"}}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3.5"/><circle cx="12" cy="12" r="1" fill="white"/></svg>'

wipro = '<img src="https://logo.clearbit.com/wipro.com" alt="Wipro" style={{width:24,height:24,borderRadius:4,objectFit:"contain"}} />'

c1 = data.count(old_eye)
c2 = data.count(old_eye2)
print(f"Eye 24px: {c1}, Eye 22px: {c2}")

data = data.replace(old_eye, wipro)
data = data.replace(old_eye2, wipro)

open(path, 'w', encoding='utf-8').write(data)
print("Replaced all eye SVGs with Wipro logo")
