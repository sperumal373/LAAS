data=open(r'C:\caas-dashboard\frontend\src\App.jsx','r',encoding='utf-8-sig').read()
idx=data.find('className="sidebar"')
print('sidebar at:', idx)
if idx > 0:
    print(data[idx:idx+1500])
else:
    idx=data.find("sidebar")
    while idx>0:
        ctx=data[idx:idx+30]
        if 'class' in data[max(0,idx-20):idx].lower():
            print(f"sidebar class at {idx}: {data[max(0,idx-30):idx+40]}")
        idx=data.find("sidebar", idx+1)
        if idx > 300000: break
