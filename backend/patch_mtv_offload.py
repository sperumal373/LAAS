content = open(r'mtv_client.py', encoding='utf-8').read()
old = (
    '    # Determine warm/cold from user options, but override if CBT disabled\n'
    '    use_warm = options.get("warm", False)'
)
new = (
    '    # Determine warm/cold from user options, but override if CBT disabled\n'
    '    # storage_offload=True enables warm (incremental) migration via CBT\n'
    '    storage_offload = options.get("storage_offload", True)\n'
    '    if storage_offload:\n'
    '        import logging as _logging\n'
    '        _logging.getLogger("mtv_client").info("\u26a1 Storage Offload: ENABLED -- warm migration (CBT incremental sync) active for OpenShift MTV")\n'
    '    else:\n'
    '        import logging as _logging\n'
    '        _logging.getLogger("mtv_client").info("\u25cb Storage Offload: DISABLED -- cold (full copy) migration")\n'
    '    use_warm = options.get("warm", storage_offload)  # storage_offload drives warm mode'
)
if old in content:
    content = content.replace(old, new, 1)
    open(r'mtv_client.py', 'w', encoding='utf-8').write(content)
    print('PATCHED OK')
else:
    print('NOT FOUND')
    idx = content.find('Determine warm/cold')
    print(repr(content[idx:idx+200]))
