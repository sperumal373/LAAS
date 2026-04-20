"""Capture project utilization — stay in SPA, click nav item, wait for data."""
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

        # Login — do not reload after login
        await pg.goto(BASE, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        try:
            inputs = await pg.query_selector_all('input')
            await inputs[0].fill("admin")
            await inputs[1].fill("caas@2024")
            btns = await pg.query_selector_all('button')
            for b in btns:
                txt = (await b.inner_text()).lower()
                if 'login' in txt or 'sign' in txt:
                    await b.click()
                    break
            await pg.wait_for_load_state("networkidle", timeout=20000)
            await asyncio.sleep(8)   # wait for dashboard + API calls
            print("Logged in")
        except Exception as e:
            print(f"Login error: {e}"); return

        body = await pg.evaluate("document.body.innerText")
        if 'Sign In' in body[:200]:
            print("Still on login page — login failed"); return
        print("Dashboard loaded OK")

        # Show available nav items
        nav_texts = await pg.evaluate("""
            () => [...document.querySelectorAll('.nav-link')]
                  .map(el => el.textContent.trim().replace(/\\s+/g,' '))
        """)
        print("Nav links found:", nav_texts)

        # Click the Project Utilization nav item (stay within SPA)
        clicked = await pg.evaluate("""
            () => {
                const links = [...document.querySelectorAll('.nav-link')];
                for (const el of links) {
                    if (el.textContent.includes('Project') || el.textContent.includes('Utiliz')) {
                        el.click();
                        return el.textContent.trim();
                    }
                }
                // Broader sidebar search
                const sidebar = document.querySelector('.sidebar');
                if (sidebar) {
                    for (const el of [...sidebar.querySelectorAll('div,span,a,button')]) {
                        const t = el.textContent.trim().replace(/\\s+/g,' ');
                        const tl = t.toLowerCase();
                        if ((tl.includes('project') || tl.includes('utiliz')) && t.length < 60) {
                            el.click();
                            return t;
                        }
                    }
                }
                return null;
            }
        """)
        print(f"Clicked nav item: {repr(clicked)}")

        # Poll until real content appears (up to 25 seconds)
        print("Waiting for data to load...")
        found = False
        for i in range(13):
            await asyncio.sleep(2)
            text = await pg.evaluate("document.body.innerText")
            if any(k in text for k in ['vCPU', 'Memory', 'No project', 'No data', 'Utilization', 'project']):
                print(f"  Content detected at {(i+1)*2}s")
                found = True
                break
            print(f"  Still loading... ({(i+1)*2}s)")

        if not found:
            print("  No content detected — taking screenshot anyway")

        await asyncio.sleep(2)  # final render buffer
        path = os.path.join(OUT, "07_project_util.png")
        await pg.screenshot(path=path)
        size = os.path.getsize(path) // 1024
        print(f"Saved: 07_project_util.png  ({size} KB)")

        text = await pg.evaluate("document.body.innerText")
        print("Page text (first 500):", text[:500].encode('ascii','replace').decode())
        await browser.close()

asyncio.run(run())
