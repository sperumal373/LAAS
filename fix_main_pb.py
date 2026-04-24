path = r"C:\caas-dashboard\backend\main.py"
content = open(path, "r", encoding="utf-8").read()

old = 'def list_available_playbooks(group_id: int, aap_id: int = None, u=Depends(require_role("admin","operator"))):'
new = 'def list_available_playbooks(group_id: int, aap_id: int = None, search: str = None, u=Depends(require_role("admin","operator"))):'
content = content.replace(old, new)

old2 = "            templates = get_aap_job_templates(inst)"
new2 = "            templates = get_aap_job_templates(inst, search=search)"
content = content.replace(old2, new2, 1)

old3 = "        except Exception:\n            pass"
new3 = "        except Exception as e:\n            import traceback; traceback.print_exc()"
content = content.replace(old3, new3, 1)

open(path, "w", encoding="utf-8").write(content)
print("Updated main.py")
