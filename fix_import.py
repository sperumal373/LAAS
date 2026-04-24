path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
data = open(path, "rb").read()
# Add getToken to existing api import - it ends with '} from "./api";'
old = b'} from "./api";'
new = b'  getToken,\r\n} from "./api";'
# Only replace first occurrence
data = data.replace(old, new, 1)
open(path, "wb").write(data)
print("Added getToken to api import")
