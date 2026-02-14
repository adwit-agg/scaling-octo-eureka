"""
SMS response formatter.

Produces SMS-ready text for:
  - Initial location assessment (danger mode vs safe mode)
  - Menu commands (WHY, Home prep, Travel, Farmer)
  - Error / help messages

Every response includes a menu footer so the user knows their options.
Templates are sized to fit within 2-3 SMS segments (~300-450 chars).
"""

from risk.engine import RiskAssessment


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIER_EMOJI = {
    "CRITICAL": "\U0001f534",  # 🔴
    "WARNING":  "\U0001f7e1",  # 🟡
    "WATCH":    "\U0001f7e0",  # 🟠
    "SAFE":     "\u2705",      # ✅
}

SOURCE_LABELS = {
    "pagasa": "PAGASA",
    "open-meteo": "Open-Meteo",
    "none": "N/A",
}

MENU_FOOTER = (
    "Reply:\n"
    "1 Risk check\n"
    "2 Home prep\n"
    "3 Travel\n"
    "4 Farmer\n"
    "WHY details\n"
    "Or text a new location."
)

MENU_FOOTER_SHORT = "Reply 1-4, WHY, or a new location."


# ---------------------------------------------------------------------------
# Danger-mode actions (WARNING / CRITICAL)
# ---------------------------------------------------------------------------

DANGER_ACTIONS = {
    "CRITICAL": [
        "EVACUATE to higher ground NOW.",
        "Bring IDs, meds, water, phone.",
        "Turn off main power before leaving.",
        "Do NOT cross floodwater.",
    ],
    "WARNING": [
        "Charge phone and powerbank.",
        "Move valuables to higher floor.",
        "Pack go-bag: IDs, meds, water, clothes.",
        "Monitor for rising water levels.",
    ],
}


# ---------------------------------------------------------------------------
# 1) Initial assessment response — the first reply to a location text
# ---------------------------------------------------------------------------

def format_sms(assessment: RiskAssessment, location_name: str) -> str:
    """
    Build the initial SMS reply from a RiskAssessment.

    Two modes:
      - Danger (WARNING/CRITICAL): risk + WHY + actions + menu
      - Safe (SAFE/WATCH): status line + menu
    """
    emoji = TIER_EMOJI.get(assessment.tier, "")
    loc = location_name.upper()

    # Rain line
    if assessment.forecast_available:
        source = SOURCE_LABELS.get(assessment.rain_source, assessment.rain_source)
        rain_line = f"Rain: {assessment.rain_label} ({assessment.rain_mm:.0f}mm) [{source}]"
    else:
        rain_line = "Rain forecast: Unavailable"

    suscept_line = f"Susceptibility: {assessment.suscept_label}"

    if assessment.tier in ("CRITICAL", "WARNING"):
        # --- Danger mode ---
        lines = [
            f"{emoji} FLOOD {assessment.tier} | {loc}",
            rain_line,
            suscept_line,
            "",
            "DO NOW:",
        ]
        for i, action in enumerate(DANGER_ACTIONS[assessment.tier], 1):
            lines.append(f"{i}. {action}")
        lines.append("")
        lines.append(MENU_FOOTER_SHORT)
    else:
        # --- Safe mode ---
        lines = [
            f"{emoji} FLOOD {assessment.tier} | {loc}",
            rain_line,
            suscept_line,
            "",
        ]
        if assessment.tier == "WATCH":
            lines.append("Stay alert. No immediate action needed.")
            lines.append("")
        lines.append(MENU_FOOTER)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2) Menu command responses
# ---------------------------------------------------------------------------

def format_why(assessment: RiskAssessment, location_name: str) -> str:
    """WHY — explainability: how the risk was calculated."""
    emoji = TIER_EMOJI.get(assessment.tier, "")
    source = SOURCE_LABELS.get(assessment.rain_source, assessment.rain_source)

    lines = [
        f"{emoji} WHY {assessment.tier} | {location_name.upper()}",
        "",
        f"Rainfall: {assessment.rain_mm:.0f}mm ({assessment.rain_label})",
        f"  Source: {source}",
        f"  {assessment.rain_detail}",
        "",
        f"Flood susceptibility: {assessment.suscept_label} ({assessment.susceptibility}/4)",
        f"  Source: MGB (Mines and Geosciences Bureau)",
        "",
        f"Risk score: {assessment.susceptibility} x {assessment.rain_trigger} = {assessment.score}",
        f"Thresholds: 0=SAFE, 1-3=WATCH, 4-6=WARNING, 7+=CRITICAL",
        "",
        MENU_FOOTER_SHORT,
    ]
    return "\n".join(lines)


def format_home_prep(assessment: RiskAssessment, location_name: str) -> str:
    """Menu 2 — Home preparation checklist, tailored to risk tier."""
    emoji = TIER_EMOJI.get(assessment.tier, "")

    if assessment.tier == "CRITICAL":
        items = [
            "If still home — LEAVE NOW.",
            "Turn off electricity and gas.",
            "Seal important documents in plastic.",
            "Move to evacuation center or higher ground.",
        ]
    elif assessment.tier == "WARNING":
        items = [
            "Move valuables and electronics upstairs.",
            "Fill containers with clean drinking water.",
            "Charge all phones and powerbanks.",
            "Pack go-bag: IDs, meds, water, change of clothes.",
            "Know your evacuation route.",
        ]
    elif assessment.tier == "WATCH":
        items = [
            "Check flashlights and batteries.",
            "Stock 3 days of food and water.",
            "Secure loose items outside (plants, furniture).",
            "Keep phone charged.",
        ]
    else:  # SAFE
        items = [
            "No urgent prep needed.",
            "Good time to restock emergency supplies.",
            "Check that your go-bag is ready (IDs, meds, water).",
        ]

    lines = [
        f"{emoji} HOME PREP | {location_name.upper()} ({assessment.tier})",
        "",
    ]
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item}")
    lines.append("")
    lines.append(MENU_FOOTER_SHORT)

    return "\n".join(lines)


def format_travel(assessment: RiskAssessment, location_name: str) -> str:
    """Menu 3 — Travel safety advice based on risk tier."""
    emoji = TIER_EMOJI.get(assessment.tier, "")

    if assessment.tier == "CRITICAL":
        advice = [
            "DO NOT TRAVEL. Roads may be impassable.",
            "Do not cross flooded roads on foot or by vehicle.",
            "If caught in rising water, move to highest accessible point.",
            "Wait for official all-clear before traveling.",
        ]
    elif assessment.tier == "WARNING":
        advice = [
            "Avoid low-lying roads and underpasses.",
            "Delay non-essential travel.",
            "If driving, do not enter flooded roads — turn around.",
            "Keep phone charged for updates.",
        ]
    elif assessment.tier == "WATCH":
        advice = [
            "Travel with caution near rivers and waterways.",
            "Avoid low-lying routes if heavy rain starts.",
            "Keep updated on weather advisories.",
        ]
    else:  # SAFE
        advice = [
            "Travel conditions are normal.",
            "Stay aware of weather changes.",
        ]

    lines = [
        f"{emoji} TRAVEL | {location_name.upper()} ({assessment.tier})",
        "",
    ]
    for i, item in enumerate(advice, 1):
        lines.append(f"{i}. {item}")
    lines.append("")
    lines.append(MENU_FOOTER_SHORT)

    return "\n".join(lines)


def format_farmer(assessment: RiskAssessment, location_name: str) -> str:
    """Menu 4 — Farmer/agriculture advice based on risk tier."""
    emoji = TIER_EMOJI.get(assessment.tier, "")

    if assessment.tier == "CRITICAL":
        advice = [
            "Prioritize personal safety over crops/livestock.",
            "Move livestock to higher ground immediately.",
            "Secure or harvest what you can NOW.",
            "Do not work in open fields.",
        ]
    elif assessment.tier == "WARNING":
        advice = [
            "Delay planting if heavy rain expected.",
            "Move equipment and supplies to higher ground.",
            "Secure livestock shelters.",
            "Harvest ripe crops before heavy rain hits.",
        ]
    elif assessment.tier == "WATCH":
        advice = [
            "Monitor forecasts before field work.",
            "Delay fertilizer application if rain is expected.",
            "Check drainage ditches are clear.",
        ]
    else:  # SAFE
        advice = [
            "Good conditions for field work.",
            "Good time to maintain drainage systems.",
            "Check weather before scheduling irrigation.",
        ]

    lines = [
        f"{emoji} FARMER | {location_name.upper()} ({assessment.tier})",
        f"Rain: {assessment.rain_label} ({assessment.rain_mm:.0f}mm)",
        "",
    ]
    for i, item in enumerate(advice, 1):
        lines.append(f"{i}. {item}")
    lines.append("")
    lines.append(MENU_FOOTER_SHORT)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3) Error / help messages
# ---------------------------------------------------------------------------

def format_unknown_location(raw_input: str) -> str:
    """Reply when parser can't resolve the location."""
    return (
        f"Could not find \"{raw_input}\".\n"
        "Try a city name like: Marikina, Cebu, Davao, Tacloban\n"
        "\n"
        "Or text STOP to unsubscribe."
    )


def format_no_session() -> str:
    """Reply when user sends a menu command but has no prior location."""
    return (
        "No location on file.\n"
        "Text a city name to get started.\n"
        "Example: Marikina"
    )


def format_stop() -> str:
    """Reply for STOP / unsubscribe."""
    return "You've been unsubscribed. Text any city name to start again."


# ---------------------------------------------------------------------------
# TwiML wrapper
# ---------------------------------------------------------------------------

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
