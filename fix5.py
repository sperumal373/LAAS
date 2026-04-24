path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()

# 1. Add ref after selVMs state
old1 = b'  const [selVMs, setSelVMs] = useState({});'
new1 = b'  const [selVMs, setSelVMs] = useState({});\r\n  const skipVCEffectRef = useRef(false);'

# 2. Guard the useEffect
old2 = b'  // Load VMs when vCenter selected\r\n  useEffect(() => {\r\n    if (!selVC) { setAllVMs([]); setHosts([]); return; }'
new2 = b'  // Load VMs when vCenter selected\r\n  useEffect(() => {\r\n    if (skipVCEffectRef.current) { skipVCEffectRef.current = false; return; }\r\n    if (!selVC) { setAllVMs([]); setHosts([]); return; }'

# 3. Set skip flag before setSelVC in handleMigrateFromGroup
old3 = b'      setSelVC(firstVC);\r\n      setAllVMs(allVms);'
new3 = b'      skipVCEffectRef.current = true;\r\n      setSelVC(firstVC);\r\n      setAllVMs(allVms);'

for i, (old, new) in enumerate([(old1,new1),(old2,new2),(old3,new3)], 1):
    c = raw.count(old)
    if c != 1:
        print(f'ERROR: replacement {i} found {c} matches')
        import sys; sys.exit(1)
    raw = raw.replace(old, new, 1)
    print(f'Replacement {i}: OK')

open(path, 'wb').write(raw)
print('All done!')
