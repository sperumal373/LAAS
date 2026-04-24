data=open(r'C:\caas-dashboard\frontend\src\App.jsx','r',encoding='utf-8-sig').read()
idx=data.find('Solution Sphere')
# go back to find the icon
chunk=data[max(0,idx-800):idx]
# find last <div or <img or <svg before Solution Sphere
import re
for m in re.finditer(r'<(img|svg|div)[^>]{0,300}>', chunk):
    print(f"  {m.group()[:120]}")
print("---")
print("Near logo:", chunk[-200:])
