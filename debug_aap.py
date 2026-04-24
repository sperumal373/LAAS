import sys; sys.path.insert(0, r'C:\caas-dashboard\backend')
from ansible_client import list_aap_instances, get_aap_job_templates
insts = list_aap_instances()
print(f'Found {len(insts)} instances')
for inst in insts:
    print(f'  id={inst["id"]} name={inst["name"]} url={inst["url"]}')
    try:
        templates = get_aap_job_templates(inst)
        print(f'    -> {len(templates)} templates')
        for t in templates[:3]:
            print(f'       {t.get("id")}: {t.get("name")}')
    except Exception as e:
        print(f'    -> ERROR: {type(e).__name__}: {e}')