path = r"C:\caas-dashboard\backend\ansible_client.py"
content = open(path, "r", encoding="utf-8").read()

# Add search parameter to function
old = "def get_aap_job_templates(inst)"
if old in content and "search" not in content.split("def get_aap_job_templates")[1].split("\n")[0]:
    content = content.replace(old, "def get_aap_job_templates(inst, search=None)")
    # Pass search to _paginate or add to URL params
    # Find where the URL is built
    if 'url = f"{base}/api/v2/job_templates/"' in content:
        content = content.replace(
            'url = f"{base}/api/v2/job_templates/"',
            'url = f"{base}/api/v2/job_templates/"\n    params = {}\n    if search:\n        params["search"] = search'
        )
    open(path, "w", encoding="utf-8").write(content)
    print("Updated ansible_client.py with search param")
else:
    print("Already updated or different signature")
