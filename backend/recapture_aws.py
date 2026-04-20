"""Re-capture ONLY the AWS page with extra-long wait for full data load."""
import os, time, json, urllib3, requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PORTAL = "https://laas-dashboard.sdxtest.local"
API    = "https://172.17.70.100:8443"

# 1. Token
print("Getting token...")
r = requests.post(f"{API}/api/auth/login",
                  json={"username": "admin", "password": "caas@2024"},
                  verify=False, timeout=15)
data = r.json()
print(f"  Token: {data['token'][:16]}...")

# 2. Browser
opts = Options()
for a in ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
          "--window-size=1920,1080", "--force-device-scale-factor=1.0",
          "--ignore-certificate-errors", "--disable-gpu", "--disable-extensions"]:
    opts.add_argument(a)
driver = webdriver.Chrome(options=opts)
driver.set_page_load_timeout(60)

# 3. Load portal
print("Loading portal...")
driver.get(PORTAL)
time.sleep(4)

# 4. Form login
print("Logging in...")
inputs = driver.find_elements(By.CSS_SELECTOR, "input")
user_input = None
pass_input = None
for inp in inputs:
    itype = inp.get_attribute("type") or ""
    if itype == "password":
        pass_input = inp
    elif itype in ("text", "email", ""):
        user_input = inp

JS_SET = (
    "var ns = Object.getOwnPropertyDescriptor("
    "window.HTMLInputElement.prototype, 'value').set;"
    "ns.call(arguments[0], arguments[1]);"
    "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));"
)
driver.execute_script(JS_SET, user_input, "admin")
time.sleep(0.3)
driver.execute_script(JS_SET, pass_input, "caas@2024")
time.sleep(0.3)

btns = driver.find_elements(By.CSS_SELECTOR, "button")
for b in btns:
    if "sign" in (b.text or "").lower():
        b.click()
        break
time.sleep(8)

tk = driver.execute_script("return sessionStorage.getItem('caas_token');")
print(f"  Logged in: {bool(tk)}")

# 5. Navigate to AWS
print("Navigating to AWS...")
driver.execute_script("sessionStorage.setItem('caas_page', 'aws');")
driver.refresh()
time.sleep(10)

# 6. Click Refresh button on the AWS page to trigger data discovery
print("Clicking Refresh to trigger AWS discovery...")
try:
    refresh_btns = driver.find_elements(By.CSS_SELECTOR, "button")
    for b in refresh_btns:
        txt = (b.text or "").strip()
        if "refresh" in txt.lower():
            b.click()
            print(f"  Clicked: '{txt}'")
            break
except Exception as e:
    print(f"  Could not click Refresh: {e}")

# 7. Wait 60 seconds for AWS data to fully load after discovery
print("Waiting 60s for AWS data to fully load after discovery...")
time.sleep(60)

driver.execute_script("window.scrollTo(0, 0);")
time.sleep(2)

# 8. Screenshot
path = r"C:\caas-dashboard\screenshots\14_aws.png"
driver.save_screenshot(path)
print(f"Saved: 14_aws.png ({os.path.getsize(path)//1024} KB)")

driver.quit()
print("Done!")
