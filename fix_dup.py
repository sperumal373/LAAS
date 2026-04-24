path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()

# Remove the duplicate block (lines 76-79)
dup = b'\r\n  const [filterPower, setFilterPower] = useState("");\r\n  const [filterOS, setFilterOS] = useState("");\r\n  const [filterTag, setFilterTag] = useState("");\r\n  const [filterApp, setFilterApp] = useState("");\r\n  const [selVMs'

good = b'\r\n  const [selVMs'

c = raw.count(dup)
print(f'Found {c} dup block(s)')
if c == 1:
    raw = raw.replace(dup, good, 1)
    open(path, 'wb').write(raw)
    print('Removed duplicate filter state declarations')
