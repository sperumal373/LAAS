import sys
sys.stdout.reconfigure(encoding="utf-8")

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")

# Find the OperationProgressDrawer definition start
DRAWER_START = "  const OperationProgressDrawer=()=>{"
# Find the main return
MAIN_RETURN = "  return(<div style={{padding:"

ds = t.find(DRAWER_START)
mr = t.find(MAIN_RETURN)
print(f"Drawer at char {ds}, Main return at char {mr}")
print(f"Drawer is after return: {ds > mr}")

if ds > mr:
    # Find end of OperationProgressDrawer (look for "  };\n" after ds)
    de = t.find("\n  };\n", ds) + len("\n  };\n")
    print(f"Drawer ends at char {de}")
    
    # Extract the drawer
    drawer_code = t[ds:de]
    
    # Remove it from current position
    t = t[:ds] + t[de:]
    
    # Re-find main return position (shifted)
    mr2 = t.find(MAIN_RETURN)
    print(f"Main return now at char {mr2}")
    
    # Insert drawer just before main return
    t = t[:mr2] + drawer_code + "\n" + t[mr2:]
    print("Moved drawer before return")

# Verify
import re
comps = re.findall(r"const (\w+Tab|\w+Modal|\w+Drawer)=", t)
mr_pos = t.find(MAIN_RETURN)
dr_pos = t.find(DRAWER_START)
print(f"Drawer at {dr_pos}, Return at {mr_pos}, Drawer before return: {dr_pos < mr_pos}")
print("Components:", comps)

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(t.encode("utf-8-sig"))
print("Done. Size:", len(t))