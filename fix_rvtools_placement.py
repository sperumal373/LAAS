"""
fix_rvtools_placement.py
Removes the misplaced RVTools render block (now inside datastores table)
and re-inserts it at the correct level (sibling to other vmTab blocks).
"""
s = open('C:/caas-dashboard/frontend/src/App.jsx', encoding='utf-8').read()
lines = s.split('\n')
print(f"File: {len(lines)} lines")

# ── Find the RVTools block start: '{/* RVTools Reports tab */}' ──────────────
rvt_start = next((i for i,l in enumerate(lines) if '{/* RVTools Reports tab */' in l), -1)
assert rvt_start >= 0, "rvtools comment not found"
print(f"RVTools block starts at line {rvt_start+1}")

# ── Find the RVTools block end: the closing ')}' of {vmTab==="rvtools"&&(...)} 
# We go forward looking for the line that is '      )}' appearing after
# the vmTab rvtools conditional closes.
# Strategy: find the matching ')' for the '(' in '{vmTab==="rvtools"&&('
rvt_cond = next((i for i in range(rvt_start, rvt_start+20) if 'vmTab==="rvtools"&&(' in lines[i]), -1)
assert rvt_cond >= 0, "rvtools conditional not found"

depth = 0
rvt_end = -1
for i in range(rvt_cond, rvt_cond + 800):
    for ch in lines[i]:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                rvt_end = i
                break
    if rvt_end >= 0:
        break

# The actual end line is the line with ')}\n' which follows rvt_end
# Find the line that has '      )}' and '      )}' pattern right after rvt_end
# Look for the pattern from the original - it ends with '      )}'
# The closing )}  of the conditional block
closing_line = next((i for i in range(rvt_end, rvt_end + 3)
                     if lines[i].strip() in (')}', ')}')), rvt_end)

print(f"RVTools block ends at line {closing_line+1}: {repr(lines[closing_line])}")

# The block to extract: from rvt_start-1 (blank line before comment) to closing_line (inclusive)
# Also include the blank line BEFORE the comment (if it's empty)
extract_start = rvt_start - 1 if (rvt_start > 0 and lines[rvt_start-1].strip() == '') else rvt_start
extract_end = closing_line

print(f"Extracting lines {extract_start+1} to {extract_end+1}")

# ── Extract the block ────────────────────────────────────────────────────────
block_lines = lines[extract_start:extract_end+1]
print(f"  Extracted {len(block_lines)} lines")

# ── Remove the block from current position ───────────────────────────────────
del lines[extract_start:extract_end+1]
print(f"File after removal: {len(lines)} lines")

# ── Find the correct insertion point────────────────────────────────────────
# We want to insert JUST BEFORE '    </div>' which closes VMwarePage's return
# That is: find the closing structure pattern:
#   ...        )} <- closes last tab
#   \n    </div>  <- closes return div   <- INSERT BEFORE THIS
#   \n  );
#   \n}          <- closes VMwarePage function
# Find where VMsPage function starts
vmspage_idx = next((i for i,l in enumerate(lines) if 'function VMsPage(' in l and 'vms,' in l), -1)
assert vmspage_idx >= 0, "VMsPage not found"
print(f"VMsPage at line {vmspage_idx+1}")

# The closing structure should be at vmspage_idx - 5 to vmspage_idx - 1
# Look backwards for '    </div>' (4 spaces + </div>)
insert_before_idx = -1
for i in range(vmspage_idx - 1, vmspage_idx - 15, -1):
    if lines[i].rstrip('\r') == '    </div>':
        insert_before_idx = i
        break

assert insert_before_idx >= 0, "closing </div> of VMwarePage not found"
print(f"Inserting before line {insert_before_idx+1}: {repr(lines[insert_before_idx])}")

# ── Re-insert the block at correct position ──────────────────────────────────
# Add a blank separator line before the block if needed
separator = ['\r'] if lines[insert_before_idx-1].strip() != '' else []

for i, bl in enumerate(separator + block_lines):
    lines.insert(insert_before_idx + i, bl)
    
print(f"File after re-insert: {len(lines)} lines")

# ── Verify ───────────────────────────────────────────────────────────────────
new_rvt = next((i for i,l in enumerate(lines) if '{/* RVTools Reports tab */' in l), -1)
new_vmspage = next((i for i,l in enumerate(lines) if 'function VMsPage(' in l and 'vms,' in l), -1)
print(f"\nVerification:")
print(f"  RVTools block now at line {new_rvt+1}")
print(f"  VMsPage now at line {new_vmspage+1}")
print(f"  Lines before VMsPage: {lines[new_vmspage-5+1]!r}")
print(f"  Line just before VMsPage: {lines[new_vmspage-1]!r}")

# Show context around new RVTools block position
print(f"\n=== 5 lines before new RVTools block ===")
for i in range(new_rvt-5, new_rvt):
    print(f"  {i+1}: {repr(lines[i])}")

# ── Write ─────────────────────────────────────────────────────────────────────
out = '\n'.join(lines)
with open(r'C:/caas-dashboard/frontend/src/App.jsx', 'w', encoding='utf-8') as f:
    f.write(out)
print(f"\n✅ App.jsx fixed and saved ({len(lines)} lines)")
