content = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8', errors='replace').read()

# Fix 1: Replace React.* with named hook imports inside VolumeTopologyModal
content = content.replace("React.useState(null);", "useState(null);")
content = content.replace("React.useState(true);", "useState(true);")
content = content.replace("React.useState('');",   "useState('');")
content = content.replace("React.useEffect(",      "useEffect(")

# Fix 2: Replace all "🔗 Topo" button text with just the topology icon (circuit icon)
# Pure FlashArray - orange
content = content.replace(
    '>&#128279; Topo</button></td>\n                        </tr>',
    '>&#128279;</button></td>\n                        </tr>'
)
# HPE Alletra - green  
content = content.replace(
    '>&#128279; Topo</button></td>\n                          </tr>',
    '>&#128279;</button></td>\n                          </tr>'
)
# Dell PowerFlex - blue
content = content.replace(
    '>&#128279; Topo</button></td>\n                          <td',
    '>&#128279;</button></td>\n                          <td'
)

# Fix all remaining "🔗 Topo" labels in topology buttons (NetApp, Dell PowerStore, Nimble etc.)
import re

# Replace button label text: ">🔗 Topo<" -> ">🔗<"
content = content.replace('\U0001f517 Topo</button>', '\U0001f517</button>')

# Also handle the HTML entity version
content = content.replace('&#128279; Topo</button>', '&#128279;</button>')

open(r'c:\caas-dashboard\frontend\src\App.jsx', 'w', encoding='utf-8').write(content)
print("Done")

# Verify no React. remains in modal
lines = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8', errors='replace').readlines()
modal_start = next(i for i,l in enumerate(lines) if 'function VolumeTopologyModal' in l)
for i in range(modal_start, modal_start+20):
    if 'React.' in lines[i]:
        print(f"Still has React. at line {i+1}: {lines[i].rstrip()}")
print("React. check done")

# Verify Topo text is gone from buttons
found = [i+1 for i,l in enumerate(lines) if 'Topo</button>' in l]
print(f"'Topo</button>' remaining at lines: {found}")
