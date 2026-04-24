text = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx","rb").read().decode("utf-8")

# Replace the entire openPostTasks with debug version
old = "async function openPostTasks(gid) {"
new = """async function openPostTasks(gid) {
    console.log("OPEN POST TASKS gid=", gid);"""
text = text.replace(old, new, 1)

# Add alert after the fetch
old2 = "setPtAapInstances(_okI);"
if old2 in text:
    text = text.replace(old2, 'console.log("OK INSTANCES:", _okI); setPtAapInstances(_okI);')

# Also add catch logging
old3 = 'catch (e) { console.error("PT LOAD ERROR:", e);'
if old3 not in text:
    old3b = 'catch (e) { showToast("Failed to load'
    text = text.replace(old3b, 'catch (e) { console.error("PT LOAD ERROR:", e); showToast("Failed to load')

open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx","wb").write(text.encode("utf-8"))
print("Debug logging added")