data = open(r"C:\caas-dashboard\frontend\src\App.jsx","rb").read()

# The actual bad pattern (with \n not \r\n in the middle)
bad = b'currentUser}\n            {page === "dr" && <ZertoPage p={p} />} p={p}/></PageErrorBoundary>}'
good = b'currentUser} p={p}/></PageErrorBoundary>}\r\n            {page === "dr" && <ZertoPage p={p} />}'

if bad in data:
    data = data.replace(bad, good, 1)
    open(r"C:\caas-dashboard\frontend\src\App.jsx","wb").write(data)
    print("Fixed bad render injection!")
else:
    print("Pattern not found, trying alternative...")
    # More permissive search
    idx = data.find(b"ZertoPage p={p}")
    ctx = data[max(0,idx-300):idx+200]
    print(repr(ctx))
