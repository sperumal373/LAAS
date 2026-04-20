"""Patch generate_pptx.py to fix remaining two issues."""
with open(r'c:\caas-dashboard\generate_pptx.py', 'r', encoding='utf-8') as f:
    code = f.read()

# ------------------------------------------------
# Fix 1: Add logo to slide 19 (before slide 20 comment)
# ------------------------------------------------
old1 = '''add_text(slide, "Platform: Stable \u00b7 Uptime 99.98% \u00b7 12 active users \u00b7 248 VMs managed",
         Inches(0.6), Inches(1.82), Inches(12), Inches(0.35), size=9.5, color=C_SUB)

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# SLIDE 20 \u2014 THANK YOU / Q&A'''

new1 = '''add_text(slide, "Platform: Stable \u00b7 Uptime 99.98% \u00b7 12 active users \u00b7 248 VMs managed",
         Inches(0.6), Inches(1.82), Inches(12), Inches(0.35), size=9.5, color=C_SUB)
add_wipro_logo(slide)  # slide 19 logo

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# SLIDE 20 \u2014 THANK YOU / Q&A'''

if old1 in code:
    code = code.replace(old1, new1, 1)
    print("Fix 1 applied: slide 19 logo added")
else:
    print("Fix 1 FAILED: could not find slide 19/20 boundary text")
    # Find it approximately
    idx = code.find("Platform: Stable")
    if idx != -1:
        print(f"  Found 'Platform: Stable' at char {idx}")
        print(f"  Context: {repr(code[idx:idx+200])}")

# ------------------------------------------------
# Fix 2: slide 20 logo → cover=True
# ------------------------------------------------
old2 = 'add_wipro_logo(slide)\n\n# \u2500\u2500 SAVE'
new2 = 'add_wipro_logo(slide, cover=True)\n\n# \u2500\u2500 SAVE'

if old2 in code:
    code = code.replace(old2, new2, 1)
    print("Fix 2 applied: slide 20 logo → cover=True")
else:
    # Try just the last occurrence
    last_idx = code.rfind('add_wipro_logo(slide)')
    if last_idx != -1:
        code = code[:last_idx] + 'add_wipro_logo(slide, cover=True)' + code[last_idx+len('add_wipro_logo(slide)'):]
        print("Fix 2 applied via rfind: last add_wipro_logo → cover=True")
    else:
        print("Fix 2 FAILED")

with open(r'c:\caas-dashboard\generate_pptx.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("\nDone. Verifying logo calls:")
import subprocess
result = subprocess.run(['python', '-c', 
    'import re; code=open(r"c:\\caas\\generate_pptx.py").read(); '
    'print(code.count("add_wipro_logo(slide, cover=True)"))'], 
    capture_output=True, text=True)
# count occurrences
c1 = code.count('add_wipro_logo(slide, cover=True)')
c2 = code.count('add_wipro_logo(slide)')
print(f"  add_wipro_logo(slide, cover=True): {c1} calls")
print(f"  add_wipro_logo(slide): {c2} calls (should be 18 interior slides)")
print(f"  Total: {c1+c2} (should be 21 = 1 def + 20 calls)")
