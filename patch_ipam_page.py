"""patch_ipam_page.py – Replace inline IPAMPage with import from IPAMPage.jsx"""
import re

APP = r"c:\caas-dashboard\frontend\src\App.jsx"
content = open(APP, encoding="utf-8").read()

# 1. Add lazy import after AnsiblePage lazy import
OLD_LAZY = "const AnsiblePage = lazy(() => import('./AnsiblePage'));"
NEW_LAZY = (
    "const AnsiblePage = lazy(() => import('./AnsiblePage'));\n"
    "// IPAM v2 — Self-hosted PostgreSQL IPAM module\n"
    "const IPAMPage = lazy(() => import('./IPAMPage'));"
)

if "import('./IPAMPage')" in content:
    print("IPAMPage lazy import already present.")
else:
    if OLD_LAZY not in content:
        print(f"ERROR: Could not find anchor: {OLD_LAZY!r}")
        exit(1)
    content = content.replace(OLD_LAZY, NEW_LAZY, 1)
    print("✓ Lazy import added")

# 2. Replace the inline IPAMPage function definition
#    Find function IPAMPage and the closing brace of the outer function
# Strategy: find "function IPAMPage({currentUser, p})" and replace the entire
# function until the next top-level "function " that follows it.

fn_start_marker = "function IPAMPage({currentUser, p}) {"
fn_start_idx = content.find(fn_start_marker)
if fn_start_idx == -1:
    print("IPAMPage function not found in App.jsx (may already be replaced).")
    open(APP, "w", encoding="utf-8").write(content)
    exit(0)

# Find the end of this function by counting braces
search_from = fn_start_idx + len(fn_start_marker)
depth = 1
i = search_from
while i < len(content) and depth > 0:
    c = content[i]
    if c == '{':
        depth += 1
    elif c == '}':
        depth -= 1
    i += 1

fn_end_idx = i  # just past the closing brace

old_fn = content[fn_start_idx:fn_end_idx]
print(f"Found IPAMPage function: chars {fn_start_idx}..{fn_end_idx} ({len(old_fn)} chars)")

# New replacement: empty stub (actual component is lazy-loaded from IPAMPage.jsx)
new_fn = (
    "// IPAMPage is now a standalone lazy-loaded component (IPAMPage.jsx)\n"
    "// See: src/IPAMPage.jsx"
)

content = content[:fn_start_idx] + new_fn + content[fn_end_idx:]
print(f"✓ Inline IPAMPage function replaced ({len(old_fn)} chars -> {len(new_fn)} chars)")

# 3. Fix the page routing: ensure IPAMPage is wrapped in Suspense
OLD_ROUTE = '{page==="ipam"      &&<IPAMPage currentUser={currentUser} p={p}/>'
NEW_ROUTE = '''{page==="ipam"      &&<PageErrorBoundary page="IPAM"><Suspense fallback={<div style={{padding:48,textAlign:"center",color:"#64748b",fontSize:18}}>⏳ Loading IPAM…</div>}><IPAMPage currentUser={currentUser} p={p}/></Suspense></PageErrorBoundary>}'''

if OLD_ROUTE in content:
    content = content.replace(OLD_ROUTE, NEW_ROUTE, 1)
    print("✓ Route updated with Suspense wrapper")
elif 'IPAMPage' in content and 'Suspense' in content[content.find('{page==="ipam"'):content.find('{page==="ipam"')+200]:
    print("Route already has Suspense, skipping.")
else:
    print("WARNING: Could not find exact route string, check manually.")

open(APP, "w", encoding="utf-8").write(content)
print(f"DONE. File written ({len(content)} chars)")
