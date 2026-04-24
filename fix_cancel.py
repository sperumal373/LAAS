import re

path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()

old = b'                          <button onClick={() => delPlan(plan.id)} style={{ background: "transparent", border: "none", cursor: "pointer", color: p.red, fontWeight: 700, fontSize: 11 }}>{"\xf0\x9f\x97\x91\xef\xb8\x8f"}</button>'

cancel_btn = b'                          {user?.role === "admin" && ["executing","migrating","validating"].includes(plan.status) && <button onClick={() => cancelPlan(plan.id)} style={{ background: "transparent", border: "none", cursor: "pointer", color: p.warn || "#f59e0b", fontWeight: 700, fontSize: 13 }} title="Cancel">{"\xe2\x9c\x96"}</button>}\r\n'

new = cancel_btn + old

count = raw.count(old)
print(f'Found {count} match(es)')
if count == 1:
    raw = raw.replace(old, new, 1)
    open(path, 'wb').write(raw)
    print('Done - cancel button added')
else:
    print('ERROR: expected 1 match')
