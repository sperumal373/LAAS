data = open(r'C:\caas-dashboard\frontend\src\MigrationPage.jsx','rb').read()
lines = data.split(b'\r\n')
# Print exact bytes around the header area
for i in [761, 762, 763]:
    print(f"{i+1}: {repr(lines[i])}")
# Print exact bytes around data cells
for i in [783, 784, 785]:
    print(f"{i+1}: {repr(lines[i])}")
# Check the filter line
for i in [377]:
    print(f"{i+1}: {repr(lines[i][:300])}")
