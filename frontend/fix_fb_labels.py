fpath = r"C:\caas-dashboard\frontend\src\App.jsx"
with open(fpath, "r", encoding="utf-8") as f:
    src = f.read()

replacements = [
    # Header button and inline empty-state button
    ("＋ Add Pure Storage", "＋ Add FlashBlade"),
    # Any remaining "Add Pure Storage" link text
    (">Add Pure Storage<", ">Add FlashBlade<"),
]

for old, new in replacements:
    count = src.count(old)
    src = src.replace(old, new)
    print(f"  '{old}' → replaced {count}x")

with open(fpath, "w", encoding="utf-8") as f:
    f.write(src)
print("Done.")
