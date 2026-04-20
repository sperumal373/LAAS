import sys, re
sys.stdout.reconfigure(encoding='utf-8')
c = open(r'c:\caas-dashboard\frontend\src\App.jsx', encoding='utf-8', errors='replace').read()

# Find all vendor option values in the storage form
idx = c.find('function StoragePage')
chunk = c[idx:idx+15000]

# Find all <option value="..."> lines
options = re.findall(r"<option value=\"([^\"]+)\"", chunk)
print("Form option values:", options)

# Find vendor: in EMPTY form def
form_vendors = re.findall(r'vendor:"([^"]+)"', chunk)
print("Form vendor defaults:", form_vendors)

# find the vendor dropdown area
vidx = chunk.find('vendor')
print("\nVendor area:")
print(chunk[vidx:vidx+600])
