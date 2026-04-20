"""
Fix cmdb_client.py:
1. _collect_storage() - use SQLite directly instead of get_array_data()
2. _collect_physical() - include position in correlation_id to avoid collisions
"""
import re

with open(r'C:\caas-dashboard\backend\cmdb_client.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# ─── Fix 1: Replace _collect_storage (lines 417-457, 0-indexed 416-456) ─────

new_storage_func = '''\
def _collect_storage() -> list:
    """Storage arrays - read directly from SQLite (bypass live API calls that may fail)."""
    cis = []
    try:
        import sqlite3
        db_path = Path(__file__).parent / "caas.db"
        conn_s = sqlite3.connect(str(db_path))
        conn_s.row_factory = sqlite3.Row
        cur_s = conn_s.cursor()
        cur_s.execute("SELECT * FROM storage_arrays")
        rows = cur_s.fetchall()
        conn_s.close()
        for arr in rows:
            arr = dict(arr)
            name   = arr.get("name") or ""
            vendor = arr.get("vendor") or ""
            ip     = arr.get("ip") or ""
            site   = arr.get("site") or "dc"
            status = str(arr.get("status") or "").lower()
            op_status = "operational" if status in ("ok", "online", "active", "healthy", "1") else "non-operational"
            cap_tb = arr.get("capacity_tb") or 0
            cis.append({
                "sys_class_name":     "cmdb_ci_storage_device",
                "name":               name,
                "correlation_id":     f"storage:{vendor.lower()}:{ip}",
                "operational_status": op_status,
                "environment":        "Production",
                "department":         "SDx-COE",
                "business_unit":      "SDx-COE",
                "company":            "SDx-COE",
                "ip_address":         ip,
                "manufacturer":       vendor,
                "model_id":           vendor,
                "serial_number":      "",
                "disk_space_gb":      float(cap_tb) * 1024 if cap_tb else 0,
                "source_platform":    "storage",
                "source_id":          str(arr.get("id", "")),
                "location":           site.upper(),
                "extra": json.dumps({
                    "vendor":       vendor,
                    "site":         site,
                    "capacity_tb":  cap_tb,
                    "status":       arr.get("status"),
                    "console_url":  arr.get("console_url"),
                    "last_checked": arr.get("last_checked"),
                    "port":         arr.get("port"),
                }),
            })
    except Exception as e:
        log.warning(f"CMDB: Storage collection error: {e}")
    return cis
'''

# Find the start of _collect_storage
start_idx = None
for i, line in enumerate(lines):
    if line.strip() == 'def _collect_storage() -> list:':
        start_idx = i
        break

if start_idx is None:
    print("ERROR: could not find _collect_storage start")
    exit(1)

# Find the end: next top-level def after start
end_idx = None
for i in range(start_idx + 1, len(lines)):
    if lines[i].startswith('def ') or lines[i].startswith('class '):
        end_idx = i
        break

print(f"_collect_storage: lines {start_idx+1}-{end_idx} (0-indexed {start_idx}-{end_idx-1})")

new_storage_lines = [l + '\n' for l in new_storage_func.rstrip('\n').split('\n')]
new_storage_lines.append('\n')
new_storage_lines.append('\n')

lines = lines[:start_idx] + new_storage_lines + lines[end_idx:]
print(f"After Fix 1: {len(lines)} lines total")

# ─── Fix 2: Fix correlation_id and source_id in _collect_physical ────────────

fixed_corr = 0
fixed_src  = 0
for i, line in enumerate(lines):
    if '"correlation_id":' in line and 'f"asset:{site}:{rack}:{aname}"' in line:
        lines[i] = line.replace(
            'f"asset:{site}:{rack}:{aname}"',
            "f\"asset:{site}:{rack}:{a.get('position','')}:{aname}\""
        )
        print(f"Fix 2a correlation_id at line {i+1}")
        fixed_corr += 1

    if '"source_id":' in line and 'f"{site}:{rack}:{aname}"' in line:
        lines[i] = line.replace(
            'f"{site}:{rack}:{aname}"',
            "f\"{site}:{rack}:{a.get('position','')}:{aname}\""
        )
        print(f"Fix 2b source_id at line {i+1}")
        fixed_src += 1

print(f"Fixed {fixed_corr} correlation_id lines, {fixed_src} source_id lines")

# ─── Write back ───────────────────────────────────────────────────────────────

with open(r'C:\caas-dashboard\backend\cmdb_client.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("cmdb_client.py updated successfully!")

# ─── Verify ───────────────────────────────────────────────────────────────────
import ast
try:
    with open(r'C:\caas-dashboard\backend\cmdb_client.py', 'r', encoding='utf-8') as f:
        src = f.read()
    ast.parse(src)
    print("Syntax check: OK")
except SyntaxError as e:
    print(f"Syntax ERROR: {e}")
