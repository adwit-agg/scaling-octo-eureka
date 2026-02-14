"""
geocoder.py — 3-tier geocoding for Philippine barangays/cities.

Resolution chain (never fails, always returns coordinates):
  1. Local cache lookup       (instant, free)
  2. Nominatim / OSM          (free, no key, 1 req/sec)
  3. OpenCage                  (free tier, needs OPENCAGE_API_KEY)
  4. Closest-match fallback    (fuzzy match against cache keys)
"""

import json
import os
import time
import difflib
import math
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CACHE_PATH = os.path.join(os.path.dirname(__file__), "locations_cache.json")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OPENCAGE_URL = "https://api.opencagedata.com/geocode/v1/json"
API_TIMEOUT = 5  # seconds
NOMINATIM_USER_AGENT = "sms-flood-risk-ph/1.0"

# Manila as absolute last-resort default
DEFAULT_FALLBACK = {"lat": 14.5995, "lon": 120.9842, "name": "manila"}


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache() -> dict:
    """Load the JSON cache from disk."""
    if not os.path.exists(CACHE_PATH):
        return {}
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cache(cache: dict) -> None:
    """Persist the cache back to disk."""
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=4, ensure_ascii=False)


def lookup_cache(location: str) -> dict | None:
    """Return cached {lat, lon} for *location* or None."""
    cache = _load_cache()
    key = location.lower().strip()
    if key in cache:
        return cache[key]
    return None


def save_to_cache(location: str, lat: float, lon: float) -> None:
    """Write a new location → coords pair into the cache."""
    cache = _load_cache()
    cache[location.lower().strip()] = {"lat": lat, "lon": lon}
    _save_cache(cache)


# ---------------------------------------------------------------------------
# Tier 1 — Nominatim (OpenStreetMap)
# ---------------------------------------------------------------------------

def nominatim_geocode(location: str) -> dict | None:
    """
    Query Nominatim for *location* scoped to the Philippines.
    Returns {"lat": float, "lon": float} or None.
    """
    params = {
        "q": f"{location}, Philippines",
        "format": "json",
        "limit": 1,
        "countrycodes": "ph",
    }
    headers = {"User-Agent": NOMINATIM_USER_AGENT}
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=API_TIMEOUT)
        resp.raise_for_status()
        results = resp.json()
        if results:
            return {"lat": float(results[0]["lat"]), "lon": float(results[0]["lon"])}
    except (requests.RequestException, KeyError, IndexError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# Tier 2 — OpenCage
# ---------------------------------------------------------------------------

def opencage_geocode(location: str) -> dict | None:
    """
    Query OpenCage for *location* scoped to the Philippines.
    Requires OPENCAGE_API_KEY env var.  Returns {"lat": …, "lon": …} or None.
    """
    api_key = os.getenv("OPENCAGE_API_KEY")
    if not api_key:
        return None

    params = {
        "q": f"{location}, Philippines",
        "key": api_key,
        "limit": 1,
        "countrycode": "ph",
        "no_annotations": 1,
    }
    try:
        resp = requests.get(OPENCAGE_URL, params=params, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("results"):
            geo = data["results"][0]["geometry"]
            return {"lat": geo["lat"], "lon": geo["lng"]}
    except (requests.RequestException, KeyError, IndexError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# Tier 3 — Closest-match fallback (fuzzy + haversine)
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_closest_match(location: str) -> dict:
    """
    Fuzzy-match *location* against all cache keys using difflib.
    Returns {"lat", "lon", "name"} of the best match, or Manila as default.
    """
    cache = _load_cache()
    if not cache:
        return DEFAULT_FALLBACK

    key = location.lower().strip()

    # 1. Try fuzzy string match on cache keys
    matches = difflib.get_close_matches(key, cache.keys(), n=1, cutoff=0.5)
    if matches:
        matched_key = matches[0]
        coords = cache[matched_key]
        return {"lat": coords["lat"], "lon": coords["lon"], "name": matched_key}

    # 2. No fuzzy match — return Manila default
    return DEFAULT_FALLBACK


# ---------------------------------------------------------------------------
# Public API — get_coordinates()
# ---------------------------------------------------------------------------

def get_coordinates(location: str) -> dict:
    """
    Resolve *location* to coordinates.  **Always returns a result — never None.**

    Returns dict:
        lat         float
        lon         float
        source      "cache" | "nominatim" | "opencage" | "fallback"
        approximate bool   (True when using fallback)
        matched_to  str    (only present when approximate=True)
    """
    clean = location.lower().strip()

    # 0. Cache (instant)
    cached = lookup_cache(clean)
    if cached:
        return {
            "lat": cached["lat"],
            "lon": cached["lon"],
            "source": "cache",
            "approximate": False,
        }

    # 1. Nominatim (free, no key)
    coords = nominatim_geocode(clean)
    if coords:
        save_to_cache(clean, coords["lat"], coords["lon"])
        return {**coords, "source": "nominatim", "approximate": False}

    # Rate-limit politeness between geocoder calls
    time.sleep(0.2)

    # 2. OpenCage (free tier, needs key)
    coords = opencage_geocode(clean)
    if coords:
        save_to_cache(clean, coords["lat"], coords["lon"])
        return {**coords, "source": "opencage", "approximate": False}

    # 3. Closest known location (always succeeds)
    closest = find_closest_match(clean)
    return {
        "lat": closest["lat"],
        "lon": closest["lon"],
        "source": "fallback",
        "approximate": True,
        "matched_to": closest["name"],
    }
