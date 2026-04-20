import re

path = r'C:\caas-dashboard\frontend\src\App.jsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace all \\u2026 with actual ellipsis character
content = content.replace('\\u2026', '\u2026')

# 2. Convert lazy imports to regular imports
content = content.replace(
    "const OpenShiftPage = lazy(() => import('./OpenShiftPage'));",
    "import OpenShiftPage from './OpenShiftPage';"
)
content = content.replace(
    "const NutanixPage = lazy(() => import('./NutanixPage'));",
    "import NutanixPage from './NutanixPage';"
)
content = content.replace(
    "const AnsiblePage = lazy(() => import('./AnsiblePage'));",
    "import AnsiblePage from './AnsiblePage';"
)
content = content.replace(
    "const IPAMPage = lazy(() => import('./IPAMPage'));",
    "import IPAMPage from './IPAMPage';"
)

# 3. Remove Suspense wrappers around those 4 pages
content = re.sub(
    r'<Suspense fallback=\{<LoadState msg="[^"]*"/>\}>(<(?:OpenShiftPage|NutanixPage|AnsiblePage|IPAMPage)[^/]*/?>)</Suspense>',
    r'\1',
    content
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! All fixes applied.")
