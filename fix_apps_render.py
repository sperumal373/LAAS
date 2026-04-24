path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
data = open(path, 'rb').read()

# Fix the applications cell - {a} should be {a.app || a}
old = b'{a}</span>'
new = b'{typeof a === "string" ? a : a.app}</span>'
count = data.count(old)
print(f"Found {count} occurrences of apps render")
data = data.replace(old, new)

# Also fix the tags join that may have same issue
# vm.tags could also be objects
old2 = b'vm.tags.join(", ")'
new2 = b'vm.tags.map(t => typeof t === "string" ? t : (t.tag || t.key || JSON.stringify(t))).join(", ")'
data = data.replace(old2, new2)

open(path, 'wb').write(data)
print("Fixed applications render")
