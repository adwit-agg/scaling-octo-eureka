---
name: Intent Parser Module
overview: Location-first SMS intent parser — user sends a Philippine barangay/city name, system resolves to coordinates via 3-tier geocoding (cache → Nominatim → OpenCage → closest-match fallback), and returns coordinates + a command menu.
todos:
  - id: scaffold
    content: "Scaffold project: requirements.txt, .env.example"
    status: completed
  - id: seed-cache
    content: Pre-seed locations_cache.json with ~27 flood-prone PH barangays/cities
    status: completed
  - id: geocoder
    content: "Implement geocoder.py: cache → Nominatim → OpenCage → closest-match fallback (always returns coords)"
    status: completed
  - id: intent-parser
    content: "Implement intent_parser.py: location-first parsing, normalize location, resolve coords, detect command keywords"
    status: completed
  - id: wire-app
    content: Wire intent_parser into app.py Flask /sms POST route with TwiML responses
    status: completed
  - id: update-readme
    content: Update README.md with file structure and geocoding architecture
    status: completed
isProject: false
---

# Intent Parser + Philippine Geocoding Module

## Context

SMS Flood Risk Assistant for the Philippines. Users text a location, system resolves it to coordinates at the barangay level, and presents a command menu for risk assessment, prep checklists, travel safety, and farmer guidance.

## Simplified Flow (Location-First)

The original plan parsed `ACTION LOCATION` (e.g. "FLOOD Marikina"). The updated approach is simpler:

1. **User sends just a location** (e.g. "Brgy Lahug, Cebu City")
2. **System resolves coordinates** via 3-tier geocoding chain
3. **System replies** with confirmed coordinates + command menu
4. **User picks a command** from the menu (1-4, WHY, LOC, STOP)

This means the intent parser only needs to distinguish between:

- A **location** (resolve to coords)
- A **command keyword** (return the action type)

### Input / Output

**Location input** → e.g. `"Brgy Lahug, Cebu City"`

```python
{
    "type": "location",
    "location": "brgy lahug, cebu city",
    "coordinates": {"lat": 10.3280, "lon": 123.8990, "source": "cache", "approximate": False},
    "menu": "Reply with:\n  1 - Risk assessment\n  ..."
}
```

**Command input** → e.g. `"1"` or `"flood"`

```python
{
    "type": "command",
    "action": "flood"
}
```

### Available Commands


| Input           | Action | Description              |
| --------------- | ------ | ------------------------ |
| `1` or `FLOOD`  | flood  | Risk assessment          |
| `2` or `PREP`   | prep   | Home prep checklist      |
| `3` or `TRAVEL` | travel | Travel safety            |
| `4` or `FARM`   | farm   | Farmer guidance          |
| `WHY`           | why    | Explain risk calculation |
| `LOC`           | loc    | Update location          |
| `STOP`          | stop   | Unsubscribe              |


---

## Geocoding Strategy: 3-Tier Fallback Chain (Never Fails)

The system resolves Philippine barangays and cities to lat/lon coordinates. It uses a strict fallback chain — if one tier fails, it moves to the next. It **always returns coordinates**.

```
Location string → Cache? → Yes → Return cached coords
                    ↓ No
              Nominatim (Tier 1) → Success → Cache + return
                    ↓ Fail
              OpenCage (Tier 2) → Success → Cache + return
                    ↓ Fail
              Closest Match (Tier 3) → fuzzy difflib match → return (approximate=True)
```

### Local Cache (`locations_cache.json`)

- Pre-seeded with ~27 flood-prone PH barangays/cities
- Auto-grows: every successful API geocode is written back
- Checked first on every call — zero latency for repeat lookups

### Tier 1: Nominatim (OSM) — Free, no key

- Scoped to Philippines (`countrycodes=ph`)
- 5s timeout, 1 req/sec rate limit
- Good coverage for PH cities and many barangays

### Tier 2: OpenCage — Free 2,500/day

- Requires `OPENCAGE_API_KEY` in `.env` (skipped if not set)
- Catches locations Nominatim misses

### Tier 3: Closest Match Fallback — Always succeeds

- `difflib.get_close_matches()` against all cache keys (cutoff=0.5)
- Handles typos: "marikna" → "marikina"
- Absolute last resort: Manila (14.5995, 120.9842)
- Returns `approximate: True` + `matched_to` field

---

## File Structure

```
scaling-octo-eureka/
├── app.py                  # Flask entry point — /sms webhook, /health check
├── intent_parser.py        # Parses SMS: location → coords, or command → action
├── geocoder.py             # 3-tier geocoding: cache → Nominatim → OpenCage → fallback
├── locations_cache.json    # Auto-growing cache of resolved {location: {lat, lon}}
├── requirements.txt        # flask, requests, python-dotenv, twilio
├── .env.example            # TWILIO_*, OPENCAGE_API_KEY
├── idea.txt                # Original project spec
└── README.md               # File structure + architecture docs
```

