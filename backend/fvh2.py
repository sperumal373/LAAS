import requests,urllib3,json
urllib3.disable_warnings()
s=requests.Session(); s.verify=False
r=s.post("https://172.17.168.212/api/session",auth=("administrator@vsphere.local","Sdxdc@168-212"))
s.headers["vmware-api-session-id"]=r.json()
vms=s.get("https://172.17.168.212/api/vcenter/vm?names=sdxdcwtesting3").json()
print("VMs:",json.dumps(vms))
