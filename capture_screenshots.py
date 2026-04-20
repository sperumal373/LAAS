import time, os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DIR = r"C:\caas-dashboard\screenshots"
URL = "https://localhost"
W, H = 1920, 1080

PAGES = [
    ("overview",  "01_overview.png",    7, "Overview Dashboard"),
    ("vmware",    "02_vmware.png",      6, "VMware vCenter"),
    ("openshift", "03_openshift.png",   6, "Red Hat OpenShift"),
    ("nutanix",   "04_nutanix.png",     6, "Nutanix Prism Central"),
    ("ansible",   "05_ansible.png",     5, "Ansible Automation"),
    ("aws",       "06_aws.png",         5, "Amazon Web Services"),
    ("hyperv",    "07_hyperv.png",      5, "Microsoft Hyper-V"),
    ("ad",        "08_ad_dns.png",      5, "Active Directory & DNS"),
    ("ipam",      "09_ipam.png",        5, "IPAM"),
    ("capacity",  "10_chargeback.png",  5, "Chargeback"),
    ("assets",    "11_assets.png",      5, "Asset Inventory"),
    ("requests",  "12_vm_requests.png", 5, "VM Requests"),
    ("insights",  "13_insights.png",    6, "Insights & Analytics"),
    ("history",   "14_history.png",     6, "Historical Trending"),
    ("forecast",  "15_forecast.png",    6, "Capacity Forecasting"),
    ("audit",     "16_audit.png",       5, "Audit Log"),
]

LABEL_MAP = {
    "overview": "overview", "vmware": "vmware", "openshift": "openshift",
    "nutanix": "nutanix", "ansible": "ansible", "aws": "aws",
    "hyperv": "hyper-v", "ad": "active directory", "ipam": "ipam",
    "capacity": "chargeback", "assets": "asset", "requests": "vm request",
    "insights": "insights", "history": "history", "forecast": "forecast",
    "audit": "audit",
}

def main():
    os.makedirs(DIR, exist_ok=True)
    opts = Options()
    for a in ["--headless=new","--disable-gpu","--no-sandbox",
              f"--window-size={W},{H}","--ignore-certificate-errors",
              "--allow-insecure-localhost","--force-device-scale-factor=1"]:
        opts.add_argument(a)

    driver = webdriver.Chrome(options=opts)
    driver.set_window_size(W, H)
    wait = WebDriverWait(driver, 15)

    try:
        print("[LOGIN]")
        driver.get(URL)
        time.sleep(3)

        ui = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[placeholder*="username"], input[placeholder*="admin"]')))
        ui.clear(); ui.send_keys("admin")

        pi = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        pi.clear(); pi.send_keys("caas@2024")
        time.sleep(1)

        driver.save_screenshot(os.path.join(DIR, "00_login.png"))
        print("  OK: 00_login.png")

        for b in driver.find_elements(By.TAG_NAME, "button"):
            if "sign" in b.text.lower():
                b.click(); break
        time.sleep(6)

        print("[PAGES]")
        for nav_id, fname, ws, desc in PAGES:
            try:
                target = LABEL_MAP.get(nav_id, nav_id)
                nav_items = driver.find_elements(By.CSS_SELECTOR, "nav div")
                for item in nav_items:
                    try:
                        if target in item.text.strip().lower():
                            item.click(); break
                    except: pass
                time.sleep(ws)
                fp = os.path.join(DIR, fname)
                driver.save_screenshot(fp)
                sz = os.path.getsize(fp) // 1024
                print(f"  OK: {fname} ({desc}) [{sz}KB]")
            except Exception as e:
                print(f"  FAIL: {fname} — {e}")

        # About modal
        print("[ABOUT]")
        for b in driver.find_elements(By.TAG_NAME, "button"):
            if "about" in b.text.lower():
                b.click(); time.sleep(2)
                fp = os.path.join(DIR, "17_about_laas.png")
                driver.save_screenshot(fp)
                print(f"  OK: 17_about_laas.png")
                for cb in driver.find_elements(By.TAG_NAME, "button"):
                    if cb.text.strip() in ("\u00d7", "Close"):
                        cb.click(); break
                break

        # Support modal
        print("[SUPPORT]")
        time.sleep(1)
        for b in driver.find_elements(By.TAG_NAME, "button"):
            if "support" in b.text.lower() or "contact" in b.text.lower():
                b.click(); time.sleep(2)
                fp = os.path.join(DIR, "18_support.png")
                driver.save_screenshot(fp)
                print(f"  OK: 18_support.png")
                for cb in driver.find_elements(By.TAG_NAME, "button"):
                    if cb.text.strip() in ("\u00d7", "Close"):
                        cb.click(); break
                break
    finally:
        driver.quit()

    files = sorted(f for f in os.listdir(DIR) if f.endswith(".png"))
    print(f"\nDone! {len(files)} screenshots.")
    for f in files:
        print(f"  {f}  ({os.path.getsize(os.path.join(DIR,f))//1024} KB)")

if __name__ == "__main__":
    main()
