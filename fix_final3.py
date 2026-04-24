path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
data = open(path, 'rb').read()

old_import_end = b'} from "./api";'
new_import_end = b'  getToken,\n} from "./api";'
if b'getToken' not in data[:data.find(old_import_end)+50]:
    data = data.replace(old_import_end, new_import_end, 1)
    print("Added getToken import")
else:
    print("getToken import already exists")

if b'>Applications</th>' not in data:
    data = data.replace(
        b'>VM Tags</th>',
        b'>VM Tags</th><th style={{padding:"8px 10px",textAlign:"left",whiteSpace:"nowrap"}}>Applications</th>',
        1
    )
    print("Added Applications header")

tags_pattern = b'.tags||[]).map('
idx = data.find(tags_pattern)
if idx > 0:
    td_close = data.find(b'</td>', idx)
    if td_close > 0:
        insert_pos = td_close + 5
        apps_cell = (
            b'<td style={{padding:"8px 10px"}}>'
            b'{(v.applications||[]).length>0 ? (v.applications||[]).map((a,i)=>'
            b'<span key={i} style={{display:"inline-block",padding:"2px 8px",borderRadius:12,'
            b'fontSize:11,fontWeight:600,marginRight:4,marginBottom:2,'
            b'background:"rgba(99,102,241,0.13)",color:"#818cf8"}}>{a}</span>'
            b') : <span style={{color:p.textMute,fontSize:11}}>\u2014</span>}'
            b'</td>'
        )
        if b'v.applications' not in data:
            data = data[:insert_pos] + apps_cell + data[insert_pos:]
            print("Added Applications data cell")
        else:
            print("Applications cell already exists")
else:
    print("Tags pattern not found")

open(path, 'wb').write(data)
print("Saved. getToken count: %d" % data.count(b'getToken'))
