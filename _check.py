with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")
lines = t.split("\n")
print("Lines:", len(lines))
print("Last 5:")
for l in lines[-5:]: print(repr(l[:100]))
print("Has Drawer:", "OperationProgressDrawer" in t)
print("Has main return:", "return(<div style={{padding" in t)
print("Has export default:", "export default function" in t)