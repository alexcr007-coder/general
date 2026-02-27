"""
Log into myflightscope.com and capture all data API calls made after login.
"""
import os
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(os.path.expanduser("~/.config/flightscope/.env"))
EMAIL = os.getenv("FLIGHTSCOPE_EMAIL")
PASSWORD = os.getenv("FLIGHTSCOPE_PASSWORD")

api_responses = {}

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # Intercept API responses to capture data
        def on_response(response):
            url = response.url
            if any(x in url for x in ["soap", "api", "session", "shot", "json", "data", "wp-json"]):
                try:
                    body = response.text()
                    if len(body) > 10:
                        api_responses[url] = body[:2000]  # save first 2000 chars
                except:
                    pass

        page.on("response", on_response)

        # --- Step 1: Load main page and click LOGIN ---
        print("Loading main page...")
        page.goto("https://myflightscope.com", timeout=60000, wait_until="networkidle")
        page.click("text=LOGIN", timeout=10000)

        # Wait for the form
        page.wait_for_selector("input[type='email']", timeout=15000)
        print("Login form ready, filling credentials...")

        page.fill("input[type='email']", EMAIL)
        page.fill("input[type='password']", PASSWORD)

        # --- Step 2: Submit login ---
        page.click("button:has-text('LOG IN'), input[type='submit']")
        print("Login submitted, waiting...")
        # Wait for page to navigate away from login (URL changes on success)
        try:
            page.wait_for_url(lambda url: "login" not in url.lower(), timeout=20000)
        except:
            pass  # might stay on same URL but logged in
        time.sleep(5)  # let the app fully load

        # Take screenshot to confirm login
        page.screenshot(path="after_login.png", full_page=True)
        print(f"After login URL: {page.url}")
        print(f"After login title: {page.title()}")

        # --- Step 3: Wait a bit more for data to load ---
        time.sleep(3)
        page.screenshot(path="after_login2.png", full_page=True)

        # Save captured API calls
        print(f"\nCaptured {len(api_responses)} API responses:")
        for url, body in api_responses.items():
            print(f"\n[URL] {url}")
            print(f"[BODY PREVIEW] {body[:300]}")

        with open("api_responses.json", "w") as f:
            json.dump(api_responses, f, indent=2)
        print("\nAll API responses saved to api_responses.json")

        browser.close()

if __name__ == "__main__":
    main()
