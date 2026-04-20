import requests,urllib3,json
urllib3.disable_warnings()
s=requests.Session(); s.verify=False
r=s.post("https://172.17.168.212/api/session",auth=("administrator@vsphere.local","Sdxdc@168-212"))
s.headers["vmware-api-session-id"]=r.json()
# Get full VM details - disks show which datastore/host
vms=s.get("https://172.17.168.212/api/vcenter/vm?names=sdxdcwtesting3&hosts=host-85321").json()
print("On 172.17.73.19:",vms)
for hid in ["host-85321","host-85468","host-85470","host-85471","host-146426","host-146428","host-146430"]:
    vms=s.get(f"https://172.17.168.212/api/vcenter/vm?names=sdxdcwtesting3&hosts={hid}").json()
    if vms:
        h=[h for h in s.get("https://172.17.168.212/api/vcenter/host").json() if h["host"]==hid]
        print(f"FOUND on {hid}: {h[0]['name'] if h else '?'}")
        break
