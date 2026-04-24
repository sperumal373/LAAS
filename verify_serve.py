import requests, re
requests.packages.urllib3.disable_warnings()
r = requests.get("https://localhost/", verify=False)
# Find the JS filename in the HTML
m = re.search(r'index-(\w+)\.js', r.text)
print("HTML references JS hash:", m.group(1) if m else "NOT FOUND")
print("Expected: CB2-AXyP")

# Now fetch the actual JS file
js_url = "https://localhost/assets/index-CB2-AXyP.js"
r2 = requests.get(js_url, verify=False)
print(f"JS file status: {r2.status_code}, length: {len(r2.text)}")
print("Contains hardcoded IP:", "172.17.92.62" in r2.text)
print("Contains DEBUG text:", "DEBUG: ptAapInstances" in r2.text)