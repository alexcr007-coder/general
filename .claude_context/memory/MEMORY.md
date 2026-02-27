# Project Memory

## User Preferences
- Build context as we go — update memory after every meaningful discovery
- User is not technical — explain things plainly
- User wants some sass/personality in responses

## Active Project: MyFlightScope Data Access

See detailed notes: [flightscope.md](./flightscope.md)

### Quick Summary
- Goal: Pull shot/session data from myflightscope.com into usable format
- Status: Login ✅, Session listing ✅, **Shot data API SOLVED ✅**
- Key methods: `GetSessionLite` (get ResultIDs) → `GetSessionResultData` (get shot data)
- **COMPLETE**: 14,597 shots across 119 sessions saved to shots_all.csv (5.7MB) and shots_all.json (149MB)
- Next step: TBD — analysis, visualization, or further data work
