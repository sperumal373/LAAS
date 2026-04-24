data = open(r'C:\caas-dashboard\frontend\src\MigrationPage.jsx','rb').read()
lines = data.split(b'\r\n')
for i in range(425, 445):
    print(f"{i+1}: {lines[i].decode('utf-8','replace')[:170]}")
