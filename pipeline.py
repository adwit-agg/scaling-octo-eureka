"""
Core pipeline — two entry points for your teammates:

  1. assess(lat, lon, location_name)
     → Initial location assessment. Call when user texts a location.
     → Returns (RiskAssessment, sms_text, twiml)

  2. handle_menu(command, assessment, location_name)
     → Menu follow-up. Call when user replies 1-4 or WHY.
     → Returns (sms_text, twiml)

  3. handle_command(raw_text, assessment, location_name)
     → High-level router. Decides if input is a menu command or unknown.
     → Returns (sms_text, twiml) or None if input is a location (not a command).

Data sources (all live):
  - PAGASA Rainfall Forecast (portal.georisk.gov.ph)
  - Open-Meteo hourly forecast (api.open-meteo.com)
  - MGB Flood Susceptibility (controlmap.mgb.gov.ph)
"""

from data.pagasa import fetch_pagasa_rainfall
from data.weather import fetch_rainfall
from data.susceptibility import get_susceptibility
from risk.engine import assess_risk, RiskAssessment
from risk.response import (
    format_sms,
    format_twiml,
    format_why,
    format_home_prep,
    format_travel,
    format_farmer,
    format_no_session,
    format_stop,
)


# ---------------------------------------------------------------------------
# Known menu commands — if input matches one of these, it's not a location
# ---------------------------------------------------------------------------
MENU_COMMANDS = {
    "1", "2", "3", "4", "5",
    "flood", "prep", "travel", "farm",   # word aliases for 1-4
    "why", "loc", "stop",
}


def is_menu_command(text: str) -> bool:
    """Check if the raw SMS text is a menu command (not a location)."""
    return text.strip().lower() in MENU_COMMANDS


# ---------------------------------------------------------------------------
# 1) Initial assessment — user texts a location
# ---------------------------------------------------------------------------

def assess(lat: float, lon: float, location_name: str) -> tuple[RiskAssessment, str, str]:
    """
    Run the full flood risk pipeline for a coordinate.

    Returns:
        (assessment, sms_text, twiml)
    """

    print(f"\n{'='*60}")
    print(f"[PIPELINE] Assessing flood risk for: {location_name} ({lat}, {lon})")
    print(f"{'='*60}")

    # 1) PAGASA rainfall forecast
    pagasa = fetch_pagasa_rainfall(lat, lon)
    if pagasa.available:
        print(
            f"[PIPELINE] PAGASA: {pagasa.rainfall_mm:.1f}mm → "
            f"Class {pagasa.pagasa_class}: {pagasa.pagasa_class_label}"
        )
    else:
        print("[PIPELINE] PAGASA: unavailable")

    # 2) Open-Meteo hourly forecast
    openmeteo = fetch_rainfall(lat, lon)
    if openmeteo.forecast_available:
        print(
            f"[PIPELINE] Open-Meteo: {openmeteo.rain_6h_mm:.1f}mm/6h, "
            f"{openmeteo.rain_3h_mm:.1f}mm/3h, peak {openmeteo.peak_hourly_mm:.1f}mm/h"
        )
    else:
        print("[PIPELINE] Open-Meteo: unavailable")

    # 3) MGB flood susceptibility
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

    # 5) Format response
    sms_text = format_sms(assessment, location_name)
    twiml = format_twiml(sms_text)

    print(f"\n[PIPELINE] SMS reply:\n---\n{sms_text}\n---\n")

    return assessment, sms_text, twiml


# ---------------------------------------------------------------------------
# 2) Menu command handler — user replies with 1-4, WHY, STOP
# ---------------------------------------------------------------------------

def handle_menu(
    command: str,
    assessment: RiskAssessment | None,
    location_name: str | None,
) -> tuple[str, str]:
    """
    Handle a menu reply. Requires a stored assessment from a prior location query.

    Args:
        command: The raw user input ("1", "2", "3", "4", "why", "stop")
        assessment: The RiskAssessment from their last location query (or None)
        location_name: The location name from their last query (or None)

    Returns:
        (sms_text, twiml)
    """
    cmd = command.strip().lower()

    # STOP doesn't need a session
    if cmd == "stop":
        sms_text = format_stop()
        return sms_text, format_twiml(sms_text)

    # Everything else needs a prior assessment
    if assessment is None or location_name is None:
        sms_text = format_no_session()
        return sms_text, format_twiml(sms_text)

    if cmd in ("1", "flood"):
        # Return the cached assessment (caller can call assess() for a live refresh)
        sms_text = format_sms(assessment, location_name)

    elif cmd in ("2", "prep"):
        sms_text = format_home_prep(assessment, location_name)

    elif cmd in ("3", "travel"):
        sms_text = format_travel(assessment, location_name)

    elif cmd in ("4", "farm"):
        sms_text = format_farmer(assessment, location_name)

    elif cmd in ("5", "loc"):
        sms_text = "Send a new city or barangay name to update your location."

    elif cmd == "why":
        sms_text = format_why(assessment, location_name)

    else:
        sms_text = format_no_session()

    print(f"[PIPELINE] Menu '{cmd}' for {location_name}:\n---\n{sms_text}\n---\n")
    return sms_text, format_twiml(sms_text)
