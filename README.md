# SMS Flood Risk Assistant — Philippines

An SMS-based early warning service that resolves Philippine barangay/city locations to coordinates and provides flood risk assessments, prep checklists, and actionable guidance — all over SMS.

---

## How It Works

1. **User texts a location** (e.g. `Marikina` or `Brgy Lahug, Cebu City`)
2. **Parser resolves coordinates** using a 3-tier geocoding chain (never fails)
3. **Pipeline fetches live data** (PAGASA rainfall, Open-Meteo forecast, MGB susceptibility)
4. **Risk engine scores** `susceptibility × rain_trigger → tier` (SAFE / WATCH / WARNING / CRITICAL)
5. **System replies** with risk assessment + actionable steps via SMS
6. **User picks a command** (`1`-`4`, `WHY`, `LOC`, `STOP`, or word aliases) for follow-up info

---

## File Structure

```
scaling-octo-eureka/
├── app.py                      # Flask entry point — /sms Twilio webhook, /health check
├── pipeline.py                 # Pipeline orchestrator — assess(), handle_menu(), is_menu_command()
├── parser/
│   ├── __init__.py             # Exports resolve_location, normalize_location
│   ├── intent_parser.py        # SMS text → (lat, lon, name) via normalize + geocode
│   ├── geocoder.py             # 3-tier geocoding: cache → Nominatim → OpenCage → fallback
│   └── locations_cache.json    # Auto-growing cache of resolved {location: {lat, lon}}
├── data/
│   ├── __init__.py
│   ├── pagasa.py               # PAGASA Rainfall Forecast (portal.georisk.gov.ph)
│   ├── susceptibility.py       # MGB Flood Susceptibility (controlmap.mgb.gov.ph)
│   └── weather.py              # Open-Meteo hourly forecast (api.open-meteo.com)
├── risk/
│   ├── __init__.py
│   ├── engine.py               # Risk scoring: susceptibility × rain_trigger → tier
│   └── response.py             # SMS response formatters (all menu commands + errors)
├── sms/
│   └── __init__.py             # Reserved for future Twilio helpers
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py        # Full test harness (offline + live API + demo)
├── requirements.txt            # flask, requests, python-dotenv, twilio
├── .env.example                # TWILIO_*, OPENCAGE_API_KEY
├── idea.txt                    # Original project spec/brainstorm
├── progress.md                 # Progress tracker with architecture overview
└── README.md                   # This file
```

---

## Architecture Flow

```
User texts location (e.g. "Marikina")
  → [app.py] Twilio webhook receives POST, reads Body + From
    → [pipeline] is_menu_command(text)?
      → YES (1-4, flood, prep, travel, farm, why, loc, stop):
          handle_menu(cmd, stored_assessment, location)
      → NO: treat as location
        → [parser/] resolve_location(text) → (lat, lon, name)
          → [pipeline] assess(lat, lon, name)
            → [data/] PAGASA rain + MGB susceptibility + Open-Meteo
              → [risk/] score = susceptibility × rain_trigger → tier
                → [risk/] format SMS (danger mode or safe mode + menu)
  → TwiML response → Twilio → SMS reply to user
```

---

## Command Menu

After location is set, users can text:

| Command | Aliases | Description |
|---------|---------|-------------|
| `1` | `FLOOD` | Risk assessment |
| `2` | `PREP` | Home prep checklist |
| `3` | `TRAVEL` | Travel safety |
| `4` | `FARM` | Farmer guidance |
| `WHY` | | Explain risk calculation |
| `5` | `LOC` | Update location (send new location next) |
| `STOP` | | Unsubscribe from alerts |

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
