data = open(r'C:\caas-dashboard\frontend\src\MigrationPage.jsx','rb').read()
lines = data.split(b'\r\n')
# Find where vm keys are first accessed
for i in range(425, 440):
    print(f"{i+1}: {lines[i].decode('utf-8','replace')[:170]}")
