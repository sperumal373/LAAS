import requests,urllib3,json
urllib3.disable_warnings()
s=requests.Session(); s.verify=False
r=s.post("https://172.17.168.212/api/session",auth=("administrator@vsphere.local","Sdxdc@168-212"))
s.headers["vmware-api-session-id"]=r.json()
clusters=s.get("https://172.17.168.212/api/vcenter/cluster").json()
for c in clusters:
    hosts=s.get(f"https://172.17.168.212/api/vcenter/host?clusters={c['cluster']}").json()
    for h in hosts:
        if h["name"]=="172.17.66.86":
            print(f"Host 172.17.66.86 is in cluster: {c['name']}")
