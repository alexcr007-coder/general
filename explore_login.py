"""
Step 1: Log into myflightscope.com and explore what data is available.
"""
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import json

# Load credentials from our secure file
load_dotenv(os.path.expanduser("~/.config/flightscope/.env"))
EMAIL = os.getenv("FLIGHTSCOPE_EMAIL")
PASSWORD = os.getenv("FLIGHTSCOPE_PASSWORD")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Capture any API/data calls the site makes in the background
        api_calls = []
        def on_request(request):
            if any(x in request.url for x in ["api", "session", "shot", "data", "json", "xml"]):
                api_calls.append({"method": request.method, "url": request.url})

        page.on("request", on_request)

        print("Navigating to login page...")
        page.goto("https://myflightscope.com/Account/Login", wait_until="networkidle")

        print("Filling in credentials...")
        # Try common field selectors
        page.fill("input[type='email'], input[name*='email'], input[name*='Email'], input[id*='email']", EMAIL)
        page.fill("input[type='password']", PASSWORD)

        print("Submitting login form...")
        page.click("button[type='submit'], input[type='submit']")
        page.wait_for_load_state("networkidle")

        current_url = page.url
        title = page.title()
        print(f"After login URL: {current_url}")
        print(f"Page title: {title}")

        # Check if login was successful
        if "login" in current_url.lower() or "Login" in current_url:
            print("ERROR: Still on login page - check credentials")
        else:
            print("SUCCESS: Logged in!")

            # Save page content to inspect structure
            content = page.content()
            with open("page_after_login.html", "w") as f:
                f.write(content)
            print("Saved page HTML to page_after_login.html")

            # Print API calls captured
            print(f"\nAPI/data calls detected ({len(api_calls)}):")
            for call in api_calls[:30]:
                print(f"  [{call['method']}] {call['url']}")

        browser.close()

if __name__ == "__main__":
    main()
