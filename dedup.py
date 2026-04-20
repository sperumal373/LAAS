api = open(r'C:\caas-dashboard\frontend\src\api.js', 'r', encoding='utf-8').read()
# Remove duplicates - keep only one set
dup = 'export async function updatePlanStatus(id, body)    { return _patch(`/api/migration/plans/${id}/status`, body); }\nexport async function executeMigrationPlan(id)     { return _post(`/api/migration/plans/${id}/execute`, {}); }\nexport async function fetchPlanEvents(id)          { return _get(`/api/migration/plans/${id}/events`); }\n'
while api.count(dup) > 1:
    idx = api.rfind(dup)
    api = api[:idx] + api[idx+len(dup):]
open(r'C:\caas-dashboard\frontend\src\api.js', 'w', encoding='utf-8').write(api)
print('Deduped. Lines:', api.count(chr(10)))