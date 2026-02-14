"""
Core pipeline: the single function your teammates call.

    assess(lat, lon, location_name) → (RiskAssessment, sms_text, twiml)

Data sources (all live, all from official PH government or open APIs):
  1. PAGASA Rainfall Forecast — raster via portal.georisk.gov.ph (official PH weather)
  2. Open-Meteo hourly forecast — via api.open-meteo.com (supplemental hourly detail)
  3. MGB Flood Susceptibility — polygon via controlmap.mgb.gov.ph (official MGB data)

Risk model:
  score = susceptibility (1-4) × rain_trigger (0-3)  →  SAFE / WATCH / WARNING / CRITICAL

Your Twilio teammate calls this from the webhook handler.
Your parser teammate provides (lat, lon, location_name).
"""

from data.pagasa import fetch_pagasa_rainfall
from data.weather import fetch_rainfall
from data.susceptibility import get_susceptibility
from risk.engine import assess_risk, RiskAssessment
from risk.response import format_sms, format_twiml


def assess(lat: float, lon: float, location_name: str) -> tuple[RiskAssessment, str, str]:
    """
    Run the full flood risk pipeline for a coordinate.

    Args:
        lat: Latitude (decimal degrees)
        lon: Longitude (decimal degrees)
        location_name: Human-readable name (e.g. "Marikina City", "Brgy Lahug, Cebu")

    Returns:
        (assessment, sms_text, twiml)
        - assessment: RiskAssessment dataclass with all details
        - sms_text:   Plain text SMS reply
        - twiml:      TwiML-wrapped XML string for Twilio response
    """

    print(f"\n{'='*60}")
    print(f"[PIPELINE] Assessing flood risk for: {location_name} ({lat}, {lon})")
    print(f"{'='*60}")

    # 1) PAGASA rainfall forecast (primary rain source)
    pagasa = fetch_pagasa_rainfall(lat, lon)
    if pagasa.available:
        print(
            f"[PIPELINE] PAGASA: {pagasa.rainfall_mm:.1f}mm → "
            f"Class {pagasa.pagasa_class}: {pagasa.pagasa_class_label}"
        )
    else:
        print("[PIPELINE] PAGASA: unavailable")

    # 2) Open-Meteo hourly forecast (supplemental / adds hourly granularity)
    openmeteo = fetch_rainfall(lat, lon)
    if openmeteo.forecast_available:
        print(
            f"[PIPELINE] Open-Meteo: {openmeteo.rain_6h_mm:.1f}mm/6h, "
            f"{openmeteo.rain_3h_mm:.1f}mm/3h, peak {openmeteo.peak_hourly_mm:.1f}mm/h"
        )
    else:
        print("[PIPELINE] Open-Meteo: unavailable")

    # 3) MGB flood susceptibility (live polygon query)
    suscept = get_susceptibility(lat, lon)
    print(
        f"[PIPELINE] Susceptibility: {suscept.label} ({suscept.level}/4) "
        f"[source: {suscept.source}]"
    )

    # 4) Compute risk
    assessment = assess_risk(
        susceptibility=suscept.level,
        suscept_label=suscept.label,
        suscept_source=suscept.source,
        pagasa_mm=pagasa.rainfall_mm if pagasa.available else None,
        pagasa_available=pagasa.available,
        openmeteo_6h_mm=openmeteo.rain_6h_mm if openmeteo.forecast_available else None,
        openmeteo_3h_mm=openmeteo.rain_3h_mm if openmeteo.forecast_available else None,
        openmeteo_peak_mm=openmeteo.peak_hourly_mm if openmeteo.forecast_available else None,
        openmeteo_available=openmeteo.forecast_available,
    )
    print(
        f"[PIPELINE] Risk: {assessment.tier} "
        f"(score={assessment.score}, "
        f"suscept={assessment.susceptibility} × rain_trigger={assessment.rain_trigger})"
    )
    print(f"[PIPELINE] Rain detail: {assessment.rain_detail}")

    # 5) Format response
    sms_text = format_sms(assessment, location_name)
    twiml = format_twiml(sms_text)

    print(f"\n[PIPELINE] SMS reply:")
    print(f"---")
    print(sms_text)
    print(f"---\n")

    return assessment, sms_text, twiml
