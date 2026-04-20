import requests,urllib3,json
urllib3.disable_warnings()
s=requests.Session(); s.verify=False
r=s.post("https://172.17.168.212/api/session",auth=("administrator@vsphere.local","Sdxdc@168-212"))
s.headers["vmware-api-session-id"]=r.json()
d=s.get("https://172.17.168.212/api/vcenter/vm/vm-413253").json()
print("Host field:",d.get("host"))
hosts=s.get("https://172.17.168.212/api/vcenter/host").json()
for h in hosts:
    if h["host"]==d.get("host"):
        print(f"ESXi: {h}")
clusters=s.get("https://172.17.168.212/api/vcenter/cluster").json()
print("Clusters:", [c["name"] for c in clusters])
