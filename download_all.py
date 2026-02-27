"""
Download all sessions and all shot data from myflightscope.com.
Saves results to: shots_all.json, shots_all.csv, sessions.json
"""
import os, json, time, csv, xml.etree.ElementTree as ET
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import requests

load_dotenv(os.path.expanduser("~/.config/flightscope/.env"))
EMAIL = os.getenv("FLIGHTSCOPE_EMAIL")
PASSWORD = os.getenv("FLIGHTSCOPE_PASSWORD")

SOAP_URL = "https://myflightscope.com/wp-content/plugins/fs-soap-frame/public/index.php"
USER_ID = "573120"
PLAYER_ID = "573120"


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_cookies():
    """Log in via browser and return session cookies."""
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


def make_session(cookies_list):
    """Build a requests.Session with the browser cookies."""
    s = requests.Session()
    for c in cookies_list:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Referer": "https://myflightscope.com/",
        "Origin": "https://myflightscope.com",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


def api_post(s, params):
    resp = s.post(SOAP_URL, data=params)
    resp.raise_for_status()
    return resp.text


# ── Session list ──────────────────────────────────────────────────────────────

def get_all_sessions(s):
    """Fetch all sessions via paginated listSessionsWithScoreForPlayerAndFilter."""
    all_sessions = []
    batch = 100
    start = 0
    while True:
        xml_text = api_post(s, {
            "playerID": PLAYER_ID,
            "filterApp": "All",
            "filterStartDate": "2012-01-01",
            "filterEndDate": "2030-12-31",
            "startIndex": str(start),
            "count": str(batch),
            "method": "listSessionsWithScoreForPlayerAndFilter",
        })
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            print(f"  XML parse error at index {start}: {e}")
            break

        sessions = root.findall("Session")
        if not sessions:
            break

        for sess in sessions:
            all_sessions.append({
                "sessionID":     sess.findtext("sessionID"),
                "displayName":   sess.findtext("sessionDisplayName"),
                "createDate":    sess.findtext("sessionCreateDate"),
                "appVersion":    sess.findtext("appVersion"),
                "location":      sess.findtext("sessionLocation") or "",
                "sessionTypeID": sess.findtext("sessionTypeID"),
            })

        print(f"  Sessions {start}–{start + len(sessions) - 1} fetched.")
        if len(sessions) < batch:
            break
        start += batch
        time.sleep(0.5)

    return all_sessions


# ── Shot data ─────────────────────────────────────────────────────────────────

def _unwrap_response(text):
    """Strip the <Response>…</Response> XML wrapper and parse as JSON."""
    text = text.strip()
    if text.startswith("<Response>") and text.endswith("</Response>"):
        return json.loads(text[len("<Response>"):-len("</Response>")])
    # Sometimes the API returns raw JSON without wrapper
    return json.loads(text)


def get_session_result_ids(s, session_id):
    """Return list of ResultIDs for a session via GetSessionLite."""
    text = api_post(s, {
        "method":    "GetSessionLite",
        "UserID":    USER_ID,
        "SessionID": session_id,
        "ShareID":   "",
    })
    try:
        data = _unwrap_response(text)
        return [r["ResultID"] for r in data.get("ResultsRange", [])]
    except Exception as e:
        print(f"    GetSessionLite parse error: {e}")
        return []


def get_shots_for_session(s, session_id, result_ids):
    """
    Fetch shot data for a session.
    Tries one bulk call first; falls back to per-ResultID calls if needed.
    Returns a list of shot dicts.
    """
    if not result_ids:
        return []

    # Bulk call: start from first ResultID, ask for all of them
    try:
        text = api_post(s, {
            "method":            "GetSessionResultData",
            "UserID":            USER_ID,
            "SessionID":         session_id,
            "StartResultID":     result_ids[0],
            "Limit":             str(len(result_ids) + 10),
            "ForcedSurfaceType": "",
            "ShareID":           "",
        })
        data = _unwrap_response(text)
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception as e:
        print(f"    Bulk GetSessionResultData failed: {e}. Falling back to per-shot calls.")

    # Fallback: one call per ResultID
    shots = []
    for rid in result_ids:
        try:
            text = api_post(s, {
                "method":            "GetSessionResultData",
                "UserID":            USER_ID,
                "SessionID":         session_id,
                "StartResultID":     rid,
                "Limit":             "1",
                "ForcedSurfaceType": "",
                "ShareID":           "",
            })
            data = _unwrap_response(text)
            if isinstance(data, list) and data:
                shots.append(data[0])
        except Exception as e:
            print(f"    Shot {rid} error: {e}")
        time.sleep(0.1)

    return shots


# ── Flatten ───────────────────────────────────────────────────────────────────

def _p(params, key):
    """Pull a _PARAMETER_STRING value, return empty string if missing."""
    return params.get(key + "_PARAMETER_STRING", "") or ""


def flatten_shot(shot, sess_info):
    """Convert a raw shot dict + session info into a flat CSV-ready row."""
    params  = shot.get("ResultParameters", {}) or {}
    weather = shot.get("WeatherData", {}) or {}
    swing   = shot.get("GolfSwingParameters", {}) or {}

    return {
        # Session
        "session_id":              sess_info["sessionID"],
        "session_name":            sess_info["displayName"],
        "session_date":            sess_info["createDate"],
        "app_version":             sess_info["appVersion"],
        "session_location":        sess_info["location"],
        # Shot identity
        "result_id":               shot.get("ResultID", ""),
        "swing_index":             shot.get("SwingIndex", ""),
        "shot_datetime":           shot.get("ShotDateTime", ""),
        "club_id":                 shot.get("ClubID", ""),
        "club_type_id":            shot.get("ClubTypeID", ""),
        "is_invalid":              shot.get("IsInvalid", ""),
        "is_deleted":              shot.get("IsDeleted", ""),
        "result_type":             shot.get("ResultType", ""),
        # Shot classification
        "shot_classification":     swing.get("SHOTCLASSIFICATION_PARAMETER_STRING", ""),
        "detection_mode":          swing.get("DETECTION_MODE_PARAMETER_STRING", ""),
        "radar_type":              swing.get("RADARCAMERATYPE", ""),
        "range_ball":              swing.get("RANGEBALL", ""),
        # Distances
        "carry_dist_yards":        _p(params, "CARRYDIST"),
        "total_dist_yards":        _p(params, "TOTALDIST"),
        "roll_dist_yards":         _p(params, "ROLLDIST"),
        "lateral_yards":           _p(params, "LATERAL"),
        "curve_dist_yards":        _p(params, "CURVEDIST"),
        "height_yards":            _p(params, "HEIGHT"),
        "flight_time_sec":         _p(params, "FLIGHTTIME"),
        # Speed & power
        "ball_speed_ms":           _p(params, "LAUNCHSPEED"),
        "club_head_speed_ms":      _p(params, "CLUBHEADSPEED"),
        "club_head_speed_post_ms": _p(params, "CLUBHEADSPEEDPOST"),
        "smash_factor":            _p(params, "SMASH"),
        # Launch
        "launch_angle_deg":        _p(params, "LAUNCHELEV"),
        "launch_direction_deg":    _p(params, "LAUNCHAZIM"),
        # Spin
        "backspin_rpm":            _p(params, "BACKSPIN"),
        "sidespin_rpm":            _p(params, "SIDESPIN"),
        "total_spin_rpm":          _p(params, "SPIN"),
        "spin_is_estimate":        params.get("SPIN_IS_ESTIMATE", ""),
        "spin_axis_deg":           _p(params, "SPINAXIS"),
        "spin_loft_deg":           _p(params, "SPINLOFT"),
        # Club / impact
        "face_angle_deg":          _p(params, "CLUBFACEANGLE"),
        "face_to_path_deg":        _p(params, "FACETOPATH"),
        "effective_loft_deg":      _p(params, "EFFECTIVELOFT"),
        "swing_plane_tilt_deg":    _p(params, "SWINGPLANETILT"),
        "swing_plane_rotation_deg":_p(params, "SWINGPLANEROTATION"),
        "club_strike_dir_deg":     _p(params, "CLUBSTRIKEDIR"),
        "club_strike_dir_vert_deg":_p(params, "CLUBSTRIKEDIRVERT"),
        "impact_elev_deg":         _p(params, "IMPACTELEV"),
        "fusion_impact_lateral":   params.get("FusionImpactLocationLateral", ""),
        "fusion_impact_vertical":  params.get("FusionImpactLocationVertical", ""),
        "club_low_point":          params.get("CLUB_LOW_POINT", ""),
        # Weather
        "weather_temperature_c":   weather.get("WEATHER_TEMPERATURE", ""),
        "weather_humidity_pct":    weather.get("WEATHER_HUMIDITY", ""),
        "weather_pressure_atm":    weather.get("WEATHER_PRESSURE", ""),
        "weather_wind_speed_ms":   weather.get("WEATHER_WIND_SPEED", ""),
        "weather_wind_dir_deg":    weather.get("WEATHER_WIND_DIRECTION_ANGLE", ""),
        "gps_latitude":            weather.get("LATITUDE", ""),
        "gps_longitude":           weather.get("LONGITUDE", ""),
        "altitude_m":              weather.get("ALTITUDE", ""),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  FlightScope Full Data Download")
    print("=" * 60)

    # Step 1: Login
    print("\n[1/4] Logging in...")
    cookies = get_cookies()
    s = make_session(cookies)
    print("      Done.\n")

    # Step 2: All sessions
    print("[2/4] Fetching all sessions...")
    sessions = get_all_sessions(s)
    print(f"      {len(sessions)} sessions found.\n")

    with open("sessions.json", "w") as f:
        json.dump(sessions, f, indent=2)
    print("      Saved sessions.json\n")

    # Step 3: All shots
    print("[3/4] Fetching shot data for every session...")
    all_shots_raw  = []
    all_shots_flat = []
    skipped = 0

    for i, sess in enumerate(sessions):
        sid  = sess["sessionID"]
        name = sess["displayName"]
        date = sess["createDate"][:10]
        print(f"  [{i+1:>3}/{len(sessions)}] {sid}  {date}  {name}")

        result_ids = get_session_result_ids(s, sid)
        if not result_ids:
            print(f"           → 0 results, skipping.")
            skipped += 1
            time.sleep(0.2)
            continue

        shots = get_shots_for_session(s, sid, result_ids)
        if not shots:
            print(f"           → 0 shots returned, skipping.")
            skipped += 1
            time.sleep(0.2)
            continue

        print(f"           → {len(shots)} shots ✓")
        for shot in shots:
            all_shots_raw.append(shot)
            all_shots_flat.append(flatten_shot(shot, sess))

        time.sleep(0.3)

    print(f"\n      Total shots: {len(all_shots_raw)}  |  Sessions skipped: {skipped}\n")

    # Step 4: Save
    print("[4/4] Saving output files...")

    with open("shots_all.json", "w") as f:
        json.dump(all_shots_raw, f, indent=2)
    print("      Saved shots_all.json")

    if all_shots_flat:
        fieldnames = list(all_shots_flat[0].keys())
        with open("shots_all.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_shots_flat)
        print("      Saved shots_all.csv")

    print("\n" + "=" * 60)
    print(f"  Done! {len(all_shots_raw)} shots across {len(sessions) - skipped} sessions.")
    print("=" * 60)


if __name__ == "__main__":
    main()
