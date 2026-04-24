path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
raw = open(path, "rb").read()
old = b'  const [vmSearch, setVmSearch] = useState("");\r\n  const [selVMs'
new = b'  const [vmSearch, setVmSearch] = useState("");\r\n  const [filterPower, setFilterPower] = useState("");\r\n  const [filterOS, setFilterOS] = useState("");\r\n  const [filterTag, setFilterTag] = useState("");\r\n  const [filterApp, setFilterApp] = useState("");\r\n  const [selVMs'
c = raw.count(old)
print(f"Found {c}")
if c == 1:
    raw = raw.replace(old, new, 1)
    open(path, "wb").write(raw)
    print("Done - filter states added")
else:
    print("ERROR")