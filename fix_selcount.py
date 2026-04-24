path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()

old = b'  const selectedVMList = allVMs.filter(v => selVMs[v.moid || v.name]);\r\n  const totalDisk = selectedVMList.reduce'
new = b'  const selectedVMList = allVMs.filter(v => selVMs[v.moid || v.name]);\r\n  const selCount = selectedVMList.length;\r\n  const totalCPU = selectedVMList.reduce((s, v) => s + (v.cpu || 0), 0);\r\n  const totalRAM = selectedVMList.reduce((s, v) => s + (v.ram_gb || 0), 0);\r\n  const totalDisk = selectedVMList.reduce'

c = raw.count(old)
print(f'Found {c}')
if c == 1:
    raw = raw.replace(old, new, 1)
    open(path, 'wb').write(raw)
    print('Fixed - added selCount, totalCPU, totalRAM')
