content = open(r'nutanix_move_client.py', encoding='utf-8').read()

old = (
    '    plan_name = plan_row.get("plan_name", f"plan-{plan_id}")\n'
    '    source = plan_row.get("source_vcenter") or plan_row.get("source_detail") or ""\n'
    '    target = plan_row.get("target_detail", "")\n'
    '\n'
    '    if is_move_reachable():'
)
new = (
    '    plan_name = plan_row.get("plan_name", f"plan-{plan_id}")\n'
    '    source = plan_row.get("source_vcenter") or plan_row.get("source_detail") or ""\n'
    '    target = plan_row.get("target_detail", "")\n'
    '\n'
    '    # Storage offload (Nutanix Move CBT Sync)\n'
    '    storage_offload = options.get("storage_offload", True)\n'
    '    if storage_offload:\n'
    '        log.info("\u26a1 Storage Offload (Nutanix Move CBT Sync): ENABLED -- incremental disk sync via CBT")\n'
    '    else:\n'
    '        log.info("\u25cb Storage Offload (Nutanix Move CBT Sync): DISABLED")\n'
    '\n'
    '    if is_move_reachable():'
)

if old in content:
    content = content.replace(old, new, 1)
    open(r'nutanix_move_client.py', 'w', encoding='utf-8').write(content)
    print("PATCHED OK")
else:
    print("NOT FOUND - checking context:")
    idx = content.find('plan_name = plan_row.get')
    print(repr(content[idx:idx+300]))
