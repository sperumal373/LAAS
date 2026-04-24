text = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", encoding="utf-8").read()

# Fix duplicate getToken import - remove the extra one
text = text.replace("  getToken,\n  getToken,\n", "  getToken,\n")
print("1. Fixed duplicate import")

# In AapDropdown: replace "token" references with getToken()
# The component has: { Authorization: "Bearer " + (tok || "") }
# and: const tok = token;
# Replace the whole auth pattern in both components

# Fix AapDropdown - it currently uses "token" prop  
text = text.replace(
    'function AapDropdown({ value, onSelect, p, token }) {',
    'function AapDropdown({ value, onSelect, p }) {'
)
text = text.replace(
    'function PlaybookDropdown({ aapId, groupId, value, onSelect, p, token }) {',
    'function PlaybookDropdown({ aapId, groupId, value, onSelect, p }) {'
)
print("2. Removed token from component signatures")

# Replace "const tok = token;" with "const tok = getToken();"
text = text.replace('const tok = token;', 'const tok = getToken();')
print("3. Fixed tok assignment")

# Replace (tok || "") with tok in Authorization headers
text = text.replace('"Bearer " + (tok || "")', '"Bearer " + tok')
print("4. Fixed Bearer token")

# In PlaybookDropdown, it uses token directly in Authorization header
# Fix: Authorization: "Bearer " + token -> "Bearer " + getToken()
# Find the PlaybookDropdown component and fix its fetch
# Look for pattern in PlaybookDropdown
idx_pb = text.find("function PlaybookDropdown")
idx_end = text.find("export default function MigrationPage")
pb_section = text[idx_pb:idx_end]
pb_fixed = pb_section.replace('"Bearer " + token', '"Bearer " + getToken()')
text = text[:idx_pb] + pb_fixed + text[idx_end:]
print("5. Fixed PlaybookDropdown auth")

# Remove token={...} props from JSX usage
text = text.replace(' token={getToken()}', '')
print("6. Removed token props from JSX")

open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", "w", encoding="utf-8").write(text)

# Verify
t2 = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", encoding="utf-8").read()
print("\nVerification:")
print("  getToken imports:", t2.count("getToken,"))
print("  getToken() calls:", t2.count("getToken()"))
print("  localStorage remaining:", t2.count("localStorage"))
print("  token prop remaining:", t2.count("token={"))
print("  Bearer + token:", t2.count('"Bearer " + token'))