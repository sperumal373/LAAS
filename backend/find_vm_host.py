import requests,urllib3
urllib3.disable_warnings()
s=requests.Session(); s.verify=False
r=s.post("https://172.17.168.212/api/session",auth=("administrator@vsphere.local","Sdxdc@168-212"))
s.headers["vmware-api-session-id"]=r.json()
vms=s.get("https://172.17.168.212/api/vcenter/vm?names=sdxdcwtesting3").json()
vm_id=vms[0]["vm"]
d=s.get(f"https://172.17.168.212/api/vcenter/vm/{vm_id}").json()
host_name = d.get("host","unknown")
# resolve host name
hosts=s.get("https://172.17.168.212/api/vcenter/host").json()
for h in hosts:
    if h["host"] == host_name:
        print(f"VM on ESXi: {h['name']} ({host_name})")
        # find cluster
        clusters=s.get("https://172.17.168.212/api/vcenter/cluster").json()
        for c in clusters:
            ch=s.get(f"https://172.17.168.212/api/vcenter/host?clusters={c['cluster']}").json()
            for x in ch:
                if x["host"]==host_name:
                    print(f"Cluster: {c['name']} ({c['cluster']})")
        break
