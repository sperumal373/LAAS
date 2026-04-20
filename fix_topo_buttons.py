import re

path = r'c:\caas-dashboard\frontend\src\App.jsx'
lines = open(path, encoding='utf-8', errors='replace').readlines()
print(f"Loaded {len(lines)} lines")

# ── Fix 1: Remove duplicate FA vol row ──
# Find the two consecutive TD data_reduction lines and remove the 2nd (stale) one
for i in range(13920, 13950):
    if 'data_reduction' in lines[i] and 'data_reduction' in lines[i+1]:
        print(f"Removing duplicate at line {i+2}: {lines[i+1][:60].rstrip()}")
        del lines[i+1]
        break

# ── Recalculate indices after deletion ──
nim_idx = pfx_idx = -1
for i, l in enumerate(lines):
    if 'tab==="nim_vols"' in l and nim_idx == -1:
        nim_idx = i
    if 'tab==="pfx_vols"' in l and pfx_idx == -1:
        pfx_idx = i
print(f"nim_vols at 1-based line: {nim_idx+1}")
print(f"pfx_vols at 1-based line: {pfx_idx+1}")

# ── Fix 2: Nimble volumes row – add topology button ──
# Find the </tr> that closes the nimVolList row
nim_row_close = -1
for i in range(nim_idx, nim_idx+25):
    if '</tr>)}</tbody>' in lines[i]:
        nim_row_close = i
        break
print(f"Nimble row close at 1-based: {nim_row_close+1}")

if nim_row_close != -1:
    # The closing looks like:  <td>...</td>\n  </tr>)}</tbody>
    # We need to insert the topology button cell before </tr>)}</tbody>
    btn = ('                      <td style={{padding:"4px 6px",textAlign:"center"}}>'
           '<button title={"Topology for "+v.name} onClick={()=>setTopoModal(v)} '
           'style={{padding:"3px 9px",borderRadius:6,border:"1px solid #01A98240",'
           'background:"#01A98210",color:"#01A982",fontSize:10,fontWeight:700,'
           'cursor:"pointer"}}>&#128279; Topo</button></td>\n')
    lines[nim_row_close] = btn + '                    </tr>)}</tbody>\n'
    print("Nimble topology button added")
else:
    # Find the last </tr> in the nim section
    for i in range(nim_idx+5, nim_idx+25):
        if '</tr>' in lines[i] and 'style' not in lines[i]:
            nim_row_close = i
            print(f"Alt Nimble close at {i+1}: {lines[i][:60].rstrip()}")
            break

# ── Fix 3: Nimble thead – add empty column header ──
nim_thead = -1
for i in range(nim_idx, nim_idx+8):
    if 'thead' in lines[i] and 'Connections' in lines[i]:
        nim_thead = i
        break
if nim_thead != -1:
    lines[nim_thead] = lines[nim_thead].rstrip().replace(
        '"Connections"',
        '"Connections",""'
    ) + '\n'
    print(f"Nimble thead updated at {nim_thead+1}")

# ── Fix 4: PowerFlex volumes row – add topology button ──
pfx_row_close = -1
for i in range(pfx_idx, pfx_idx+20):
    if lines[i].strip() == '</tr>' or ('vtree_id' in lines[i] and '/>' in lines[i]):
        pfx_row_close = i
        print(f"PFlex row area at 1-based: {i+1}: {lines[i][:70].rstrip()}")

# The vtree_id line ends with /> so we append button there
vtree_line = -1
for i in range(pfx_idx, pfx_idx+20):
    if 'vtree_id' in lines[i] and '/>' in lines[i]:
        vtree_line = i
        break
print(f"vtree_id line at 1-based: {vtree_line+1}")

if vtree_line != -1:
    orig = lines[vtree_line].rstrip()
    if '</tr>' in lines[vtree_line+1]:
        # Insert button before </tr>
        btn = ('                          <td style={{padding:"4px 6px",textAlign:"center"}}>'
               '<button title={"Topology for "+v.name} onClick={()=>setTopoModal(v)} '
               'style={{padding:"3px 9px",borderRadius:6,border:"1px solid #0076CE40",'
               'background:"#0076CE10",color:"#0076CE",fontSize:10,fontWeight:700,'
               'cursor:"pointer"}}>&#128279; Topo</button></td>\n')
        lines.insert(vtree_line+1, btn)
        print("PowerFlex topology button added")

# ── Fix 5: PowerFlex thead – add empty column ──
pfx_thead = -1
for i in range(pfx_idx, pfx_idx+8):
    if 'thead' in lines[i] and 'VTree ID' in lines[i]:
        pfx_thead = i
        break
if pfx_thead != -1:
    lines[pfx_thead] = lines[pfx_thead].rstrip().replace(
        '"VTree ID"',
        '"VTree ID",""'
    ) + '\n'
    print(f"PowerFlex thead updated at {pfx_thead+1}")

print(f"\nFinal line count: {len(lines)}")
open(path, 'w', encoding='utf-8').writelines(lines)
print("Saved successfully")
