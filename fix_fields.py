path = r"C:\caas-dashboard\frontend\src\MigrationPage.jsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix all field name mismatches
replacements = [
    # Power state
    ("v.power_state", "v.status"),
    ("vm.power_state", "vm.status"),
    # CPU
    ("v.num_cpu", "v.cpu"),
    ("vm.num_cpu", "vm.cpu"),
    # Memory - was memory_mb, actual is ram_gb
    ("v.memory_mb", "v.ram_gb"),
    ("vm.memory_mb", "vm.ram_gb"),
    # Storage
    ("v.storage_used_gb", "v.disk_gb"),
    ("vm.storage_used_gb", "vm.disk_gb"),
    # ESXi host
    ("v.esxi_host", "v.host"),
    ("vm.esxi_host", "vm.host"),
    # VM moref
    ("v.vm_moref", "v.moid"),
    ("vm.vm_moref", "vm.moid"),
]

for old, new in replacements:
    count = content.count(old)
    if count > 0:
        content = content.replace(old, new)
        print(f"  {old} -> {new} ({count}x)")

# Fix RAM display: was memory_mb/1024, now ram_gb directly
content = content.replace("(vm.ram_gb / 1024).toFixed(1)", "(vm.ram_gb || 0).toFixed(1)")
content = content.replace("((v.ram_gb || 0) / 1024)", "(v.ram_gb || 0)")

# Fix power state display: was "poweredOn", actual is "poweredOn" too but let's handle both
# The badge check: vm.status === "poweredOn"
# Already correct since we changed power_state to status

# Fix totalRAM calc: was memory_mb/1024, now ram_gb directly
content = content.replace(
    "((v.memory_mb || 0) / 1024)",
    "(v.ram_gb || 0)"
)
content = content.replace(
    "s + ((v.ram_gb || 0) / 1024)",
    "s + (v.ram_gb || 0)"
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("All field names fixed")
