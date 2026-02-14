# SMS Flood Risk Assistant — Philippines

An SMS-based early warning service that resolves Philippine barangay/city locations to coordinates and provides flood risk assessments, prep checklists, and actionable guidance — all over SMS.

---

## How It Works

1. **User texts a location** (e.g. `Brgy Lahug, Cebu City`)
2. **System resolves coordinates** using a 3-tier geocoding chain (never fails)
3. **System replies** with confirmed coordinates + a command menu
4. **User picks a command** (`1`-`4`, `WHY`, `LOC`, `STOP`) to get risk info

---

## File Structure

```
scaling-octo-eureka/
├── app.py                  # Flask entry point — /sms webhook, /health check
├── intent_parser.py        # Parses SMS: location → coords, or command → action
├── geocoder.py             # 3-tier geocoding: cache → Nominatim → OpenCage → fallback
├── locations_cache.json    # Auto-growing cache of resolved {location: {lat, lon}}
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── idea.txt                # Original project spec/brainstorm
└── README.md               # This file
```

---

## Geocoding Architecture

The geocoder **always returns coordinates** — it degrades gracefully, never errors out.

```
User sends location
        │
        ▼
┌─────────────────┐
│  Local Cache     │ ── Hit ──→ Return cached coords (instant, free)
│  (JSON file)     │
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────┐
│  Tier 1:         │ ── Success ──→ Cache result + return
│  Nominatim/OSM   │    (free, no key, 1 req/sec)
└────────┬────────┘
         │ Fail/Timeout
         ▼
┌─────────────────┐
│  Tier 2:         │ ── Success ──→ Cache result + return
│  OpenCage        │    (free tier, needs API key)
└────────┬────────┘
         │ Fail/No key
         ▼
┌─────────────────┐
│  Tier 3:         │ ── Always succeeds
│  Closest Match   │    (fuzzy match against cache keys via difflib)
│  Fallback        │    Returns approximate=True + matched_to field
└─────────────────┘
```

- **Cache**: `locations_cache.json` — pre-seeded with ~27 flood-prone PH barangays/cities, auto-grows on every successful API resolve
- **Nominatim**: Free OSM geocoder, good PH coverage for cities and many barangays
- **OpenCage**: Free 2,500 req/day tier, catches Nominatim misses (optional, needs `OPENCAGE_API_KEY`)
- **Fallback**: `difflib.get_close_matches()` against cache keys — typo-tolerant. Absolute last resort = Manila

---

## Command Menu

After location is set, users can text:

| Command | Description |
|---------|-------------|
| `1` or `FLOOD` | Risk assessment |
| `2` or `PREP` | Home prep checklist |
| `3` or `TRAVEL` | Travel safety |
| `4` or `FARM` | Farmer guidance |
| `WHY` | Explain risk calculation |
| `LOC` | Update location (send new location next) |
| `STOP` | Unsubscribe from alerts |

---

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy env template and fill in your keys
cp .env.example .env

# 3. Run the server
python app.py
```

The server starts on port 5000 by default. Point your Twilio SMS webhook to `https://your-domain/sms`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TWILIO_ACCOUNT_SID` | Yes | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Yes | Your Twilio phone number |
| `OPENCAGE_API_KEY` | No | OpenCage API key (Tier 2 geocoder backup) |
| `FLASK_DEBUG` | No | Set to `1` for development |
