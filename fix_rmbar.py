path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
raw = open(path, "rb").read()
lines = raw.split(b"\r\n")

# Remove lines 617-634 (indices 616-633) - the separate filter bar
old_block = b"\r\n".join(lines[616:634])
c = raw.count(old_block)
print(f"Found {c} match(es) for filter bar block")
if c == 1:
    raw = raw.replace(old_block + b"\r\n", b"", 1)
    open(path, "wb").write(raw)
    print("Removed separate filter bar")
else:
    print("ERROR")