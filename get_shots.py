"""
Fetch all sessions and their shot data from myflightscope.com via the SOAP API.
"""
import os
import json
import time
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(os.path.expanduser("~/.config/flightscope/.env"))
EMAIL = os.getenv("FLIGHTSCOPE_EMAIL")
PASSWORD = os.getenv("FLIGHTSCOPE_PASSWORD")

SOAP_URL = "https://myflightscope.com/wp-content/plugins/fs-soap-frame/public/index.php"

def login_and_get_cookies():
    """Log in via browser and return session cookies for direct API calls."""
    cookies = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

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
        time.sleep(3)

        cookies = context.cookies()
        print(f"Got {len(cookies)} cookies after login")
        browser.close()

    return cookies

def soap_request(session, action, params=""):
    """Make a SOAP-style request to the FlightScope API."""
    response = session.get(
        SOAP_URL,
        params={"action": action, **({} if not params else params)}
    )
    return response.text

def main():
    import requests

    # Step 1: Get cookies from browser login
    cookies_list = login_and_get_cookies()

    # Step 2: Use cookies in a requests session
    session = requests.Session()
    for cookie in cookies_list:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain',''))

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Referer": "https://myflightscope.com/",
    }
    session.headers.update(headers)

    # Step 3: Fetch sessions list
    print("\nFetching sessions...")
    resp = session.get(SOAP_URL, params={"action": "getSessions"})
    print(f"Sessions response status: {resp.status_code}")

    sessions_xml = resp.text
    with open("sessions_raw.xml", "w") as f:
        f.write(sessions_xml)
    print("Raw sessions XML saved")

    # Parse sessions
    try:
        root = ET.fromstring(sessions_xml)
        sessions = []
        for s in root.findall("Session"):
            sessions.append({
                "id": s.findtext("sessionID"),
                "name": s.findtext("sessionDisplayName"),
                "date": s.findtext("sessionCreateDate"),
                "app": s.findtext("appVersion"),
            })
        print(f"\nFound {len(sessions)} sessions:")
        for s in sessions:
            print(f"  [{s['id']}] {s['date']} - {s['name']} ({s['app']})")
    except Exception as e:
        print(f"Could not parse sessions XML: {e}")
        print("Raw response:", sessions_xml[:500])
        return

    # Step 4: Fetch shots for the most recent session
    if sessions:
        latest = sessions[0]
        print(f"\nFetching shots for session: {latest['name']} ({latest['date']})...")

        resp = session.get(SOAP_URL, params={
            "action": "getShots",
            "sessionID": latest['id']
        })
        print(f"Shots response status: {resp.status_code}")

        with open("shots_raw.xml", "w") as f:
            f.write(resp.text)
        print("Raw shots XML saved to shots_raw.xml")
        print("\nShots preview:")
        print(resp.text[:1000])

if __name__ == "__main__":
    main()
