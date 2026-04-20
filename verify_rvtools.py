s = open('C:/caas-dashboard/frontend/src/App.jsx', encoding='utf-8').read()
lines = s.split('\n')
checks = [
    ('fetchRVToolsStatus import',  'fetchRVToolsStatus'),
    ('loadRVToolsReports fn',      'async function loadRVToolsReports'),
    ('rvtools tab entry',          'id:"rvtools"'),
    ('RVTools render block',       'RVTools Reports tab'),
    ('doRunRVTools fn',            'async function doRunRVTools'),
    ('rvtReports state',           'rvtReports, setRvtReports'),
]
for name, token in checks:
    idx = next((i for i, l in enumerate(lines) if token in l), -1)
    status = f'line {idx+1}' if idx >= 0 else 'MISSING!'
    print(f'  {name}: {status}')
print(f'Total lines: {len(lines)}')
