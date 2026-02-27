"""
Navigate into a session page and capture all SOAP API calls made to load shot data.
Fixed: site is an Angular SPA — navigate via URL directly using known session IDs.
"""
import os, json, time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(os.path.expanduser("~/.config/flightscope/.env"))
EMAIL = os.getenv("FLIGHTSCOPE_EMAIL")
PASSWORD = os.getenv("FLIGHTSCOPE_PASSWORD")
SOAP_URL = "https://myflightscope.com/wp-content/plugins/fs-soap-frame/public/index.php"

# Known session IDs from all_sessions.xml (most recent first)
KNOWN_SESSION_IDS = ["9149941", "9112535", "9117036", "9095402"]

# Angular SPA route patterns to try for a session detail page
SESSION_URL_PATTERNS = [
    "https://myflightscope.com/app/sessions/{sid}",
    "https://myflightscope.com/app/data/sessions/{sid}",
    "https://myflightscope.com/app/#/sessions/{sid}",
    "https://myflightscope.com/#/sessions/{sid}",
    "https://myflightscope.com/app/session/{sid}",
]

captured = []

def on_request(request):
    if SOAP_URL in request.url:
        captured.append({
            "type": "REQUEST",
            "method": request.method,
            "url": request.url,
            "post_data": request.post_data,
        })

def on_response(response):
    if SOAP_URL in response.url:
        try:
            captured.append({
                "type": "RESPONSE",
                "url": response.url,
                "status": response.status,
                "body": response.text()[:5000],
            })
        except:
            pass

def login(page):
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
    print(f"Logged in. Current URL: {page.url}")

def dump_page_links(page, label):
    """Print all links and buttons on the current page for debugging."""
    items = page.evaluate("""() => {
        const results = [];
        document.querySelectorAll('a, button, [ng-click], [v-on\\\\:click]').forEach(el => {
            const text = el.innerText.trim().substring(0, 60);
            const href = el.href || el.getAttribute('ng-click') || el.getAttribute('@click') || '';
            if (text) results.push({tag: el.tagName, text, href});
        });
        return results;
    }""")
    print(f"\n--- {label} ({len(items)} items) ---")
    for item in items[:40]:
        print(f"  <{item['tag']}> [{item['text']}] {item['href']}")

def try_navigate_to_session(page, session_id):
    """Try each URL pattern for a session and return True if we land on a session page."""
    for pattern in SESSION_URL_PATTERNS:
        url = pattern.format(sid=session_id)
        print(f"  Trying: {url}")
        try:
            page.goto(url, timeout=15000, wait_until="networkidle")
            time.sleep(4)
            current = page.url
            title = page.title()
            print(f"  -> URL: {current} | Title: {title}")
            # Check if new SOAP requests fired (means we hit a real page)
            if len(captured) > 0 and any(
                session_id in str(item.get("post_data", "")) or
                session_id in str(item.get("body", ""))
                for item in captured
            ):
                print(f"  -> SESSION DATA DETECTED for {session_id}!")
                return True
        except Exception as e:
            print(f"  -> Error: {e}")
    return False

def try_click_into_session(page):
    """After landing on the DATA/Sessions list, find and click a session row."""
    print("\nLooking for session rows to click...")
    page.screenshot(path="debug_sessions_list.png", full_page=True)

    # Dump page to understand structure
    dump_page_links(page, "Sessions list page")

    # Try clicking anything that looks like a session entry
    selectors_to_try = [
        "button:has-text('VIEW')",
        "button:has-text('View')",
        "a:has-text('VIEW')",
        "a:has-text('View')",
        ".session-row",
        "tr.clickable",
        "[class*='session'] button",
        "[class*='session'] a",
        "td button",
        "tbody tr:first-child button",
        "tbody tr:first-child a",
        ".v-list-item",
        ".v-btn:has-text('VIEW')",
    ]
    for sel in selectors_to_try:
        try:
            el = page.query_selector(sel)
            if el:
                print(f"  Found element with selector: {sel}")
                el.click()
                time.sleep(5)
                page.screenshot(path="debug_after_session_click.png", full_page=True)
                print(f"  After click URL: {page.url}")
                return True
        except Exception as e:
            pass

    print("  No session row found to click.")
    return False

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        page.on("request", on_request)
        page.on("response", on_response)

        login(page)
        page.screenshot(path="debug_dashboard.png")
        dump_page_links(page, "Dashboard")

        # --- Strategy 1: Direct URL navigation with known session IDs ---
        print("\n=== Strategy 1: Direct URL navigation ===")
        found = False
        for sid in KNOWN_SESSION_IDS:
            if try_navigate_to_session(page, sid):
                found = True
                break

        if not found:
            # --- Strategy 2: Navigate to sessions list, then click in ---
            print("\n=== Strategy 2: Navigate to DATA > Sessions, then click ===")
            # Go back to dashboard
            page.goto("https://myflightscope.com", timeout=60000, wait_until="networkidle")
            time.sleep(3)

            # Try clicking DATA menu
            try:
                page.click("text=DATA", timeout=8000)
                time.sleep(3)
                print(f"After DATA click URL: {page.url}")
                page.screenshot(path="debug_data_section.png")

                # Try hovering to reveal submenu
                try:
                    page.hover("text=Sessions", timeout=3000)
                    time.sleep(1)
                    page.click("text=Sessions", timeout=3000)
                    time.sleep(3)
                    print(f"After Sessions click URL: {page.url}")
                except:
                    pass

                try_click_into_session(page)
            except Exception as e:
                print(f"Strategy 2 failed: {e}")

        # --- Print results ---
        print(f"\n\n=== Captured {len(captured)} SOAP interactions ===")
        shot_methods = []
        for item in captured:
            if item["type"] == "REQUEST" and item.get("post_data"):
                print(f"\n[REQUEST POST] {item['post_data']}")
                if "method=" in (item.get("post_data") or ""):
                    method = item["post_data"].split("method=")[-1].split("&")[0]
                    if method not in ["getTotalStatsForPlayer", "getDashboardStatsForPlayer",
                                      "listSessionsWithScoreForPlayerAndFilter", "getUserProfile",
                                      "getTemplateLeaderBoard", "getDrivingStatsForPlayer",
                                      "getApproachStatsForPlayer"]:
                        shot_methods.append(item["post_data"])
            elif item["type"] == "RESPONSE":
                print(f"[RESPONSE] status={item['status']} body={item['body'][:200]}")

        if shot_methods:
            print("\n\n*** NEW/UNKNOWN API METHODS FOUND (likely shot data): ***")
            for m in shot_methods:
                print(f"  {m}")
        else:
            print("\n*** No new API methods found beyond the known dashboard ones ***")

        with open("session_api_calls_v2.json", "w") as f:
            json.dump(captured, f, indent=2)
        print("\nSaved to session_api_calls_v2.json")

        browser.close()

if __name__ == "__main__":
    main()
