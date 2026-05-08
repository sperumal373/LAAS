with open(r"C:\caas-dashboard\frontend\src\api.js","rb") as f:
    t = f.read().decode("utf-8-sig")

# Remove the broken last line
lines = t.split("\n")
lines = [l for l in lines if "fetchZertoTask = (siteId, taskId)" not in l]
t = "\n".join(lines)

# Add correct line using chr(96) for backtick
bt = chr(96)
add = f"export const fetchZertoTask = (siteId, taskId) => _get({bt}/api/zerto/sites/${'{'}siteId{'}'}/tasks/${'{'}taskId{'}'}{bt});\n"
t = t.rstrip() + "\n" + add

with open(r"C:\caas-dashboard\frontend\src\api.js","wb") as f:
    f.write(t.encode("utf-8-sig"))
print("Done:", t.count("export const fetchZertoTask "))
print("Last line:", repr(t.strip().split("\n")[-1]))