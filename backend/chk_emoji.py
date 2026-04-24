f = r'C:\caas-dashboard\frontend\src\MigrationPage.jsx'
raw = open(f, 'rb').read()
# Check for sparkle emoji (U+2728) = E2 9C A8 in UTF-8
sparkle_utf8 = b'\xe2\x9c\xa8'
if sparkle_utf8 in raw:
    print('Sparkle emoji OK (proper UTF-8)')
else:
    idx = raw.find(b'Magic Migrate')
    chunk = raw[idx-10:idx+5]
    print('Before Magic Migrate:', repr(chunk))
    
# Check clipboard emoji
idx2 = raw.find(b'Plans')
if idx2 > 0:
    chunk2 = raw[idx2-10:idx2+10]
    print('Around Plans:', repr(chunk2))