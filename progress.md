# Flood Risk SMS Assistant — Progress Tracker

Last updated: 2026-02-13

---

## Architecture Overview

```
User sends SMS → [sms/] Twilio webhook → [parser/] extract location
  → [data/] fetch PAGASA rain + MGB susceptibility + Open-Meteo hourly
    → [risk/] score = susceptibility × rain_trigger → tier + actions
      → TwiML response → Twilio → SMS reply to user
```

---

## Module 1: SMS Gateway (`sms/`)

**Owner:** (teammate 1)
**Status:** In progress

Twilio webhook that receives incoming SMS, delegates to parser + pipeline, and returns TwiML.

- [ ] Flask route `POST /sms` that reads Twilio `Body` and `From` fields
- [ ] Returns `application/xml` TwiML response (pipeline already generates this)
- [ ] Twilio phone number configured with webhook URL
- [ ] ngrok (or similar) for local dev tunneling
- [ ] Signature verification (optional for hackathon)

**Integration point:** Calls `from pipeline import assess` with `(lat, lon, name)` from parser, returns `twiml` string.

---

## Module 2: Location Parser (`parser/`)

**Owner:** (teammate 2)
**Status:** In progress

Parses raw SMS text into coordinates and a human-readable location name.

- [ ] Parse `FLOOD <city>` command from SMS body
- [ ] Resolve city/barangay name to `(lat, lon)` — options:
  - Hardcoded lookup table of common cities
  - Nominatim (OSM) geocoding for arbitrary locations
  - Hybrid: table first, Nominatim fallback
- [ ] Return `(lat, lon, location_name)` tuple
- [ ] Handle unknown/unrecognized locations gracefully (error reply text)
- [ ] Normalize input: strip whitespace, case-insensitive, handle "city" suffix

**Integration point:** Returns `(lat, lon, location_name)` which gets passed to `pipeline.assess()`.

---

## Module 3: Data Fetching (`data/`)

**Owner:** (your name)
**Status:** DONE

Fetches live data from three external sources given a `(lat, lon)` coordinate.

- [x] **PAGASA Rainfall Forecast** (`data/pagasa.py`)
  - Queries `portal.georisk.gov.ph` Rainfall_Forecast MapServer via ArcGIS Identify
  - Returns rainfall in mm + PAGASA class (1-4)
  - Official Philippine government weather data
- [x] **MGB Flood Susceptibility** (`data/susceptibility.py`)
  - Queries `controlmap.mgb.gov.ph` GDI_Detailed_Flood_Susceptibility FeatureServer
  - Point-in-polygon spatial query returns `VHF`/`HF`/`MF`/`LF`
  - Official MGB polygon data — exact zone for any coordinate in the PH
- [x] **Open-Meteo Hourly Forecast** (`data/weather.py`)
  - Queries `api.open-meteo.com` for hourly precipitation (next 12hrs)
  - Returns 3hr total, 6hr total, peak hourly
  - Supplemental source — adds hourly granularity to PAGASA aggregate

**All three APIs verified working as of 2026-02-13.**

---

## Module 4: Risk Engine + Response (`risk/`)

**Owner:** (your name)
**Status:** DONE

Pure logic — no API calls. Takes data module outputs and produces a risk tier + SMS text.

- [x] **Risk engine** (`risk/engine.py`)
  - PAGASA rain classification: 0-40mm → Light, 40-80 → Moderate, 80-120 → Heavy, 120+ → Intense
  - Multiplicative scoring: `susceptibility (1-4) × rain_trigger (0-3)`
  - Tier thresholds: 0 = SAFE, 1-3 = WATCH, 4-6 = WARNING, 7+ = CRITICAL
  - Safety bias: high susceptibility areas warned even with no forecast data
  - PAGASA primary, Open-Meteo fallback for rain classification
- [x] **Response formatter** (`risk/response.py`)
  - Tier-specific SMS templates with emoji, rain source attribution, and action items
  - TwiML wrapper for Twilio webhook response
  - Templates fit within 2-3 SMS segments (~300-450 chars)

---

## Module 5: Pipeline Orchestrator (`pipeline.py`)

**Owner:** (your name)
**Status:** DONE

Single function that chains everything together.

- [x] `assess(lat, lon, location_name)` → `(RiskAssessment, sms_text, twiml)`
- [x] Calls data modules (PAGASA, Open-Meteo, MGB) then risk engine then formatter
- [x] Structured logging for demo terminal output
- [x] Graceful degradation if any API is down

---

## Tests (`tests/`)

- [x] Risk engine unit tests (all threshold boundaries)
- [x] Response formatting tests
- [x] Live API tests (PAGASA, Open-Meteo, MGB susceptibility)
- [x] Full pipeline end-to-end with 6 cities

Run: `python -m tests.test_pipeline` (full) or `python -m tests.test_pipeline --quick` (offline only)

---

## Integration Checklist

When all modules are ready, connect them:

- [ ] `sms/` webhook calls `parser/` to get `(lat, lon, name)` from SMS body
- [ ] `sms/` webhook calls `pipeline.assess(lat, lon, name)` to get `twiml`
- [ ] `sms/` webhook returns `twiml` as HTTP response to Twilio
- [ ] End-to-end test: real SMS from phone → Twilio → webhook → pipeline → SMS reply

---

## Data Sources

| Source | Type | Endpoint | Auth |
|--------|------|----------|------|
| PAGASA Rainfall Forecast | Raster (identify) | `portal.georisk.gov.ph/.../Rainfall_Forecast/MapServer/identify` | None |
| MGB Flood Susceptibility | Polygon (query) | `controlmap.mgb.gov.ph/.../GDI_Detailed_Flood_Susceptibility/FeatureServer/0/query` | None |
| Open-Meteo | JSON API | `api.open-meteo.com/v1/forecast` | None |
