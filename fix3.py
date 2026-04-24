path = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(path, 'rb').read()
old = b'user?.role === "admin"'
count = raw.count(old)
print(f'Found {count}')
raw = raw.replace(old, b'currentUser?.role === "admin"')
open(path, 'wb').write(raw)
print('Fixed all occurrences')
