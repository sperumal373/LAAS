with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","rb") as f:
    t = f.read().decode("utf-8-sig")
lines = t.split("\n")

# Reconstruct: lines 1-272 (wizard) + blank + lines 549-end (drawer + return)
good = lines[:272] + [""] + lines[548:]
result = "\n".join(good)
print("New line count:", len(good))

# Add missing API imports
if "fetchZertoVirtSites" not in result:
    result = result.replace(
        "  fetchZertoTask,",
        "  fetchZertoTask, fetchZertoVirtSites, fetchZertoVirtSiteVMs,"
    )
    print("Imports patched")

# Add wizard state vars if missing
if "vpgWizStep" not in result:
    result = result.replace(
        "const[createVPGModal,setCreateVPGModal]=useState(false);",
        "const[createVPGModal,setCreateVPGModal]=useState(false);\n"
        "  const[vpgWizStep,setVpgWizStep]=useState(1);\n"
        "  const[virtSites,setVirtSites]=useState([]);\n"
        "  const[virtVMs,setVirtVMs]=useState([]);\n"
        "  const[virtVMsLoading,setVirtVMsLoading]=useState(false);\n"
        '  const[vmSearch2,setVmSearch2]=useState("");'
    )
    print("State patched")

print("Has wizard:", "vpgWizStep" in result)
print("Has drawer:", "OperationProgressDrawer" in result)
print("Has return:", "return(<div style={{padding" in result)
print("Has exports:", "export default" in result)

with open(r"C:\caas-dashboard\frontend\src\ZertoPage.jsx","wb") as f:
    f.write(result.encode("utf-8-sig"))
print("Done. Lines:", result.count("\n"))