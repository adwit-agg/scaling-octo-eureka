"""
Flood susceptibility lookup.

Given (lat, lon), queries MGB's Detailed Flood Susceptibility FeatureServer
at controlmap.mgb.gov.ph — the same polygon dataset that powers HazardHunterPH.

Returns one of: VHF (Very High), HF (High), MF (Moderate), LF (Low),
mapped to a 1-4 integer scale for the risk engine.

Endpoint:
  https://controlmap.mgb.gov.ph/arcgis/rest/services/
  GeospatialDataInventory/GDI_Detailed_Flood_Susceptibility/FeatureServer/0/query
"""

import requests
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# MGB Detailed Flood Susceptibility FeatureServer (live, query-enabled)
# ---------------------------------------------------------------------------
MGB_FLOOD_URL = (
    "https://controlmap.mgb.gov.ph/arcgis/rest/services"
    "/GeospatialDataInventory/GDI_Detailed_Flood_Susceptibility"
    "/FeatureServer/0/query"
)
MGB_TIMEOUT = 10  # seconds


@dataclass
class SusceptibilityResult:
    level: int         # 1=Low, 2=Medium, 3=High, 4=Very High
    label: str
    source: str        # "mgb" or "default"


# MGB field values → our 1-4 scale
FLOOD_SUSC_MAP = {
    "VHF": (4, "Very High"),
    "HF":  (3, "High"),
    "MF":  (2, "Moderate"),
    "LF":  (1, "Low"),
}

LEVEL_LABELS = {1: "Low", 2: "Moderate", 3: "High", 4: "Very High"}

DEFAULT_SUSCEPTIBILITY = 2  # Conservative default if API fails


def get_susceptibility(lat: float, lon: float) -> SusceptibilityResult:
    """
    Query MGB Detailed Flood Susceptibility for the given coordinate.

    Performs a point-in-polygon spatial query against the MGB FeatureServer.
    The response tells us exactly which flood susceptibility zone the
    coordinate falls in (VHF / HF / MF / LF).
    """
    try:
        resp = requests.get(
            MGB_FLOOD_URL,
            params={
                "geometry": f'{{"x":{lon},"y":{lat},"spatialReference":{{"wkid":4326}}}}',
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "FloodSusc",
                "returnGeometry": "false",
                "f": "json",
            },
            timeout=MGB_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            print(f"[SUSCEPTIBILITY] MGB: no polygon found at ({lat}, {lon}), using default")
            return SusceptibilityResult(
                level=DEFAULT_SUSCEPTIBILITY,
                label=LEVEL_LABELS[DEFAULT_SUSCEPTIBILITY],
                source="default",
            )

        code = features[0]["attributes"]["FloodSusc"]
        level, label = FLOOD_SUSC_MAP.get(code, (DEFAULT_SUSCEPTIBILITY, "Unknown"))

        print(f"[SUSCEPTIBILITY] MGB: ({lat}, {lon}) → {code} → {label} ({level}/4)")
        return SusceptibilityResult(level=level, label=label, source="mgb")

    except Exception as e:
        print(f"[SUSCEPTIBILITY] MGB query failed: {e} — using default")
        return SusceptibilityResult(
            level=DEFAULT_SUSCEPTIBILITY,
            label=LEVEL_LABELS[DEFAULT_SUSCEPTIBILITY],
            source="default",
        )
