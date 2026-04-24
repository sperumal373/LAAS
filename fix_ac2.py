path = r"C:\caas-dashboard\backend\ansible_client.py"
content = open(path, "r", encoding="utf-8").read()
content = content.replace(
    "def get_aap_job_templates(inst: dict) -> list:",
    "def get_aap_job_templates(inst: dict, search=None) -> list:"
)
open(path, "w", encoding="utf-8").write(content)
print("Done")
