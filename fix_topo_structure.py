"""
Fix get_volume_topology to return flat structure matching VolumeTopologyModal expectations.
Also fix corrupted emoji in VolumeTopologyModal in App.jsx.
"""
import re

# ── 1. Fix storage_client.py ─────────────────────────────────────────────────
sc_path = r'c:\caas-dashboard\backend\storage_client.py'
with open(sc_path, encoding='utf-8', errors='replace') as f:
    sc = f.read()

# Find the function boundaries
fn_start = sc.find('def get_volume_topology')
next_fn  = sc.find('\ndef ', fn_start + 10)

# Find the last "return result" inside the function
ret_idx = sc.rfind('    return result', fn_start, next_fn)
old_return = '    return result\n'

new_return = '''\
    # ── Flatten into the structure VolumeTopologyModal expects ──────────
    vol   = result.get("volume", {})
    conns = result.get("connections", [])

    def _fmt_bytes(b):
        try:
            b = int(b or 0)
        except Exception:
            b = 0
        if b >= 1 << 40: return f"{b/(1<<40):.2f} TB"
        if b >= 1 << 30: return f"{b/(1<<30):.2f} GB"
        if b >= 1 << 20: return f"{b/(1<<20):.2f} MB"
        return f"{b} B" if b else ""

    # Rename "host" key to "host_name" in every connection entry
    flat_topo = []
    for conn in conns:
        entry = dict(conn)
        if "host_name" not in entry:
            entry["host_name"] = entry.pop("host", "")
        flat_topo.append(entry)

    flat = {
        "vendor":         result.get("vendor", ""),
        "volume_name":    vol.get("name",       volume_name),
        "serial":         vol.get("serial",     ""),
        "wwn":            vol.get("wwn",        ""),
        "naa_id":         ("naa." + vol["serial"].lower()) if vol.get("serial") else "",
        "size":           _fmt_bytes(vol.get("size_bytes", 0)),
        "used":           _fmt_bytes(vol.get("used_bytes", 0)),
        "state":          vol.get("state",      ""),
        "protocol":       vol.get("protocol",   ""),
        "pool":           vol.get("cpg") or vol.get("pool") or vol.get("storage_pool") or "",
        "svm":            vol.get("svm",        ""),
        "pod":            vol.get("pod",        ""),
        "data_reduction": vol.get("data_reduction"),
        "thin":           vol.get("thin"),
        "lun_id":         vol.get("lun_id"),
        # extra vendor-specific passthrough
        "junction_path":  vol.get("junction_path", ""),
        "type":           vol.get("type", ""),
        "topology":       flat_topo,
        "storage_ports":  result.get("storage_ports", []),
        "replication":    result.get("replication", []),
        "error":          result.get("error"),
    }
    return flat
'''

if old_return in sc[ret_idx:ret_idx+30]:
    new_sc = sc[:ret_idx] + new_return + sc[ret_idx + len(old_return):]
    with open(sc_path, 'w', encoding='utf-8') as f:
        f.write(new_sc)
    print("OK: storage_client.py return statement replaced")
else:
    print("ERROR: could not find 'return result' in exact position")
    print("Nearby text:", repr(sc[ret_idx:ret_idx+40]))

# ── 2. Fix VolumeTopologyModal emoji corruption in App.jsx ───────────────────
app_path = r'c:\caas-dashboard\frontend\src\App.jsx'
with open(app_path, encoding='utf-8', errors='replace') as f:
    app = f.read()

fn_start = app.find('function VolumeTopologyModal')
fn_end   = app.find('\nfunction ', fn_start + 10)
modal    = app[fn_start:fn_end]
modal_orig = modal

R = chr(0xfffd)   # unicode replacement char (shown as ??? or ?)

# hostOsIcon function — replace empty/corrupted returns with text labels
modal = re.sub(
    r"if\(o\.includes\('windows'\)\|\|o\.includes\('win'\)\) return '.*?';",
    "if(o.includes('windows')||o.includes('win')) return '[Win]';",
    modal
)
modal = re.sub(
    r"if\(o\.includes\('vmware'\)\|\|o\.includes\('esxi'\)\|\|o\.includes\('esx'\)\) return '.*?';",
    "if(o.includes('vmware')||o.includes('esxi')||o.includes('esx')) return '[ESX]';",
    modal
)
modal = re.sub(
    r"if\(o\.includes\('linux'\)\|\|o\.includes\('rhel'\)\|\|o\.includes\('ubuntu'\)\) return '.*?';",
    "if(o.includes('linux')||o.includes('rhel')||o.includes('ubuntu')) return '[Lin]';",
    modal
)
modal = re.sub(
    r"if\(o\.includes\('aix'\)\) return '.*?';",
    "if(o.includes('aix')) return '[AIX]';",
    modal
)
modal = re.sub(
    r"if\(o\.includes\('solaris'\)\) return '.*?';",
    "if(o.includes('solaris')) return '[Sol]';",
    modal
)
# The final fallback return in hostOsIcon
modal = re.sub(
    r"(const hostOsIcon.*?return '';)\s",
    lambda m: m.group(0).replace("return '';", "return '[?]';"),
    modal,
    flags=re.DOTALL
)

# Fix Label strings with corrupted chars
modal = modal.replace(
    'Label t="?? Storage Array \ufffd Source Volume"',
    'Label t="[Storage Array - Source Volume]"'
)
modal = modal.replace(
    'Label t="?? Storage Array',
    'Label t="[Storage Array]'
)

# All remaining replacement chars in label strings
import re as _re
# Replace ??? and ? in JSX string literals and template literals
modal = modal.replace('??? Export PDF', 'Export PDF')
modal = modal.replace('??? Body ???', 'Body')
modal = modal.replace('??? Header bar ???', 'Header')
modal = modal.replace('?? Volume source card ??', 'Volume source card')
modal = modal.replace('?? Replication flows ??', 'Replication flows')
modal = modal.replace('? Source', 'Source')
modal = modal.replace('? Destination', 'Destination')
modal = modal.replace('? Building topology map.', 'Building topology map...')
modal = modal.replace('? Healthy', 'Healthy')
modal = modal.replace('? Unhealthy', 'Unhealthy')
modal = modal.replace('? Unknown', 'Unknown')

# Replace any stray unicode replacement chars in the modal section
modal = modal.replace(R, '-')

# status: replicates-to / replicates-from arrows (corrupted ? chars)
modal = modal.replace("'Replicates to ?'", "'Replicates to >>'")
modal = modal.replace("'? Replicates from'", "'<< Replicates from'")
# arrow div with single ? char
modal = _re.sub(
    r"<div style=\{.*?fontSize:14.*?\}\}>\?</div>",
    "<div style={{fontSize:14,color:sc}}>{'>'}</div>",
    modal,
    flags=re.DOTALL
)

if modal != modal_orig:
    new_app = app[:fn_start] + modal + app[fn_end:]
    with open(app_path, 'w', encoding='utf-8') as f:
        f.write(new_app)
    print("OK: App.jsx VolumeTopologyModal emoji/corruption fixed")
else:
    print("WARN: No changes made to App.jsx (patterns may not have matched)")
