data=open(r'C:\caas-dashboard\frontend\src\App.jsx','rb').read()
idx=data.find(b'Portal Header')
if idx>0:
    print(data[idx:idx+800])
