from nutanix_move_client import MoveClient
import json
c = MoveClient()
c.login()
uuid = "a8de427d-4dd1-4f03-a86f-1616b6a7e5c4"

# The Move UI is a SPA - check what API routes exist by looking at /move/v2/
# Try the swagger/openapi endpoint
for path in ["/move/v2/api-docs", "/move/v2/swagger.json", "/move/v2/openapi.json", "/move/v2/docs", "/api/v2"]:
    r = c.s.get(f"{c.base}{path}", timeout=10)
    if r.status_code != 404:
        print(f"GET {path}: {r.status_code} {r.text[:300]}")

# The key insight: Move UI sends requests to /move/v2/plans with PUT
# Check what happens with DELETE + recreate approach
# BUT - let's first check the OPTIONS to see allowed methods
r = c.s.options(f"{c.base}/move/v2/plans/{uuid}/start", timeout=10)
print(f"\nOPTIONS /start: {r.status_code} Allow={r.headers.get('Allow','')}")

# Try the full plan list to see all the endpoints mentioned
# The UI likely does: PUT /move/v2/plans with action in body
r2 = c.s.put(f"{c.base}/move/v2/plans/{uuid}/start", json={"Spec":{}}, timeout=10)
print(f"PUT start: {r2.status_code} {r2.text[:200]}")
