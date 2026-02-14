"""
intent_parser.py — Location resolver for SMS input.

Takes raw SMS text, normalizes it, and resolves to coordinates
via the 3-tier geocoder. Command detection is handled by pipeline.py.

Public API:
    resolve_location(raw_text) → {lat, lon, name, source, approximate, ...}
    normalize_location(raw)    → cleaned location string
"""

from parser.geocoder import get_coordinates


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

    # Collapse multiple spaces
    text = " ".join(text.split())
    return text


# ---------------------------------------------------------------------------
# Public API — resolve_location()
# ---------------------------------------------------------------------------

def resolve_location(raw_text: str) -> dict:
    """
    Resolve raw SMS text to coordinates.

    Returns dict:
        lat         float
        lon         float
        name        str    (normalized location string used for geocoding)
        source      "cache" | "nominatim" | "opencage" | "fallback"
        approximate bool   (True when using fallback)
        matched_to  str    (only present when approximate=True)
    """
    name = normalize_location(raw_text)
    coords = get_coordinates(name)

    return {
        "lat": coords["lat"],
        "lon": coords["lon"],
        "name": name,
        "source": coords["source"],
        "approximate": coords["approximate"],
        **( {"matched_to": coords["matched_to"]} if coords.get("matched_to") else {} ),
    }
