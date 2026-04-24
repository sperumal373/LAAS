path = r'C:\caas-dashboard\frontend\src\App.jsx'
data = open(path, 'r', encoding='utf-8-sig').read()

old = 'src="https://logo.clearbit.com/wipro.com" alt="Wipro" style={{width:24,height:24,borderRadius:4,objectFit:"contain"}}'

# Use Wipro's official logo from their website
new = 'src="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Wipro_Primary_Logo_Color_RGB.svg/1200px-Wipro_Primary_Logo_Color_RGB.svg.png" alt="Wipro" style={{width:28,height:28,borderRadius:4,objectFit:"contain"}} onError={(e)=>{e.target.style.display="none"}}'

count = data.count(old)
print(f"Found {count} occurrences")
data = data.replace(old, new)
open(path, 'w', encoding='utf-8').write(data)
print("Replaced with Wikipedia Wipro logo URL")
