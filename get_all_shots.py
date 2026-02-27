"""
Use the discovered API to fetch all sessions and all shot data.
"""
import os
import json
import xml.etree.ElementTree as ET
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import requests as req_lib

load_dotenv(os.path.expanduser("~/.config/flightscope/.env"))
EMAIL = os.getenv("FLIGHTSCOPE_EMAIL")
PASSWORD = os.getenv("FLIGHTSCOPE_PASSWORD")

SOAP_URL = "https://myflightscope.com/wp-content/plugins/fs-soap-frame/public/index.php"
PLAYER_ID = "573120"

def get_session_cookies():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

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
        browser.close()
    return cookies

def soap_post(session, method, extra_params=None):
    data = {"method": method}
    if extra_params:
        data.update(extra_params)
    resp = session.post(SOAP_URL, data=data)
    return resp.text

def parse_xml_to_dict(xml_text):
    """Best-effort XML to list-of-dicts converter."""
    try:
        root = ET.fromstring(xml_text)
        results = []
        for child in root:
            row = {}
            for field in child:
                row[field.tag] = field.text
            if row:
                results.append(row)
        return results
    except Exception as e:
        return [{"error": str(e), "raw": xml_text[:200]}]

def main():
    print("Step 1: Logging in to get session cookies...")
    cookies_list = get_session_cookies()

    session = req_lib.Session()
    for c in cookies_list:
        session.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Referer": "https://myflightscope.com/",
        "Origin": "https://myflightscope.com",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    })

    print("\nStep 2: Fetching all sessions...")
    xml = soap_post(session, "listSessionsWithScoreForPlayerAndFilter", {
        "playerID": PLAYER_ID,
        "filterApp": "All",
        "filterStartDate": "2012-01-01",
        "filterEndDate": "2026-12-31",
        "startIndex": "0",
        "count": "100",  # get up to 100 sessions
    })
    with open("all_sessions.xml", "w") as f:
        f.write(xml)

    sessions = parse_xml_to_dict(xml)
    print(f"Found {len(sessions)} sessions")
    for s in sessions[:5]:
        print(f"  [{s.get('sessionID')}] {s.get('sessionCreateDate')} - {s.get('sessionDisplayName')}")

    # Step 3: Try different method names to get shot data
    if sessions:
        session_id = sessions[0].get("sessionID")
        print(f"\nStep 3: Fetching shots for session {session_id}...")

        # Try several possible method names
        methods_to_try = [
            ("getSessionShots", {"sessionID": session_id}),
            ("getShotsForSession", {"sessionID": session_id}),
            ("getShots", {"sessionID": session_id}),
            ("getShotList", {"sessionID": session_id}),
            ("listShotsForSession", {"sessionID": session_id, "playerID": PLAYER_ID}),
            ("getSessionData", {"sessionID": session_id}),
            ("getFullSession", {"sessionID": session_id}),
        ]

        for method_name, params in methods_to_try:
            resp = soap_post(session, method_name, params)
            if len(resp) > 10 and "<error>" not in resp.lower() and "0 results" not in resp:
                print(f"\n  [SUCCESS] Method '{method_name}' returned data:")
                print(f"  {resp[:400]}")
                with open(f"shots_{method_name}.xml", "w") as f:
                    f.write(resp)
                break
            else:
                print(f"  [SKIP] {method_name}: {resp[:80]}")

if __name__ == "__main__":
    main()
