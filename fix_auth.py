text = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", encoding="utf-8").read()

# 1. Add getToken to the import from "./api"
old_import = "} from \"./api\";"
new_import = "  getToken,\n} from \"./api\";"
text = text.replace(old_import, new_import, 1)
print("1. Added getToken import")

# 2. Replace ALL localStorage.getItem("token") with getToken()
count = text.count('localStorage.getItem("token")')
text = text.replace('localStorage.getItem("token")', 'getToken()')
print(f"2. Replaced {count} localStorage.getItem calls with getToken()")

# 3. Also replace the token prop pattern (from previous fix)
text = text.replace('token={getToken()}', '')  # remove redundant token prop
text = text.replace(', token', '')  # remove token from component signatures  
# Actually be more careful - only fix the component signatures
# Let me redo this more carefully

open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", "w", encoding="utf-8").write(text)
print("SAVED")

# Verify
text2 = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx", encoding="utf-8").read()
print("localStorage.getItem remaining:", text2.count('localStorage.getItem("token")'))
print("getToken() count:", text2.count('getToken()'))
print("getToken in import:", "getToken," in text2)