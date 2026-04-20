from nutanix_move_client import MoveClient
c = MoveClient()
c.login()
r = c.s.delete(f"{c.base}/move/v2/plans/7977446b-248f-4482-94b7-9f002e0f5c09", timeout=15)
print(f"Delete: {r.status_code} {r.text[:200]}")
