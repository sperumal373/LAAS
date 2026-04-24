text = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", encoding="utf-8").read()

# Fix 1: AapDropdown - accept token prop and use fetchAPI from parent
# The issue is localStorage.getItem("token") returns null in the component
# because it's defined outside MigrationPage. Pass token explicitly.

# Change AapDropdown signature to accept token
text = text.replace(
    'function AapDropdown({ value, onSelect, p }) {',
    'function AapDropdown({ value, onSelect, p, token }) {'
)

# Change PlaybookDropdown signature to accept token
text = text.replace(
    'function PlaybookDropdown({ aapId, groupId, value, onSelect, p }) {',
    'function PlaybookDropdown({ aapId, groupId, value, onSelect, p, token }) {'
)

# Fix all localStorage.getItem("token") in AapDropdown and PlaybookDropdown
# These are the ones BEFORE "export default function MigrationPage"
export_idx = text.find("export default function MigrationPage")
before = text[:export_idx]
after = text[export_idx:]

before = before.replace('localStorage.getItem("token")', 'token')
text = before + after

# Fix the JSX where components are used - add token prop
text = text.replace(
    '<AapDropdown value={ptSelAapInst} onSelect={v => { setPtSelAapInst(v); setPtSelTemplate(""); }} p={p} />',
    '<AapDropdown value={ptSelAapInst} onSelect={v => { setPtSelAapInst(v); setPtSelTemplate(""); }} p={p} token={localStorage.getItem("token")} />'
)
text = text.replace(
    '<PlaybookDropdown aapId={ptSelAapInst} groupId={ptGroupId} value={ptSelTemplate} onSelect={v => setPtSelTemplate(v)} p={p} />',
    '<PlaybookDropdown aapId={ptSelAapInst} groupId={ptGroupId} value={ptSelTemplate} onSelect={v => setPtSelTemplate(v)} p={p} token={localStorage.getItem("token")} />'
)

open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", "w", encoding="utf-8").write(text)
print("Fixed: token now passed as prop")