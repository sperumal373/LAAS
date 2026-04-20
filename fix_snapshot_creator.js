const fs = require('fs');
const path = 'C:/caas-dashboard/backend/main.py';
const src = fs.readFileSync(path, 'utf8');
const crlf = src.includes('\r\n');
const EOL = crlf ? '\r\n' : '\n';
const lines = src.split(EOL);

// Find dynamically
let bodyLine = -1;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('def snapshots(') && lines[i].includes('vcenter_id')) {
    // Function def found, body is next non-empty line
    bodyLine = i + 1;
    break;
  }
}
console.log('def at line', bodyLine, '(0-indexed)');
console.log('body:', JSON.stringify(lines[bodyLine]));

if (!lines[bodyLine] || !lines[bodyLine].includes('_filter')) {
  console.error('Body not found'); process.exit(1);
}

const newBody = [
    '    rows=_filter(_require_data()["snapshots"],vcenter_id)',
    '    try:',
    '        snap_logs=list_audit(limit=10000)',
    '        creator_map={}',
    '        for al in snap_logs:',
    '            if al.get("action")!="VM_SNAPSHOT": continue',
    '            vm=al.get("target","")',
    '            det=al.get("detail","")',
    '            snap_name=""',
    '            for part in det.split():',
    '                if part.startswith("snap="):',
    '                    snap_name=part[5:]; break',
    '            key=vm+"::"+snap_name',
    '            if key not in creator_map:',
    '                creator_map[key]=al.get("username","")',
    '        for r in rows:',
    '            key=(r.get("vm_name") or "")+" :: "+(r.get("snapshot_name") or "")',
    '            r["created_by"]=creator_map.get(key,"")',
    '    except Exception:',
    '        pass',
    '    return {"snapshots":rows,"count":len(rows)}',
];

lines.splice(bodyLine, 1, ...newBody);
console.log('Replaced body');

fs.writeFileSync(path, lines.join(EOL));
console.log('Done');
