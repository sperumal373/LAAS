import requests, re
requests.packages.urllib3.disable_warnings()
# Get HTML
r = requests.get("https://localhost/", verify=False)
m = re.search(r'src="/assets/(index-[^"]+)"', r.text)
print("HTML JS:", m.group(1) if m else "NOT FOUND")

# Get the JS and check for the debug marker
if m:
    r2 = requests.get("https://localhost/assets/" + m.group(1), verify=False)
    print("JS size:", len(r2.text))
    print("Has DEBUG:", "DEBUG: ptAapInstances" in r2.text)
    print("Has PRELOAD:", "PRELOAD AAP" in r2.text)
    print("Has hardcoded IP:", "172.17.92.62" in r2.text)
    # Find the ptAapInstances.length check in rendered JSX
    idx = r2.text.find("ptAapInstances.length")
    if idx >= 0:
        print("Context around ptAapInstances.length:", r2.text[idx-100:idx+100])