text = open(r"C:\caas-dashboard\backend\ansible_client.py", encoding="utf-8").read()

# Fix get_aap_job_templates to fetch all templates (no 500 limit)
text = text.replace(
    'items = _paginate(inst, "/api/v2/job_templates/")',
    'items = _paginate(inst, "/api/v2/job_templates/", max_items=10000)'
)
print("Fixed: job_templates max_items=10000")

open(r"C:\caas-dashboard\backend\ansible_client.py", "w", encoding="utf-8").write(text)
print("SAVED")