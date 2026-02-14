"""
SMS response formatter.

Takes a RiskAssessment and a location name, produces SMS-ready text.
Each template is designed to fit within 2-3 SMS segments (~300-450 chars).
"""

from risk.engine import RiskAssessment


# ---------------------------------------------------------------------------
# Action templates per tier
# ---------------------------------------------------------------------------

ACTIONS = {
    "CRITICAL": [
        "EVACUATE to higher ground NOW.",
        "Bring IDs, meds, water, phone.",
        "Turn off main power before leaving.",
        "Do NOT cross floodwater on foot or by vehicle.",
    ],
    "WARNING": [
        "Charge phone and powerbank.",
        "Move valuables to higher floor.",
        "Pack go-bag: IDs, meds, water, clothes.",
        "Monitor for rising water levels.",
    ],
    "WATCH": [
        "Stay alert for official advisories.",
        "Avoid unnecessary travel near waterways.",
    ],
    "SAFE": [],
}

TIER_EMOJI = {
    "CRITICAL": "\U0001f534",  # 🔴
    "WARNING":  "\U0001f7e1",  # 🟡
    "WATCH":    "\U0001f7e0",  # 🟠
    "SAFE":     "\u2705",      # ✅
}

# Map rain source to a more readable credit
SOURCE_LABELS = {
    "pagasa": "PAGASA",
    "open-meteo": "Open-Meteo",
    "none": "N/A",
}


def format_sms(assessment: RiskAssessment, location_name: str) -> str:
    """
    Build the SMS reply text from a RiskAssessment.

    `location_name` is whatever the parser resolved — could be a city,
    barangay, or any human-readable label.
    """
    emoji = TIER_EMOJI.get(assessment.tier, "")
    lines = []

    # Header
    lines.append(f"{emoji} FLOOD {assessment.tier} | {location_name.upper()}")

    # Forecast line
    if assessment.forecast_available:
        source_label = SOURCE_LABELS.get(assessment.rain_source, assessment.rain_source)
        lines.append(
            f"Rain: {assessment.rain_label} ({assessment.rain_mm:.0f}mm) "
            f"[{source_label}]"
        )
    else:
        lines.append("Rain forecast: Unavailable")

    # Susceptibility line
    lines.append(f"Flood susceptibility: {assessment.suscept_label}")

    # Actions
    actions = ACTIONS.get(assessment.tier, [])
    if actions:
        lines.append("")
        lines.append("ACTIONS:")
        for i, action in enumerate(actions, 1):
            lines.append(f"{i}. {action}")

    # Footer
    lines.append("")
    lines.append("Reply FLOOD <city> to check another area.")

    return "\n".join(lines)


def format_twiml(sms_text: str) -> str:
    """Wrap SMS text in TwiML for Twilio webhook response."""
    escaped = (
        sms_text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escaped}</Message></Response>"
    )
