const fs = require('fs');
const path = 'C:/caas-dashboard/backend/vmware_client.py';
const src = fs.readFileSync(path, 'utf8');
const crlf = src.includes('\r\n');
const EOL = crlf ? '\r\n' : '\n';
const lines = src.split(EOL);

// Replace lines 238-260 (0-indexed 237-259) with the new function
const newFn = [
'def _snapshots(si, vid, vname):',
'    rows = []',
'    content = si.RetrieveContent()',
'    cnt = content.viewManager.CreateContainerView(',
'        content.rootFolder, [vim.VirtualMachine], True)',
'    # Query event history for snapshot create events to get creator username',
'    creator_map = {}',
'    try:',
'        em = content.eventManager',
'        spec = vim.event.EventFilterSpec()',
'        spec.category = ["info"]',
'        spec.type = [vim.event.VmSnapshotCreateSucceededEvent]',
'        collector = em.CreateCollectorForEvents(spec)',
'        collector.SetCollectionPageSize(1000)',
'        while True:',
'            events = collector.ReadNextEvents(100)',
'            if not events:',
'                break',
'            for ev in events:',
'                vm_name = (ev.vm.name if ev.vm else "") or ""',
'                snap_name = getattr(ev, "snapName", "") or ""',
'                user = (ev.userName or "").split("\\\\")[-1].split("/")[-1]',
'                key = vm_name + "::" + snap_name',
'                if key and key not in creator_map:',
'                    creator_map[key] = user',
'        collector.DestroyCollector()',
'    except Exception:',
'        pass',
'    for vm in cnt.view:',
'        try:',
'            if not vm.snapshot:',
'                continue',
'            vn = vm.summary.config.name',
'            def walk(lst):',
'                for s in lst:',
'                    key = vn + "::" + s.name',
'                    rows.append({',
'                        "vcenter_id": vid, "vcenter_name": vname,',
'                        "vm_name": vn, "snapshot_name": s.name,',
'                        "description": s.description or "",',
'                        "created": str(s.createTime)[:19].replace("T"," "),',
'                        "state": str(s.state),',
'                        "created_by": creator_map.get(key, ""),',
'                    })',
'                    walk(s.childSnapshotList)',
'            walk(vm.snapshot.rootSnapshotList)',
'        except Exception:',
'            pass',
'    return rows',
'',
];

const start = 237; // 0-indexed line 238
const end = 260;   // 0-indexed line 261 (exclusive, up to blank line)
lines.splice(start, end - start, ...newFn);

fs.writeFileSync(path, lines.join(EOL));
console.log('Done. Replaced _snapshots function with', newFn.length, 'lines');

// Verify
const verify = fs.readFileSync(path, 'utf8').split(EOL);
for (let i = start; i < start + newFn.length + 2; i++) console.log((i+1) + ': ' + verify[i]);
