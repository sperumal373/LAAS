from vmware_client import _detect_applications
tests = [
    {"name": "sdxdclpurekvdb01", "guest_os": "Red Hat Enterprise Linux 8", "annotation": "", "guest_id": "", "folder": "", "tags": ["DataBase team"]},
    {"name": "cicd-jenkins-new", "guest_os": "Other Linux (64-bit)", "annotation": "", "guest_id": "", "folder": "", "tags": ["ServiceTheater Team"]},
    {"name": "k8s_wn01", "guest_os": "Other Linux (64-bit)", "annotation": "", "guest_id": "", "folder": "", "tags": ["OpenShift(Infra)"]},
    {"name": "VCSA8.0U1", "guest_os": "Other 3.x or later Linux (64-bit)", "annotation": "", "guest_id": "", "folder": "", "tags": []},
    {"name": "Ansible_Tower_Test_Post", "guest_os": "Red Hat Enterprise Linux 7", "annotation": "", "guest_id": "", "folder": "", "tags": ["DataBase team"]},
    {"name": "sdxdcw2025jh01", "guest_os": "Microsoft Windows Server 2022 (64-bit)", "annotation": "", "guest_id": "", "folder": "", "tags": []},
]
for t in tests:
    apps = _detect_applications(t)
    print(f'{t["name"]:35s} -> {[a["app"] for a in apps]}')
