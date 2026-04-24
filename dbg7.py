# Simplify: just fetch instances directly and remove the status filter
text = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx","rb").read().decode("utf-8")

# Replace the filter line to not filter, and add alert
old = 'const _okI = (aapRes.instances || []).filter(i => i.status === "ok"); console.log("AAP instances loaded:", _okI.length, aapRes); setPtAapInstances(_okI);'
if old in text:
    new = 'const _allI = aapRes.instances || aapRes || []; window._debug_aap = aapRes; console.log("AAP RAW:", JSON.stringify(aapRes).slice(0,300)); setPtAapInstances(Array.isArray(_allI) ? _allI : []);'
    text = text.replace(old, new)
    print("Replaced with debug + no filter")
else:
    # Try without the console.log version
    old2 = 'setPtAapInstances((aapRes.instances || []).filter(i => i.status === "ok"));'
    if old2 in text:
        new2 = 'window._debug_aap = aapRes; console.log("AAP RAW:", JSON.stringify(aapRes).slice(0,300)); setPtAapInstances((aapRes.instances || []).filter(i => i.status === "ok"));'
        text = text.replace(old2, new2)
        print("Added debug to original")
    else:
        print("Neither pattern found")
        # Search for what's actually there
        idx = text.find("setPtAapInstances")
        while idx != -1:
            print(f"  Found at {idx}: {repr(text[idx:idx+120])}")
            idx = text.find("setPtAapInstances", idx+1)

open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx","wb").write(text.encode("utf-8"))
print("Saved")