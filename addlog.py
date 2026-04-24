text = open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx","rb").read().decode("utf-8")
old = '''    } catch (e) { showToast("Failed to load post-tasks: " + e.message, "error"); }
    setPtLoading(false);'''
new = '''    } catch (e) { console.error("PT LOAD ERROR:", e); showToast("Failed to load: " + e.message, "error"); }
    setPtLoading(false);'''
if old in text:
    text = text.replace(old, new)
    # Also add logging to the success path
    old2 = 'setPtAapInstances((aapRes.instances || []).filter(i => i.status === "ok"));'
    new2 = 'const _okI = (aapRes.instances || []).filter(i => i.status === "ok"); console.log("AAP instances loaded:", _okI.length, aapRes); setPtAapInstances(_okI);'
    text = text.replace(old2, new2)
    open(r"C:\caas-dashboard\frontend\src\MigrationPage.jsx","wb").write(text.encode("utf-8"))
    print("Added logging")
else:
    print("Pattern not found - checking...")
    idx = text.find("catch (e) { showToast")
    print(f"catch idx: {idx}")
    idx2 = text.find("setPtAapInstances")
    print(f"setPtAapInstances idx: {idx2}")
    if idx2 > 0:
        print("Context:", repr(text[idx2-20:idx2+100]))