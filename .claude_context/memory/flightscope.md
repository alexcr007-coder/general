# FlightScope Project Notes

## Credentials & Account
- Email: hectorchavez007@hotmail.com
- Password: scorpion11
- Stored in: ~/.config/flightscope/.env
- Player ID: 573120
- Account created: 2024-08-26
- Total shots ever measured: 14,400

## Environment
- Python virtual env: ~/flightscope_env/ (Python 3.11)
- Scripts directory: ~/flightscope/
- Activate venv: source ~/flightscope_env/bin/activate

## API Details
- SOAP-style API endpoint: https://myflightscope.com/wp-content/plugins/fs-soap-frame/public/index.php
- Authentication: Browser login via Playwright, extract cookies, use in requests.Session
- All API calls are POST with form-encoded body (method= is the key param)

## Known Working API Methods
| Method | Key Params | Returns |
|--------|-----------|---------|
| getTotalStatsForPlayer | PlayerID | Total shots measured, distance tracked |
| getDashboardStatsForPlayer | PlayerID | Dashboard stats (all zeros for this account) |
| getDrivingStatsForPlayer | PlayerID, timeScope=0 | Driving stats |
| getApproachStatsForPlayer | PlayerID, timeScope=0 | Approach stats |
| getTemplateLeaderBoard | templateID=3162, filterString=1, startIndex, count | Global leaderboard |
| listSessionsWithScoreForPlayerAndFilter | playerID, filterApp=All, filterStartDate, filterEndDate, startIndex, count | Session list |
| getUserProfile | UserID | User profile info |

## Session Data
- Total sessions: 119
- Most recent: "Tuesday, 02:40 PM" (2026-02-24), sessionID=9149941, iOS_FS Golf_9.5.0
- Sessions XML saved to: ~/flightscope/all_sessions.xml

## Scripts in ~/flightscope/
| File | Purpose | Status |
|------|---------|--------|
| screenshot_login.py | Screenshot login page to understand UI | Done (exploratory) |
| explore_login.py | First login attempt, capture API calls | Done (exploratory) |
| fetch_data.py | Login + capture all API responses | Done, produced api_responses.json |
| intercept_api.py | Login + intercept SOAP calls on dashboard | Done, produced api_interactions.json |
| intercept_session.py | Login + navigate to DATA > click session | Done, produced session_api_calls.json — but "View" click failed |
| get_shots.py | Login + fetch shots via getSessions/getShots GET | Partial — sessions_raw.xml is empty (wrong method) |
| get_all_shots.py | Login + list all sessions + try multiple shot methods | Partial — all_sessions.xml works, shot methods all failed |

## *** SOLVED: Shot Data API ***

### Session page URL (triggers the right API calls)
Navigate to: `https://myflightscope.com/app/sessions/{sessionID}`
Redirects to: `/app/session/PocketAppLesson/{sessionID}/result/{resultID}/`

### Step 1 — GetSessionLite
```
POST method=GetSessionLite&UserID=573120&SessionID={sid}&ShareID=
```
Returns: Session metadata + `ResultsRange` = list of ALL shot ResultIDs in the session
```json
"ResultsRange": [{"ResultID": "253965466", "ClubID": "115013403", "BallID": "91307764", ...}, ...]
```

### Step 2 — GetSessionResultData (actual shot data)
```
POST method=GetSessionResultData&UserID=573120&SessionID={sid}&StartResultID={first_result_id}&Limit=1&ForcedSurfaceType=&ShareID=
```
Returns: JSON inside `<Response>` tags with complete shot data per shot.

### Shot data fields available (per shot)
- `IsInvalid`, `IsDeleted`, `ShotDateTime`, `ResultTypeID`, `ResultType`
- `GolfSwingID`, `ResultID`, `PlayerID`, `ClubID`, `SwingIndex` (shot number), `ClubTypeID`
- `WeatherData`: altitude, lat/lng, temperature, humidity, pressure, wind speed/direction
- `GolfSwingParameters`: detection mode (Indoor/Outdoor), shot classification (fade/draw/straight), radar type (Fusion), GUID
- `ResultParameters` — full ballistics:
  - `CARRYDIST_PARAMETER_STRING` (e.g. 127.889 yards)
  - `TOTALDIST_PARAMETER_STRING` (e.g. 129.789 yards)
  - `LAUNCHSPEED_PARAMETER_STRING` (ball speed, e.g. 45.97 m/s)
  - `CLUBHEADSPEED_PARAMETER_STRING` (e.g. 35.54 m/s)
  - `SMASH_PARAMETER_STRING` (smash factor, e.g. 1.29)
  - `LAUNCHELEV_PARAMETER_STRING` (launch angle, e.g. 18.07°)
  - `LAUNCHAZIM_PARAMETER_STRING` (launch direction, e.g. 1.18°)
  - `BACKSPIN_PARAMETER_STRING` (e.g. 5607 rpm)
  - `SIDESPIN_PARAMETER_STRING` (e.g. 1013 rpm)
  - `SPIN_PARAMETER_STRING`, `SPINAXIS_PARAMETER_STRING`, `SPINLOFT_PARAMETER_STRING`
  - `CLUBFACEANGLE_PARAMETER_STRING`, `FACETOPATH_PARAMETER_STRING`
  - `EFFECTIVELOFT_PARAMETER_STRING`, `SWINGPLANETILT_PARAMETER_STRING`
  - `HEIGHT_PARAMETER_STRING` (apex, yards)
  - `LATERAL_PARAMETER_STRING` (offline distance)
  - `FLIGHTTIME_PARAMETER_STRING`, `ROLLDIST_PARAMETER_STRING`
  - `SHOTCLASSIFICATION_PARAMETER_STRING` (fade/draw/straight/etc.)
  - `CURVEDIST_PARAMETER_STRING`
- `RollModel`: full ball trajectory with time-series `BounceRoll` positions

### Pagination
- `GetSessionLite` gives you ALL ResultIDs upfront (in `ResultsRange`)
- `GetSessionResultData` with high `Limit` (e.g. 1000) should return all shots at once
- Or iterate per ResultID

### Site tech stack
- Angular SPA (`ng-app="app"`) + Vuetify
- Session links on dashboard: `https://myflightscope.com/fs-golf/#mfsSessionID={sessionID}`
- Angular routing: `https://myflightscope.com/app/sessions/{sessionID}` → works for navigation

## Output Files in ~/flightscope/
- **shots_all.csv** — 5.7MB, 14,597 shots, all sessions, all fields (ready for Excel/Sheets)
- **shots_all.json** — 149MB, full raw shot data with trajectory arrays
- **sessions.json** — 25KB, all 119 sessions metadata
- download_all.py — the script that downloads everything (run from ~/flightscope/ with venv active)
- all_sessions.xml — raw session list from earlier exploration
- api_interactions.json, session_api_calls.json, session_api_calls_v2.json — API intercept logs
- Various .png screenshots from early exploration

## Running the download script
```bash
cd ~/flightscope
source ../flightscope_env/bin/activate
python download_all.py
```
