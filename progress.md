# Flood Risk SMS Assistant — Progress Tracker

Last updated: 2026-02-14

---

## Architecture Overview

```
User texts location (e.g. "Marikina")
  → [app.py] Twilio webhook receives POST, reads Body + From
    → [pipeline] is_menu_command(text)?
      → YES (1-4, flood, prep, travel, farm, why, loc, stop):
          handle_menu(cmd, stored_assessment, location)
      → NO: treat as location
        → [parser/] resolve_location(text) → {lat, lon, name}
          → [pipeline] assess(lat, lon, name)
            → [data/] PAGASA rain + MGB susceptibility + Open-Meteo
              → [risk/] score = susceptibility × rain_trigger → tier
                → [risk/] format SMS (danger mode or safe mode + menu)
  → TwiML response → Twilio → SMS reply to user
```

---

## Module 1: SMS Gateway (`app.py`)

**Owner:** (teammate 1)
**Status:** DONE

Flask webhook + in-memory session state, wired to parser + pipeline.

- [x] Flask route `POST /sms` that reads Twilio `Body` and `From`
- [x] Use `pipeline.is_menu_command(body)` to check if input is a menu command
  - If YES: call `pipeline.handle_menu(body, sessions[phone]["assessment"], sessions[phone]["name"])`
  - If NO: call `parser.resolve_location(body)` → `pipeline.assess(lat, lon, name)`
- [x] Store last assessment per phone number: `sessions[from_number] = {"assessment": ..., "name": ...}`
- [x] Return TwiML string as `application/xml` response
- [ ] Twilio phone number + ngrok for local dev

**Integration (implemented in `app.py`):**
```python
from pipeline import assess, handle_menu, is_menu_command
from parser.intent_parser import resolve_location

# In webhook handler:
if is_menu_command(body):
    sms, twiml = handle_menu(body, session["assessment"], session["name"])
else:
    location = resolve_location(body)
    assessment, sms, twiml = assess(location["lat"], location["lon"], location["name"])
    sessions[from_number] = {"assessment": assessment, "name": location["name"]}
```

---

## Module 2: Location Parser (`parser/`)

**Owner:** (teammate 2)
**Status:** DONE

Pure location resolver — command detection owned by `pipeline.py`.

- [x] Function: `resolve_location(text) → {lat, lon, name, source, approximate}`
- [x] 3-tier geocoding: cache → Nominatim → OpenCage → fuzzy fallback (never fails)
- [x] Normalize input: strip, lowercase, "barangay" → "brgy" prefix normalization
- [x] Imports fixed to work as package from project root

**Integration:** Returns dict with `lat`, `lon`, `name` for `pipeline.assess()`.

---

## Module 3: Data Fetching (`data/`)

**Owner:** (your name)
**Status:** DONE

- [x] `data/pagasa.py` — PAGASA Rainfall Forecast (portal.georisk.gov.ph)
- [x] `data/susceptibility.py` — MGB Flood Susceptibility (controlmap.mgb.gov.ph)
- [x] `data/weather.py` — Open-Meteo hourly forecast (api.open-meteo.com)

All three APIs verified working with live data.

---

## Module 4: Risk Engine + Response (`risk/`)

**Owner:** (your name)
**Status:** DONE

- [x] `risk/engine.py` — Multiplicative risk model (susceptibility × rain_trigger → tier)
- [x] `risk/response.py` — All response formatters:
  - [x] `format_sms()` — Initial assessment (danger mode vs safe mode + menu)
  - [x] `format_why()` — WHY explainability (sources, score breakdown)
  - [x] `format_home_prep()` — Home preparation checklist (tier-tailored)
  - [x] `format_travel()` — Travel safety advice (tier-tailored)
  - [x] `format_farmer()` — Farmer/agriculture advice (tier-tailored)
  - [x] `format_unknown_location()` — Error when location not found
  - [x] `format_no_session()` — Error when menu used without prior location
  - [x] `format_stop()` — Unsubscribe acknowledgment
  - [x] `format_twiml()` — TwiML XML wrapper

---

## Module 5: Pipeline (`pipeline.py`)

**Owner:** (your name)
**Status:** DONE

- [x] `assess(lat, lon, name)` — Full pipeline: data fetch → risk → formatted SMS + TwiML
- [x] `handle_menu(command, assessment, name)` — Menu command router (1-4 + word aliases, WHY, LOC, STOP)
- [x] `is_menu_command(text)` — Check if input is a menu command vs location (supports number + word aliases)

---

## Tests (`tests/`)

Run: `python -m tests.test_pipeline [--quick | --demo | --coord lat lon name]`

- [x] Risk engine unit tests (thresholds, classification)
- [x] Response formatting (danger vs safe mode, menu footer)
- [x] Menu command handlers (number + word aliases + no-session + STOP)
- [x] Command detection (menu vs location input, including word aliases)
- [x] Live API tests (PAGASA, Open-Meteo, MGB)
- [x] Full pipeline end-to-end
- [x] Demo conversation simulation (4-step SMS exchange)

---

## SMS User Flow

```
User: "Marikina"
Bot:  🟡 FLOOD WARNING | MARIKINA CITY
      Rain: Moderate (45mm) [PAGASA]
      Susceptibility: Very High
      DO NOW: 1. Charge phone... 2. Move valuables...
      Reply 1-4, WHY, or a new location.

User: "WHY"
Bot:  🟡 WHY WARNING | MARIKINA CITY
      Rainfall: 45mm (Moderate) — Source: PAGASA
      Susceptibility: Very High (4/4) — Source: MGB
      Risk score: 4 x 1 = 4
      Reply 1-4, WHY, or a new location.

User: "2"
Bot:  🟡 HOME PREP | MARIKINA CITY (WARNING)
      1. Move valuables upstairs...
      Reply 1-4, WHY, or a new location.

User: "Cebu City"
Bot:  🟠 FLOOD WATCH | CEBU CITY
      Rain: Moderate (59mm) [PAGASA]
      Susceptibility: Low
      Stay alert. No immediate action needed.
      Reply: 1 Risk check  2 Home prep  3 Travel  4 Farmer...
```

---

## Data Sources

| Source | Endpoint | Returns |
|--------|----------|---------|
| PAGASA Rainfall | `portal.georisk.gov.ph/.../Rainfall_Forecast/MapServer/identify` | Rainfall mm + class |
| MGB Flood Susceptibility | `controlmap.mgb.gov.ph/.../GDI_Detailed_Flood_Susceptibility/FeatureServer/0/query` | VHF/HF/MF/LF |
| Open-Meteo | `api.open-meteo.com/v1/forecast` | Hourly precipitation |
