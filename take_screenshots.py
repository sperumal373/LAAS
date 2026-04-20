"""
take_screenshots.py  –  Automated LaaS Dashboard screenshots via Playwright.
"""
import asyncio, os
from playwright.async_api import async_playwright

BASE  = "http://localhost:5174"
OUT   = r"C:\caas-dashboard\screenshots"
W, H  = 1600, 900
os.makedirs(OUT, exist_ok=True)

PAGES = [
    ("01_login.png",         None),
    ("02_overview.png",      "overview"),
    ("03_vmware_vms.png",    "vms"),
    ("04_snapshots.png",     "snapshots"),
    ("05_networks.png",      "networks"),
    ("06_capacity.png",      "capacity"),
    ("07_project_util.png",  "project_utilization"),
    ("08_chargeback.png",    "chargeback"),
    ("09_requests.png",      "requests"),
    ("10_ipam.png",          "ipam"),
    ("11_assets.png",        "assets"),
    ("12_openshift.png",     "openshift"),
    ("13_nutanix.png",       "nutanix"),
    ("14_ansible.png",       "ansible"),
    ("15_addns.png",         "addns"),
    ("16_audit.png",         "audit"),
    ("17_users.png",         "users"),
]

async def nav_to(page, pid):
    """Navigate to page by setting sessionStorage and reloading."""
    if not pid:
        return
    await page.evaluate(f"sessionStorage.setItem('caas_page', {pid!r})")
    await page.reload(wait_until="domcontentloaded", timeout=15000)
    await asyncio.sleep(2.5)

async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"])
        ctx = await browser.new_context(
            viewport={"width": W, "height": H})
        pg = await ctx.new_page()

        # Login page
        await pg.goto(BASE, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        await pg.screenshot(path=os.path.join(OUT, "01_login.png"))
        print("  01_login.png")

        # Log in
        try:
            await pg.fill('input[type=text]', "admin")
            await pg.fill('input[type=password]', "caas@2024")
            await pg.click('button[type=submit]')
            await pg.wait_for_load_state("domcontentloaded", timeout=15000)
            await asyncio.sleep(3)
            print("  Logged in")
        except Exception as e:
            # Try alternative selectors
            try:
                inputs = await pg.query_selector_all('input')
                if len(inputs) >= 2:
                    await inputs[0].fill("admin")
                    await inputs[1].fill("caas@2024")
                btns = await pg.query_selector_all('button')
                for b in btns:
                    txt = await b.inner_text()
                    if 'login' in txt.lower() or 'sign' in txt.lower():
                        await b.click()
                        break
                await pg.wait_for_load_state("domcontentloaded", timeout=15000)
                await asyncio.sleep(3)
                print("  Logged in (fallback)")
            except Exception as e2:
                print(f"  Login failed: {e2}")

        # Save auth token to session
        await pg.screenshot(path=os.path.join(OUT, "02_overview.png"))
        print("  02_overview.png (default page)")

        # Capture each page
        for fname, pid in PAGES[2:]:
            try:
                await nav_to(pg, pid)
                await pg.screenshot(path=os.path.join(OUT, fname))
                size = os.path.getsize(os.path.join(OUT, fname)) // 1024
                print(f"  {fname}  ({size} KB)")
            except Exception as e:
                print(f"  ERROR {fname}: {e}")

        await browser.close()

    print("\nScreenshots saved:")
    for f in sorted(os.listdir(OUT)):
        kb = os.path.getsize(os.path.join(OUT, f)) // 1024
        print(f"  {f}  {kb} KB")

asyncio.run(run())
