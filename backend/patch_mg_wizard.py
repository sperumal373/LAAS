"""Fix Move Group migrate to use full wizard flow"""
f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()
q = b'\x22'

# 1. Replace handleMigrateGroup function to feed into wizard
old_fn = b'async function handleMigrateGroup(gid) {\r\n    if (!mgTargetPlatform) return showToast(' + q + b'Select a target platform' + q + b', ' + q + b'error' + q + b');\r\n    try {\r\n      const r = await migrateGroup(gid, mgTargetPlatform, {});\r\n      showToast(`Created ${r.plans_created} migration plan(s)! Go to Plans tab.`, ' + q + b'success' + q + b');\r\n      setMgMigrateId(null); setMgTargetPlatform(' + q + q + b');\r\n      loadGroups();\r\n    } catch (e) { showToast(e.message, ' + q + b'error' + q + b'); }\r\n  }'
new_fn = b'function handleMigrateFromGroup(group) {\r\n    if (!group.vms || !group.vms.length) return showToast(' + q + b'No VMs in this group' + q + b', ' + q + b'error' + q + b');\r\n    // Pick the first vCenter (or if all same, just use it)\r\n    const firstVC = group.vms[0].vcenter_id;\r\n    const vcName = group.vms[0].vcenter_name || firstVC;\r\n    // Build selVMs map {vmName: vmObject}\r\n    const vmMap = {};\r\n    const vmList = [];\r\n    group.vms.filter(v => v.vcenter_id === firstVC).forEach(v => {\r\n      vmMap[v.vm_name] = true;\r\n      vmList.push({ name: v.vm_name, moref: v.vm_moref || ' + q + q + b', guest_os: v.guest_os, cpu: v.cpu, memory_mb: v.memory_mb, disk_gb: v.disk_gb, power_state: v.power_state, ip_address: v.ip_address, esxi_host: v.esxi_host });\r\n    });\r\n    // Set wizard state\r\n    setSelVC(firstVC);\r\n    setAllVMs(vmList);\r\n    setSelVMs(vmMap);\r\n    setPlanName(group.name);\r\n    setStep(1); // Go to Step 2: Target selection\r\n    setTab(' + q + b'new' + q + b');\r\n    const multiVC = new Set(group.vms.map(v => v.vcenter_id)).size > 1;\r\n    if (multiVC) showToast(`Loaded ${Object.keys(vmMap).length} VMs from ${vcName}. Create separate plans for other vCenters.`, ' + q + b'success' + q + b');\r\n    else showToast(`Loaded ${Object.keys(vmMap).length} VMs into wizard. Select your target.`, ' + q + b'success' + q + b');\r\n  }'

assert old_fn in raw, 'handleMigrateGroup function not found'
raw = raw.replace(old_fn, new_fn, 1)
print('1. Replaced handleMigrateGroup with handleMigrateFromGroup')

# 2. Replace the Migrate button to call new function (pass full group object)
old_btn = b'<button onClick={e => { e.stopPropagation(); setMgMigrateId(isMigrating ? null : g.id); }} disabled={!g.vm_count}'
new_btn = b'<button onClick={e => { e.stopPropagation(); handleMigrateFromGroup(g); }} disabled={!g.vm_count}'
assert old_btn in raw, 'Migrate button not found'
raw = raw.replace(old_btn, new_btn, 1)
print('2. Updated Migrate button')

# 3. Remove the inline migrate panel (isMigrating section)
# Find {isMigrating && ( ... )} block
migrate_start = b'                {/* Migrate panel */}\r\n                {isMigrating && ('
migrate_end_marker = b'                )}\r\n\r\n                {/* Expanded: VM list'
idx_start = raw.find(migrate_start)
idx_end = raw.find(migrate_end_marker)
if idx_start > 0 and idx_end > idx_start:
    raw = raw[:idx_start] + raw[idx_end:]
    print('3. Removed inline migrate panel')
else:
    print('3. WARNING: Could not find migrate panel boundaries, skipping')
    print('  start:', idx_start, 'end:', idx_end)

open(f, 'wb').write(raw)
print('Done! Size:', len(raw))