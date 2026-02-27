"""
Click the LOGIN button on the main page and wait for the login modal/form to appear.
"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    print("Loading main page...")
    page.goto("https://myflightscope.com", timeout=60000, wait_until="networkidle")
    page.screenshot(path="main_page.png")
    print("Main page loaded, clicking LOGIN button...")

    # Click the login button in the top nav
    page.click("text=LOGIN", timeout=10000)
    print("Clicked LOGIN, waiting for form...")

    # Wait for input fields to appear
    try:
        page.wait_for_selector("input", timeout=15000)
        print("Form appeared!")
    except:
        print("Form didn't appear after 15s")

    page.screenshot(path="login_modal.png", full_page=True)
    print("Screenshot saved to login_modal.png")

    inputs = page.query_selector_all("input")
    print(f"\nFound {len(inputs)} input fields:")
    for inp in inputs:
        print(f"  type={inp.get_attribute('type')} name={inp.get_attribute('name')} id={inp.get_attribute('id')} placeholder={inp.get_attribute('placeholder')}")

    browser.close()
