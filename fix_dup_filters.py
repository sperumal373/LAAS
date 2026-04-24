path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
data = open(path, 'rb').read()

# Remove the second set of filter declarations
block = (
    b'\r\n  const [fPower, setFPower] = useState("");\r\n'
    b'  const [fOS, setFOS] = useState("");\r\n'
    b'  const [fTag, setFTag] = useState("");\r\n'
    b'  const [fApp, setFApp] = useState("");\r\n'
    b'  const hasFilters = fPower || fOS || fTag || fApp;'
)
# Find first occurrence, then remove second
first = data.find(block)
second = data.find(block, first + len(block))
if second > 0:
    data = data[:second] + data[second + len(block):]
    open(path, 'wb').write(data)
    print("Removed duplicate filter declarations")
    print("fPower count now:", data.count(b'const [fPower'))
else:
    print("No duplicate found")
