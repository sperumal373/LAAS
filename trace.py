import re
js = open(r"C:\caas-dashboard\frontend\dist\assets\index-6b4KguGp.js", encoding="utf-8").read()

# Find the debug text rendering to get the variable name
m = re.search(r'"DEBUG: ptAapInstances\.length = ",(\w+)\.length', js)
if m:
    var = m.group(1)
    print(f"Variable used in debug: {var}")
    
    # Find where this variable is defined (useState)
    # Look for: var = r.useState([])  or [var, setter] = r.useState
    # In minified React, useState is often like Yt(someValue)
    # Search for the setter pattern near the variable
    pattern = rf'\[{var},(\w+)\]=\w+\.useState\(([^)]*)\)'
    m2 = re.search(pattern, js)
    if m2:
        print(f"useState found: [{var}, {m2.group(1)}] = useState({m2.group(2)})")
        setter = m2.group(1)
        
        # Find ALL places the setter is called
        setter_calls = [(m3.start(), js[max(0,m3.start()-30):m3.end()+30]) for m3 in re.finditer(rf'{setter}\(', js)]
        print(f"\nSetter {setter}() called {len(setter_calls)} times:")
        for pos, ctx in setter_calls:
            print(f"  pos {pos}: ...{ctx}...")
    else:
        print("useState pattern not found, searching more broadly...")
        # Search for the variable assignment
        for m3 in re.finditer(rf'(?<!\w){var}(?!\w)', js):
            ctx = js[max(0,m3.start()-40):m3.end()+40]
            if 'useState' in ctx or '=' in ctx[:20]:
                print(f"  pos {m3.start()}: {ctx}")
else:
    print("DEBUG text not found!")
    # Search for ptAapInstances
    idx = js.find("ptAapInstances")
    if idx >= 0:
        print(f"Found ptAapInstances at {idx}: {js[idx-50:idx+100]}")