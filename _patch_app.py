import sys, re

p = r"C:\caas-dashboard\frontend\src\App.jsx"
raw = open(p,"rb").read()
bom = b"\xef\xbb\xbf" if raw[:3]==b"\xef\xbb\xbf" else b""
data = raw[len(bom):]

changed = False

# 1. Add import
if b"ZertoPage" not in data:
    # Find last import line
    last = data.rfind(b"\nimport ")
    if last >= 0:
        end = data.find(b"\n", last+1)+1
        imp = b'\nimport ZertoPage from "./ZertoPage";\n'
        data = data[:end] + imp + data[end:]
        changed = True
        print("Added ZertoPage import")

# 2. Add sidebar nav
if b'"dr"' not in data and b"'dr'" not in data:
    # Find Magic Migrate nav item - look for the text in a nav item
    targets = [b"Magic Migrate", b"MagicMigrate", b"magic-migrate"]
    for t in targets:
        idx = data.find(t)
        if idx < 0: continue
        # Find the closing </div> tag after this position
        close = data.find(b"</div>", idx)
        if close < 0: continue
        nav = b'\n              <div className={`nav-item${page === "dr" ? " active" : ""}`} onClick={() => setPage("dr")}><span className="nav-icon">\xf0\x9f\x94\x84</span><span className="nav-label">Disaster Recovery</span></div>'
        data = data[:close+6] + nav + data[close+6:]
        changed = True
        print("Added DR nav item after", t.decode())
        break

# 3. Add page render
if b'page === "dr"' not in data and b'page==="dr"' not in data:
    # Look for MagicMigratePage or similar render block
    targets = [b"MagicMigratePage", b"<MigrationPage", b"CompliSpherePage", b"<CompliSphere"]
    for t in targets:
        idx = data.find(t)
        if idx < 0: continue
        # Find the closing brace/tag of this render line
        close = data.find(b"}", idx)
        if close < 0: continue
        render = b'\n            {page === "dr" && <ZertoPage p={p} />}'
        data = data[:close+1] + render + data[close+1:]
        changed = True
        print("Added ZertoPage render after", t.decode())
        break

if changed:
    open(p,"wb").write(bom+data)
    print("App.jsx saved,", len(data), "bytes")
else:
    print("No changes needed")
