data = open(r"C:\caas-dashboard\frontend\src\App.jsx","rb").read()

# The bad pattern: after the ZertoPage line there is "p={p}/></PageErrorBoundary>}"
# which belongs to the preceding migration line that was split
# Find and fix by looking for the malformed sequence

bad = b'{page === "dr" && <ZertoPage p={p} />}\r\n             p={p}/></PageErrorBoundary>}'
fix1 = b'{page === "dr" && <ZertoPage p={p} />}\r\n             {page==="migration"  &&<PageErrorBoundary page="Magic Migrate"><MigrationPage currentUser={currentUser} p={p}/></PageErrorBoundary>}'

if bad in data:
    data = data.replace(bad, fix1, 1)
    open(r"C:\caas-dashboard\frontend\src\App.jsx","wb").write(data)
    print("Fixed!")
else:
    # Show context around the ZertoPage render
    idx = data.find(b"ZertoPage p={p}")
    if idx >= 0:
        print("ZertoPage render context:")
        print(repr(data[idx-200:idx+300]))
    else:
        print("ZertoPage render not found")
