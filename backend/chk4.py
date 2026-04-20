from nutanix_move_client import MoveClient
c = MoveClient(); c.login()
r = c.get_plan("ece9a675-ed90-40ba-9d14-4a7c9b29ec2e")
md = r.get("MetaData",{})
print(f"State: {md.get('StateString')}")
print(f"VMStateCounts: {md.get('VMStateCounts')}")
print(f"Actions: {md.get('Actions')}")
print(f"Data: {md.get('MigratedDataInBytes',0)/1073741824:.1f}/{md.get('DataInBytes',0)/1073741824:.1f} GB")
