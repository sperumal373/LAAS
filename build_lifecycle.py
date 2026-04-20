import os, json
print("Starting migration lifecycle build...")

# 1. BACKEND
be = open(r"C:\caas-dashboard\backend\main.py", "r", encoding="utf-8").read()
marker = "#  Magic Migrate  Cross-Hypervisor VM Migration Plans"
idx = be.find(marker)
if idx == -1:
    print("ERROR: marker not found")
    exit(1)
# Go to start of the comment block (line before)
nl = be.rfind('\n', 0, idx)
nl2 = be.rfind('\n', 0, nl)
cut = nl2 + 1
before = be[:cut]
print(f"Cutting backend at byte {cut}, keeping {len(before)} bytes")
