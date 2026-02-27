"""
Log in and capture the exact requests/responses made to the SOAP API.
"""
import os
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(os.path.expanduser("~/.config/flightscope/.env"))
EMAIL = os.getenv("FLIGHTSCOPE_EMAIL")
PASSWORD = os.getenv("FLIGHTSCOPE_PASSWORD")

SOAP_URL = "https://myflightscope.com/wp-content/plugins/fs-soap-frame/public/index.php"

captured = []

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        def on_request(request):
            if SOAP_URL in request.url:
                captured.append({
                    "type": "REQUEST",
                    "method": request.method,
                    "url": request.url,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                })

        def on_response(response):
            if SOAP_URL in response.url:
                try:
                    body = response.text()
                    captured.append({
                        "type": "RESPONSE",
                        "url": response.url,
                        "status": response.status,
                        "body": body[:3000],
                    })
                except:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # Login
        print("Logging in...")
        page.goto("https://myflightscope.com", timeout=60000, wait_until="networkidle")
        page.click("text=LOGIN", timeout=10000)
        page.wait_for_selector("input[type='email']", timeout=15000)
        page.fill("input[type='email']", EMAIL)
        page.fill("input[type='password']", PASSWORD)
        page.click("button:has-text('LOG IN')")

        try:
            page.wait_for_url(lambda url: "login" not in url.lower(), timeout=20000)
        except:
            pass
        time.sleep(5)

        # Navigate to DATA section to trigger more API calls
        print("Navigating to DATA section...")
        try:
            page.click("text=DATA", timeout=5000)
            time.sleep(3)
        except:
            print("Could not click DATA menu")

        print(f"\nCaptured {len(captured)} SOAP interactions:")
        for item in captured:
            if item["type"] == "REQUEST":
                print(f"\n[REQUEST] {item['method']} {item['url']}")
                if item["post_data"]:
                    print(f"  POST DATA: {item['post_data'][:500]}")
            else:
                print(f"\n[RESPONSE] Status {item['status']} - {item['url']}")
                print(f"  BODY: {item['body'][:500]}")

        with open("api_interactions.json", "w") as f:
            json.dump(captured, f, indent=2)
        print("\nSaved to api_interactions.json")

        browser.close()

if __name__ == "__main__":
    main()
