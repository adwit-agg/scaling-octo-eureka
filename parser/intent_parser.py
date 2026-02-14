"""
intent_parser.py — Location-first SMS intent parser.

Flow:
  1. User sends a location (e.g. "Brgy Lahug, Cebu City")
  2. System resolves it to coordinates (via geocoder.py)
  3. System returns coordinates + available command menu

If the message is a known command keyword, it is returned as an action
instead of being treated as a location.
"""

from geocoder import get_coordinates

# ---------------------------------------------------------------------------
# Known commands the user can send *after* setting their location.
# These are presented as a menu after the first location resolve.
# ---------------------------------------------------------------------------

KNOWN_COMMANDS = {
    "1":       "flood",     # Risk assessment
    "flood":   "flood",
    "2":       "prep",      # Home prep checklist
    "prep":    "prep",
    "3":       "travel",    # Travel safety
    "travel":  "travel",
    "4":       "farm",      # Farmer mode
    "farm":    "farm",
    "why":     "why",       # Explain risk calculation
    "loc":     "loc",       # Update location (next message = new location)
    "stop":    "stop",      # Unsubscribe
}

COMMAND_MENU = (
    "Reply with:\n"
    "  1 - Risk assessment\n"
    "  2 - Home prep checklist\n"
    "  3 - Travel safety\n"
    "  4 - Farmer guidance\n"
    "  WHY - Explain risk\n"
    "  LOC - Update location\n"
    "  STOP - Unsubscribe"
)


# ---------------------------------------------------------------------------
# Location string normalization
# ---------------------------------------------------------------------------

def normalize_location(raw: str) -> str:
    """
    Clean up a raw location string for geocoding.
    - lowercase, strip
    - normalize common PH prefixes/suffixes
    """
    text = raw.lower().strip()

    # Normalize "barangay" variants → "brgy"
    for prefix in ("barangay ", "bgy ", "bgy. "):
        if text.startswith(prefix):
            text = "brgy " + text[len(prefix):]

    # Strip trailing "city" if preceded by comma (e.g. "lahug, cebu city" stays,
    # but standalone "cebu city" also stays — only strip if redundant)
    # Actually, keep "city" — Nominatim uses it. Just clean whitespace.
    text = " ".join(text.split())  # collapse multiple spaces
    return text


# ---------------------------------------------------------------------------
# Public API — parse_intent()
# ---------------------------------------------------------------------------

def parse_intent(raw_text: str) -> dict:
    """
    Parse an incoming SMS message.

    Returns one of two shapes:

    A) Location message (user sent a place name):
       {
           "type": "location",
           "location": "brgy lahug, cebu city",
           "coordinates": {"lat": ..., "lon": ..., "source": ..., ...},
           "menu": <command menu string>,
       }

    B) Command message (user sent a known keyword):
       {
           "type": "command",
           "action": "flood" | "prep" | "travel" | "farm" | "why" | "loc" | "stop",
       }
    """
    text = raw_text.strip().lower()

    # Check if the entire message is a known command
    if text in KNOWN_COMMANDS:
        return {
            "type": "command",
            "action": KNOWN_COMMANDS[text],
        }

    # Otherwise treat the whole message as a location
    location = normalize_location(raw_text)
    coords = get_coordinates(location)

    return {
        "type": "location",
        "location": location,
        "coordinates": coords,
        "menu": COMMAND_MENU,
    }
