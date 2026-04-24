with open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", "rb") as f:
    text = f.read().decode("utf-8")

# Normalize line endings for searching
lines = text.split("\n")
for i, line in enumerate(lines):
    s = line.rstrip("\r")
    if "AAP Instance</label>" in s:
        print(f"Found AAP Instance at line {i+1}: [{s.strip()[:80]}]")
    if "ptSelAapInst" in s and "&&" in s:
        print(f"Found ptSelAapInst && at line {i+1}: [{s.strip()[:80]}]")
    if ")}" in s and i > 1300 and i < 1400:
        print(f"Line {i+1} has )}: [{s.strip()[:80]}]")