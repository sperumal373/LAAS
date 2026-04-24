f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()
q = b'\x22'

# 1. Fix handleMigrateFromGroup to fetch fresh VM data from vCenter
old_fn_start = b'function handleMigrateFromGroup(group) {'
old_fn_end = b'else showToast(`Loaded ${Object.keys(vmMap).length} VMs into wizard. Select your target.`, ' + q + b'success' + q + b');\r\n  }'
idx_start = raw.find(old_fn_start)
idx_end = raw.find(old_fn_end)
assert idx_start > 0 and idx_end > idx_start, f'Function not found: start={idx_start} end={idx_end}'

new_fn = (
    b'async function handleMigrateFromGroup(group) {\r\n'
    b'    if (!group.vms || !group.vms.length) return showToast(' + q + b'No VMs in this group' + q + b', ' + q + b'error' + q + b');\r\n'
    b'    const firstVC = group.vms[0].vcenter_id;\r\n'
    b'    const vcName = group.vms[0].vcenter_name || firstVC;\r\n'
    b'    const groupVMNames = new Set(group.vms.filter(v => v.vcenter_id === firstVC).map(v => v.vm_name));\r\n'
    b'    // Fetch fresh VM data from vCenter for full fields (network, datastore, snapshots)\r\n'
    b'    showToast(' + q + b'Loading VMs from vCenter...' + q + b', ' + q + b'success' + q + b');\r\n'
    b'    try {\r\n'
    b'      const vr = await fetchVMs(firstVC);\r\n'
    b'      const allVms = (Array.isArray(vr) ? vr : vr.vms || []).filter(v => v.vcenter_id === firstVC || !v.vcenter_id);\r\n'
    b'      setSelVC(firstVC);\r\n'
    b'      setAllVMs(allVms);\r\n'
    b'      // Pre-select VMs that are in the group\r\n'
    b'      const vmMap = {};\r\n'
    b'      allVms.forEach(v => { if (groupVMNames.has(v.name)) vmMap[v.moid || v.name] = true; });\r\n'
    b'      setSelVMs(vmMap);\r\n'
    b'      setPlanName(group.name);\r\n'
    b'      setStep(1); // Target selection\r\n'
    b'      setTab(' + q + b'new' + q + b');\r\n'
    b'      const multiVC = new Set(group.vms.map(v => v.vcenter_id)).size > 1;\r\n'
    b'      if (multiVC) showToast(`Loaded ${Object.keys(vmMap).length} VMs from ${vcName}. Create separate plans for other vCenters.`, ' + q + b'success' + q + b');\r\n'
    b'      else showToast(`Loaded ${Object.keys(vmMap).length} VMs into wizard. Select your target.`, ' + q + b'success' + q + b');\r\n'
    b'    } catch (e) { showToast(' + q + b'Failed to load VMs: ' + q + b' + e.message, ' + q + b'error' + q + b'); }\r\n'
    b'  }'
)

raw = raw[:idx_start] + new_fn + raw[idx_end + len(old_fn_end):]
print('1. Fixed handleMigrateFromGroup to fetch fresh VM data')

open(f, 'wb').write(raw)
print('Done! Size:', len(raw))