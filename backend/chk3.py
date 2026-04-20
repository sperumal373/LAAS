from nutanix_move_client import MoveClient
c = MoveClient(); c.login()
r = c.get_plan("29c8edc7-c4c4-4f71-a564-b3869c3df8c1")
md = r.get("MetaData",{})
print(f"State: {md.get('StateString')}")
print(f"Actions: {md.get('Actions')}")
print(f"VMStateCounts: {md.get('VMStateCounts')}")
gb = md.get("MigratedDataInBytes",0)/1073741824
total = md.get("DataInBytes",0)/1073741824
print(f"Data: {gb:.1f}/{total:.1f} GB")
print(f"Schedule: {md.get('Schedule')}")
print(f"Elapsed: {md.get('ElapsedTime')}")
