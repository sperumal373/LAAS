"""
Capture full-page screenshots of all CaaS Portal pages.
Strategy:
  1. Use the REST API to get a JWT token
  2. Open browser to the portal
  3. Inject token into sessionStorage
  4. Verify with /api/auth/me that the token is valid from browser context
  5. Navigate pages by setting sessionStorage + location.reload()
"""
import os, time, json, urllib3
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PORTAL_URL     = "https://laas-dashboard.sdxtest.local"
API_BASE       = "https://172.17.70.100:8443"
USERNAME       = "admin"
PASSWORD       = "caas@2024"
SCREENSHOT_DIR = r"C:\caas-dashboard\screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

PAGES = [
    ("overview",            "01_overview"),
    ("vms",                 "02_vmware_vms"),
    ("snapshots",           "03_snapshots"),
    ("networks",            "04_networks"),
    ("capacity",            "05_capacity"),
    ("project_utilization", "06_projects"),
    ("chargeback",          "07_chargeback"),
    ("requests",            "08_requests"),
    ("ipam",                "09_ipam"),
    ("assets",              "10_assets"),
    ("openshift",           "11_openshift"),
    ("nutanix",             "12_nutanix"),
    ("ansible",             "13_ansible"),
    ("aws",                 "14_aws"),
    ("hyperv",              "15_hyperv"),
    ("storage",             "16_storage"),
    ("backup",              "17_backup"),
    ("cmdb",                "18_cmdb"),
    ("addns",               "19_ad_dns"),
    ("users",               "20_users"),
    ("audit",               "21_audit"),
    ("insights",            "22_insights"),
    ("history",             "23_history"),
    ("forecast",            "24_forecast"),
]


def get_token_and_user():
    """Get JWT token + user object via the REST API."""
    print("[1] Getting token via API...")
    resp = requests.post(
        f"{API_BASE}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        verify=False, timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"    Token: {data['token'][:20]}...")
    print(f"    User:  {data['user']['username']}")
    return data["token"], data["user"]


def setup_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--force-device-scale-factor=1.0")
    opts.add_argument("--ignore-certificate-errors")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(5)
    return driver


def do_login_via_form(driver, token, user_dict):
    """
    Approach: load page, use JS to inject session, then do a proper
    form-based login so React picks it up naturally.
    """
    print("[2] Loading portal...")
    driver.get(PORTAL_URL)
    time.sleep(4)

    # First, try form login - fill username & password and submit
    print("[3] Attempting form login...")
    login_ok = driver.execute_script("""
        try {
            var inputs = document.querySelectorAll('input');
            var userInput = null, passInput = null;
            for (var inp of inputs) {
                var t = (inp.type || '').toLowerCase();
                var ph = (inp.placeholder || '').toLowerCase();
                if (t === 'password') passInput = inp;
                else if (t === 'text' || t === 'email' || ph.includes('user')) userInput = inp;
            }
            if (!userInput || !passInput) return 'no_inputs';

            // Set values using React-compatible approach
            var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeInputValueSetter.call(userInput, arguments[0]);
            userInput.dispatchEvent(new Event('input', { bubbles: true }));
            userInput.dispatchEvent(new Event('change', { bubbles: true }));

            nativeInputValueSetter.call(passInput, arguments[1]);
            passInput.dispatchEvent(new Event('input', { bubbles: true }));
            passInput.dispatchEvent(new Event('change', { bubbles: true }));

            // Find and click submit button
            var btns = document.querySelectorAll('button');
            for (var btn of btns) {
                if (btn.type === 'submit' || btn.innerText.toLowerCase().includes('sign')) {
                    btn.click();
                    return 'clicked';
                }
            }
            // Try form submit
            var form = document.querySelector('form');
            if (form) { form.submit(); return 'form_submitted'; }
            return 'no_button';
        } catch(e) {
            return 'error: ' + e.message;
        }
    """, USERNAME, PASSWORD)
    print(f"    Form login result: {login_ok}")
    time.sleep(6)

    # Check if we got past login
    stored_token = driver.execute_script("return sessionStorage.getItem('caas_token');")
    if stored_token:
        print(f"    Login successful! Token in sessionStorage: {stored_token[:20]}...")
        return True

    # If form login didn't work, inject token directly and reload
    print("[3b] Form login didn't set token. Injecting API token...")
    user_json = json.dumps(user_dict)
    driver.execute_script(
        "sessionStorage.setItem('caas_token', arguments[0]);"
        "sessionStorage.setItem('caas_user',  arguments[1]);"
        "sessionStorage.setItem('caas_page',  'overview');",
        token, user_json
    )

    # Verify token is stored before reload
    check = driver.execute_script("return sessionStorage.getItem('caas_token');")
    print(f"    Token stored: {check[:20] if check else 'NONE'}...")

    # Navigate (not refresh) to the same URL to trigger fresh React mount
    driver.get(PORTAL_URL)
    time.sleep(6)

    # Check again
    check2 = driver.execute_script("return sessionStorage.getItem('caas_token');")
    body = driver.execute_script("return document.body.innerText.substring(0, 300);")
    print(f"    After reload - token: {check2[:20] if check2 else 'NONE'}")
    print(f"    Page text: {body[:150]}...")

    if check2 and "Sign In" not in body[:100]:
        print("    Dashboard loaded!")
        return True

    # Last resort: try setting token AFTER page load via direct API call from browser
    print("[3c] Trying fetch-based login from browser context...")
    browser_result = driver.execute_script("""
        return fetch('/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: arguments[0], password: arguments[1]})
        })
        .then(r => r.json())
        .then(data => {
            sessionStorage.setItem('caas_token', data.token);
            sessionStorage.setItem('caas_user', JSON.stringify(data.user));
            sessionStorage.setItem('caas_page', 'overview');
            return 'ok:' + data.token.substring(0, 16);
        })
        .catch(e => 'error:' + e.message);
    """, USERNAME, PASSWORD)

    # Wait for the async fetch to complete
    time.sleep(5)
    check3 = driver.execute_script("return sessionStorage.getItem('caas_token');")
    print(f"    Browser fetch result token: {check3[:20] if check3 else 'NONE'}")

    if check3:
        # Reload to let React pick it up
        driver.get(PORTAL_URL)
        time.sleep(6)
        check4 = driver.execute_script("return sessionStorage.getItem('caas_token');")
        body2 = driver.execute_script("return document.body.innerText.substring(0, 300);")
        print(f"    Final - token: {check4[:20] if check4 else 'NONE'}")
        print(f"    Final page: {body2[:150]}...")
        if check4 and "Sign In" not in body2[:100]:
            return True

    print("    WARNING: Could not confirm login. Will try screenshots anyway.")
    return False


def wait_for_data(driver, page_key, max_wait=20):
    """Wait for page data to load."""
    time.sleep(3)
    for attempt in range(max_wait):
        time.sleep(1)
        still_loading = driver.execute_script("""
            var spinners = document.querySelectorAll(
                '[class*="spinner"], [class*="loading"], [class*="skeleton"], [class*="Spinner"]'
            );
            for (var s of spinners) {
                if (s.offsetParent !== null && s.offsetWidth > 0) return true;
            }
            var body = document.body.innerText;
            if (body.includes('Loading...') || body.includes('Syncing...')) return true;
            return false;
        """)
        if not still_loading:
            break
        if attempt % 5 == 0 and attempt > 0:
            print(f"      Still loading... ({attempt}s)")
    time.sleep(3)


def navigate_and_capture(driver, page_key, filename):
    """Navigate to a page and capture screenshot."""
    print(f"\n  [{filename}] → '{page_key}'")

    # Set the page key in sessionStorage
    driver.execute_script(
        "sessionStorage.setItem('caas_page', arguments[0]);",
        page_key
    )
    # Reload to trigger React to read the new page from sessionStorage
    driver.refresh()
    time.sleep(2)

    wait_for_data(driver, page_key)

    # Scroll to top
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

    filepath = os.path.join(SCREENSHOT_DIR, f"{filename}.png")
    driver.save_screenshot(filepath)
    size = os.path.getsize(filepath)
    print(f"      Saved: {filename}.png ({size // 1024} KB)")
    return filepath


def main():
    token, user_dict = get_token_and_user()
    driver = setup_driver()

    try:
        ok = do_login_via_form(driver, token, user_dict)

        print(f"\n[4] Capturing {len(PAGES)} pages...")
        for page_key, filename in PAGES:
            navigate_and_capture(driver, page_key, filename)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

    print(f"\n{'=' * 60}")
    print(f"Screenshots saved to: {SCREENSHOT_DIR}")
    pngs = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith('.png')]
    print(f"Total PNG files: {len(pngs)}")


if __name__ == "__main__":
    main()
