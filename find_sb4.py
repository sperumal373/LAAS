data=open(r'C:\caas-dashboard\frontend\src\App.jsx','rb').read()
pat = b'className="sidebar">'
idx=data.find(pat)
print("sidebar at:", idx)
if idx>0:
    print(data[idx:idx+1200].decode('utf-8','replace'))
