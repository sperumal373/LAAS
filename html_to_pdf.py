"""Convert USER_MANUAL.html to USER_MANUAL.pdf using Playwright (full CSS rendering)."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

HTML_PATH = Path(r"c:\caas-dashboard\USER_MANUAL.html").resolve()
PDF_PATH  = Path(r"c:\caas-dashboard\USER_MANUAL.pdf").resolve()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        await page.goto(HTML_PATH.as_uri(), wait_until="networkidle")
        # Give any CSS animations a moment to settle
        await page.wait_for_timeout(500)
        await page.pdf(
            path=str(PDF_PATH),
            format="A4",
            print_background=True,
            margin={"top": "15mm", "bottom": "15mm", "left": "12mm", "right": "12mm"},
        )
        await browser.close()
    size = PDF_PATH.stat().st_size
    print(f"PDF written: {PDF_PATH}  ({size:,} bytes)")

asyncio.run(main())
