path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()

old = b'cancelPlan(plan.id)'
new = b'doUpdateStatus(plan.id, "cancelled")'

# Only replace first occurrence (the table row one at line 1250)
# Check it's the right one
lines = raw.split(b'\r\n')
count = raw.count(old)
print(f'Found {count} occurrence(s) of cancelPlan(plan.id)')
if count == 1:
    raw = raw.replace(old, new, 1)
    open(path, 'wb').write(raw)
    print('Done - replaced with doUpdateStatus')
else:
    print('Multiple or zero - manual fix needed')
