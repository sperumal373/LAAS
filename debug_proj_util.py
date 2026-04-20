"""Debug project utilization page — check what's on screen and try to trigger loading."""
import asyncio, os
from playwright.async_api import async_playwright

BASE  = "http://localhost:5174"
OUT   = r"C:\caas-dashboard\screenshots"

async def run():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True,
            args=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu"])
        ctx = await browser.new_context(viewport={"width":1600,"height":900})
        pg  = await ctx.new_page()

        # Login
        await pg.goto(BASE, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        try:
            inputs = await pg.query_selector_all('input')
            await inputs[0].fill("admin"); await inputs[1].fill("caas@2024")
            btns = await pg.query_selector_all('button')
            for b in btns:
                if 'login' in (await b.inner_text()).lower(): await b.click(); break
            await pg.wait_for_load_state("domcontentloaded", timeout=15000)
            await asyncio.sleep(4)
            print("Logged in")
        except Exception as e:
            print(f"Login: {e}")

        # Navigate via sessionStorage
        await pg.evaluate("sessionStorage.setItem('caas_page','project_utilization')")
        await pg.reload(wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(5)

        # Check page text content
        text = await pg.evaluate("document.body.innerText")
        print("PAGE TEXT (first 800 chars):")
        print(text[:800])
        print("---")

        # Check if there's a vCenter selector / dropdown
        selects = await pg.query_selector_all('select')
        print(f"Selects found: {len(selects)}")
        for sel in selects:
            val = await sel.evaluate("el => ({value:el.value, options:[...el.options].map(o=>o.text)})")
            print("  select:", val)

        # Check console errors
        errors = []
        pg.on("console", lambda msg: errors.append(f"{msg.type}: {msg.text}") if msg.type in ("error","warning") else None)

        await asyncio.sleep(3)

        # Try clicking a vCenter tab or "all" option
        try:
            # Look for any tab or button labeled "All" or a vCenter name
            btns_all = await pg.query_selector_all('button, .vc-tab, [class*=tab]')
            print(f"Buttons/tabs: {len(btns_all)}")
            for b in btns_all[:20]:
                txt = await b.inner_text()
                print(f"  btn: '{txt.strip()[:40]}'")
        except Exception as e:
            print(f"Buttons error: {e}")

        await pg.screenshot(path=os.path.join(OUT, "debug_proj_util.png"))
        print(f"Debug screenshot saved")

        await browser.close()

asyncio.run(run())
