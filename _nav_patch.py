data = open(r"C:\caas-dashboard\frontend\src\App.jsx","rb").read()
if b'"dr"' in data:
    print("DR already in nav array")
else:
    anchor = b'label:"Magic Migrate"'
    idx = data.find(anchor)
    if idx < 0:
        print("anchor not found - searching alternatives")
        anchor = b"Magic Migrate"
        idx = data.find(anchor)
    if idx >= 0:
        end = data.find(b"},", idx) + 2
        dr = b'\r\n    {id:"dr", label:"Disaster Recovery", icon:"\xf0\x9f\x94\x84", roles:["admin","operator","viewer"]},'
        data = data[:end] + dr + data[end:]
        open(r"C:\caas-dashboard\frontend\src\App.jsx","wb").write(data)
        print("DR nav added after byte", end)
    else:
        print("Could not find anchor")
