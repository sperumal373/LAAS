f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()

# Check line endings
crlf = raw.count(b'\r\n')
lf = raw.count(b'\n') - crlf
print(f'CRLF: {crlf}, LF-only: {lf}')

# Find exact bytes around Guest OS header
idx = raw.find(b'Guest OS</th>')
if idx > 0:
    chunk = raw[idx:idx+120]
    print('After Guest OS:', repr(chunk))