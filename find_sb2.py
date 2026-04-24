data=open(r'C:\caas-dashboard\frontend\src\App.jsx','r',encoding='utf-8-sig').read()
# Find ALL Solution Sphere occurrences
idx=0
i=0
while True:
    idx=data.find('Solution Sphere',idx)
    if idx<0: break
    i+=1
    chunk=data[max(0,idx-500):idx+50]
    print(f"=== Occurrence {i} at char {idx} ===")
    # Find nearest img/svg
    if 'sidebar' in data[max(0,idx-2000):idx]:
        print("  ** SIDEBAR context **")
    if 'clearbit' in chunk or 'wipro' in chunk.lower() or 'upload.wiki' in chunk:
        print("  Has logo img")
    if '<svg' in chunk[max(0,len(chunk)-400):]:
        print("  Has SVG")
    # Show the icon div
    print(chunk[-300:])
    print()
    idx+=1
