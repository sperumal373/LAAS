src = open(r'C:\Users\Administrator\Desktop\sdx_lab_connectivity_pro.html', encoding='utf-8').read()

header = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SDx Lab Connectivity</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Exo+2:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;padding:0;background:#080c14;overflow-y:auto;overflow-x:hidden}
  #close-bar{position:fixed;top:0;left:0;right:0;z-index:9999;display:flex;align-items:center;
    justify-content:space-between;padding:8px 18px;background:rgba(4,8,20,.95);
    border-bottom:1px solid #1a3a5a;backdrop-filter:blur(6px)}
  #close-bar .cb-title{font-family:'Exo 2',sans-serif;font-size:13px;font-weight:700;
    letter-spacing:2px;text-transform:uppercase;color:#5cc8f8}
  #close-bar button{background:linear-gradient(135deg,#0055aa,#0088cc);border:1px solid #00d4ff;
    border-radius:6px;padding:5px 16px;color:#fff;font-size:12px;font-weight:700;cursor:pointer;
    letter-spacing:1px;box-shadow:0 0 12px rgba(0,180,255,.3);font-family:'Exo 2',sans-serif}
  #close-bar button:hover{background:linear-gradient(135deg,#0077cc,#00aaee)}
  .diagram-wrap{padding-top:52px !important}
</style>
</head>
<body>
<div id="close-bar">
  <span class="cb-title">&#127760; SDx Lab Network Connectivity</span>
  <button onclick="window.parent&&window.parent.postMessage('close-topo','*')">&#x2715; CLOSE</button>
</div>
"""

footer = "\n</body>\n</html>"

output = header + src + footer
open(r'C:\caas-dashboard\frontend\public\sdx-topo.html', 'w', encoding='utf-8').write(output)
print('Written', len(output), 'bytes')


# Collapse the 3 multi-line backtick GLSL strings into single double-quoted lines
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    if 'const VS=' in line and '`' in line and 'attribute vec3 aPos' in line:
        # Consume until closing backtick+semicolon, merge into one double-quoted line
        buf = line.rstrip('\n')
        while not buf.endswith('`;'):
            i += 1
            buf = buf + lines[i].rstrip('\n')
        # strip surrounding backticks and semicolon, rewrap in double quotes
        inner = buf.replace('const VS=`', '', 1)
        inner = inner[:-2]  # remove trailing `;
        inner = inner.replace('\n', '').replace('  ', ' ')
        new_lines.append('const VS="' + inner + '";\n')
    elif 'const FS=' in line and '`' in line and 'precision mediump' in line:
        buf = line.rstrip('\n')
        while not buf.endswith('`;'):
            i += 1
            buf = buf + lines[i].rstrip('\n')
        inner = buf.replace('const FS=`', '', 1)[:-2].replace('\n', '').replace('  ', ' ')
        new_lines.append('const FS="' + inner + '";\n')
    elif 'const EFS=' in line and '`' in line:
        buf = line.rstrip('\n')
        while not buf.endswith('`;'):
            i += 1
            buf = buf + lines[i].rstrip('\n')
        inner = buf.replace('const EFS=`', '', 1)[:-2]
        new_lines.append('const EFS="' + inner + '";\n')
    else:
        new_lines.append(line)
    i += 1

with open(r'C:\caas-dashboard\frontend\src\App.jsx', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Done. Verifying...")
with open(r'C:\caas-dashboard\frontend\src\App.jsx', 'r', encoding='utf-8') as f:
    lines2 = f.readlines()
for j, l in enumerate(lines2):
    if 'const VS=' in l or 'const FS=' in l or 'const EFS=' in l:
        if 'WEBGL' not in l:
            print(f"Line {j+1}: {l.rstrip()}")

