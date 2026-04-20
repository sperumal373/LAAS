from nutanix_move_client import MoveClient
c = MoveClient()
c.login()
uuid = "29c8edc7-c4c4-4f71-a564-b3869c3df8c1"
try:
    r = c.cutover_plan(uuid)
    print(f"Cutover triggered: {r}")
except Exception as e:
    print(f"Cutover error: {e}")
