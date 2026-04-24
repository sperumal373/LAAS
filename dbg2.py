with open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", "rb") as f:
    text = f.read().decode("utf-8")

lines = text.split("\n")
for i, line in enumerate(lines):
    s = line.rstrip("\r")
    if "AAP Instance</label>" in s:
        print("AAP label at line %d" % (i+1))
    if "ptSelAapInst" in s and "&&" in s:
        print("ptSelAapInst && at line %d: %s" % (i+1, s.strip()[:80]))
    if "DEBUG: ptAap" in s:
        print("DEBUG at line %d" % (i+1))

# Now just do a simple text replacement instead
# Find "AAP Instance</label>" and trace back/forward
idx = text.find("AAP Instance</label>")
print("AAP label at char index:", idx)

# Find the <div> before it 
div_idx = text.rfind("<div>", 0, idx)
print("div before it at:", div_idx)
print("Content between:", repr(text[div_idx:idx+25]))

# Find end - after the playbook section close
# Look for the pattern: </select>\n                    </div>\n                  )}
end_search = text.find("{ptSelAapInst &&", idx)
if end_search < 0:
    end_search = text.find("{ptSelAapInst&&", idx)
print("ptSelAapInst && at:", end_search)
if end_search > 0:
    # Find closing )}  after this
    close = text.find(")}", end_search + 100)
    print("First close at:", close, "context:", repr(text[close-20:close+5]))