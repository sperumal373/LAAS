api = open(r'C:\caas-dashboard\frontend\src\api.js', 'r', encoding='utf-8').read()
old = 'export async function runPreflightCheck(body)        { return _post("/api/migration/preflight", body); }'
found = old in api
print('Found marker:', found)
if found:
    new = 'export async function updatePlanStatus(id, body)    { return _patch(`/api/migration/plans/${id}/status`, body); }\n'
    new += 'export async function executeMigrationPlan(id)     { return _post(`/api/migration/plans/${id}/execute`, {}); }\n'
    new += 'export async function fetchPlanEvents(id)          { return _get(`/api/migration/plans/${id}/events`); }\n'
    new += old
    api = api.replace(old, new)
    open(r'C:\caas-dashboard\frontend\src\api.js', 'w', encoding='utf-8').write(api)
    print('api.js updated!')