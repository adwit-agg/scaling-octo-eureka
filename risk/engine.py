"""
Risk engine.

Takes rainfall metrics + susceptibility and produces a risk tier.

Two rainfall classification modes:
  1. PAGASA (primary): uses PAGASA's own class thresholds (0-40, 40-80, 80-120, 120+ mm)
  2. Open-Meteo (fallback): uses 6hr-based thresholds (0-7.5, 7.5-15, 15-30, 30+ mm)

Model:
  rain_trigger (0-3)  = classify(rainfall)
  score               = susceptibility (1-4)  ×  rain_trigger (0-3)
  tier                = threshold(score)

  score  0     → SAFE
  score  1-3   → WATCH
  score  4-6   → WARNING
  score  7+    → CRITICAL
"""

from dataclasses import dataclass


@dataclass
class RiskAssessment:
    tier: str              # SAFE | WATCH | WARNING | CRITICAL
    score: int             # raw multiplicative score
    susceptibility: int    # 1-4
    suscept_label: str     # Low / Medium / High / Very High
    suscept_source: str    # where the susceptibility came from
    rain_trigger: int      # 0-3
    rain_label: str        # Light / Moderate / Heavy / Intense
    rain_source: str       # "pagasa" | "open-meteo" | "none"
    rain_mm: float         # primary rainfall value used for classification
    rain_detail: str       # human-readable detail about the rainfall data
    forecast_available: bool
    description: str       # one-liner for the tier


# ---------------------------------------------------------------------------
# Rain classification — PAGASA thresholds (for PAGASA aggregate forecast)
# ---------------------------------------------------------------------------
# Based on PAGASA Rainfall Forecast MapServer legend:
#   Class 1:   0 –  40 mm   → trigger 0 (Light)
#   Class 2:  40 –  80 mm   → trigger 1 (Moderate)
#   Class 3:  80 – 120 mm   → trigger 2 (Heavy)
#   Class 4: 120+ mm        → trigger 3 (Intense)

def classify_rain_pagasa(mm: float) -> tuple[int, str]:
    """Classify using PAGASA's official thresholds."""
    if mm <= 40:
        return 0, "Light"
    elif mm <= 80:
        return 1, "Moderate"
    elif mm <= 120:
        return 2, "Heavy"
    else:
        return 3, "Intense"


# ---------------------------------------------------------------------------
# Rain classification — Open-Meteo thresholds (for 6hr hourly sum)
# ---------------------------------------------------------------------------
# Scaled-down thresholds for a 6hr window:
#   Light    < 7.5 mm / 6h
#   Moderate   7.5 – 15 mm / 6h
#   Heavy     15 – 30 mm / 6h
#   Intense   30+ mm / 6h

def classify_rain_openmeteo(mm_6h: float) -> tuple[int, str]:
    """Classify using Open-Meteo 6hr thresholds."""
    if mm_6h < 7.5:
        return 0, "Light"
    elif mm_6h < 15:
        return 1, "Moderate"
    elif mm_6h < 30:
        return 2, "Heavy"
    else:
        return 3, "Intense"


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------

TIER_THRESHOLDS = [
    (0,  "SAFE",     "No immediate flood risk."),
    (3,  "WATCH",    "Low flood risk. Stay alert for updates."),
    (6,  "WARNING",  "Moderate flood risk. Prepare to act."),
    (99, "CRITICAL", "High flood risk. Act immediately."),
]


def _score_to_tier(score: int) -> tuple[str, str]:
    """Return (tier_name, description) for a given score."""
    for max_score, tier, desc in TIER_THRESHOLDS:
        if score <= max_score:
            return tier, desc
    return "CRITICAL", "High flood risk. Act immediately."


def assess_risk(
    susceptibility: int,
    suscept_label: str,
    suscept_source: str,
    # PAGASA data (primary — may be None if unavailable)
    pagasa_mm: float | None,
    pagasa_available: bool,
    # Open-Meteo data (fallback — may be None if unavailable)
    openmeteo_6h_mm: float | None,
    openmeteo_3h_mm: float | None,
    openmeteo_peak_mm: float | None,
    openmeteo_available: bool,
) -> RiskAssessment:
    """
    Core risk computation.

    Prefers PAGASA rainfall data (official PH source) when available.
    Falls back to Open-Meteo. If neither is available, uses susceptibility only.
    """

    # Decide which rainfall source to use
    if pagasa_available and pagasa_mm is not None:
        rain_trigger, rain_label = classify_rain_pagasa(pagasa_mm)
        rain_source = "pagasa"
        rain_mm = pagasa_mm
        rain_detail = f"PAGASA forecast: {pagasa_mm:.0f}mm"
        if openmeteo_available and openmeteo_6h_mm is not None:
            rain_detail += f" | Open-Meteo 6hr: {openmeteo_6h_mm:.1f}mm"
        forecast_available = True

    elif openmeteo_available and openmeteo_6h_mm is not None:
        rain_trigger, rain_label = classify_rain_openmeteo(openmeteo_6h_mm)
        rain_source = "open-meteo"
        rain_mm = openmeteo_6h_mm
        rain_detail = f"Open-Meteo 6hr: {openmeteo_6h_mm:.1f}mm"
        if openmeteo_3h_mm is not None:
            rain_detail += f", 3hr: {openmeteo_3h_mm:.1f}mm"
        forecast_available = True

    else:
        rain_trigger = 0
        rain_label = "Unknown"
        rain_source = "none"
        rain_mm = 0.0
        rain_detail = "No forecast data available"
        forecast_available = False

    # Compute score
    score = susceptibility * rain_trigger
    tier, description = _score_to_tier(score)

    # If no forecast at all, be conservative for high-susceptibility areas
    if not forecast_available:
        description += " (no forecast data)"
        if susceptibility >= 3:
            tier = "WATCH"
            description = "Flood-prone area. No forecast data — stay alert."

    return RiskAssessment(
        tier=tier,
        score=score,
        susceptibility=susceptibility,
        suscept_label=suscept_label,
        suscept_source=suscept_source,
        rain_trigger=rain_trigger,
        rain_label=rain_label,
        rain_source=rain_source,
        rain_mm=rain_mm,
        rain_detail=rain_detail,
        forecast_available=forecast_available,
        description=description,
    )
