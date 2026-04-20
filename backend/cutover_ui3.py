from nutanix_move_client import MoveClient
import re
c = MoveClient()
c.login()

# Download the app JS to find cutover API call
r = c.s.get(f"{c.base}/app.689739f", timeout=15)
if r.status_code != 200:
    # Get the actual filename from the HTML
    r2 = c.s.get(f"{c.base}/api/v2", timeout=10)
    scripts = re.findall(r'src="/(app\.[^"]+)"', r2.text)
    print(f"Scripts: {scripts}")
    if scripts:
        r = c.s.get(f"{c.base}/{scripts[0]}", timeout=15)
        print(f"App JS: {r.status_code} {len(r.text)} bytes")
        # Search for cutover related strings
        for pattern in ["cutover", "Cutover", "CUTOVER", "startCutover", "start_cutover"]:
            matches = [(m.start(), r.text[max(0,m.start()-50):m.end()+100]) for m in re.finditer(pattern, r.text)]
            for pos, ctx in matches[:3]:
                print(f"  [{pos}] ...{ctx}...")
