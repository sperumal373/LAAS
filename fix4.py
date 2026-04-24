path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()

# 1. Add useRef import
old1 = b'import { useState, useEffect, useCallback, Fragment } from "react";'
new1 = b'import { useState, useEffect, useCallback, useRef, Fragment } from "react";'

# 2. Add ref after selVMs state (line 72)
old2 = b'  const [selVMs, setSelVMs] = useState({});'
new2 = b'  const [selVMs, setSelVMs] = useState({});\r\n  const skipVCEffectRef = useRef(false);'

# 3. Guard the useEffect to skip when flag is set
old3 = b'  // Load VMs when vCenter selected\r\n  useEffect(() => {\r\n    if (!selVC) { setAllVMs([]); setHosts([]); return; }\r\n    setLoadingVMs(true);\r\n    Promise.all([fetchVMs(), fetchHosts()])'
new3 = b'  // Load VMs when vCenter selected\r\n  useEffect(() => {\r\n    if (skipVCEffectRef.current) { skipVCEffectRef.current = false; return; }\r\n    if (!selVC) { setAllVMs([]); setHosts([]); return; }\r\n    setLoadingVMs(true);\r\n    Promise.all([fetchVMs(), fetchHosts()])'

# 4. Set the skip flag in handleMigrateFromGroup before setSelVC
old4 = b'      setSelVC(firstVC);\r\n      setAllVMs(allVms);'
new4 = b'      skipVCEffectRef.current = true;\r\n      setSelVC(firstVC);\r\n      setAllVMs(allVms);'

replacements = [(old1, new1), (old2, new2), (old3, new3), (old4, new4)]

for i, (old, new) in enumerate(replacements):
    count = raw.count(old)
    if count != 1:
        print(f'ERROR: replacement {i+1} found {count} matches')
        import sys; sys.exit(1)
    raw = raw.replace(old, new, 1)
    print(f'Replacement {i+1}: OK')

open(path, 'wb').write(raw)
print('All done!')
