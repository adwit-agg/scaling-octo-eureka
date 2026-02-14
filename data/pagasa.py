"""
PAGASA Rainfall Forecast client.

Queries the PAGASA/Rainfall_Forecast raster layer on the GeoRisk portal
via ArcGIS Identify. Returns the official PAGASA rainfall forecast value
for a given coordinate.

Endpoint: https://portal.georisk.gov.ph/arcgis/rest/services/PAGASA/Rainfall_Forecast/MapServer/identify

The raster pixel value is a rainfall forecast in mm.
Official PAGASA classification (from the legend):
  Class 1:   0.001 –   40 mm
  Class 2:  40.001 –   80 mm
  Class 3:  80.001 –  120 mm
  Class 4: 120.001 – 1500 mm
"""

import requests
from dataclasses import dataclass

PAGASA_URL = (
    "https://portal.georisk.gov.ph/arcgis/rest/services"
    "/PAGASA/Rainfall_Forecast/MapServer/identify"
)
TIMEOUT_SECONDS = 10


@dataclass
class PagasaForecast:
    """Result from querying the PAGASA Rainfall Forecast layer."""
    rainfall_mm: float       # raw pixel value — forecast rainfall in mm
    pagasa_class: int        # 1-4 classification from PAGASA
    pagasa_class_label: str  # human label for the class
    available: bool          # False if the query failed


# PAGASA legend-based classification
PAGASA_CLASSES = {
    1: "Light (0–40mm)",
    2: "Moderate (40–80mm)",
    3: "Heavy (80–120mm)",
    4: "Intense (120mm+)",
}


def _classify_pagasa(mm: float) -> tuple[int, str]:
    """Classify rainfall mm into PAGASA's official 4-class scheme."""
    if mm <= 40:
        cls = 1
    elif mm <= 80:
        cls = 2
    elif mm <= 120:
        cls = 3
    else:
        cls = 4
    return cls, PAGASA_CLASSES[cls]


def fetch_pagasa_rainfall(lat: float, lon: float) -> PagasaForecast:
    """
    Query PAGASA Rainfall Forecast at (lat, lon).

    Uses the ArcGIS Identify operation on the raster layer.
    Returns a PagasaForecast with the pixel value and classification.
    """
    try:
        # Build a small mapExtent around the point (required by Identify)
        delta = 0.01
        extent = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"

        resp = requests.get(
            PAGASA_URL,
            params={
                "geometry": f'{{"x":{lon},"y":{lat},"spatialReference":{{"wkid":4326}}}}',
                "geometryType": "esriGeometryPoint",
                "sr": "4326",
                "layers": "all",
                "tolerance": 5,
                "mapExtent": extent,
                "imageDisplay": "800,600,96",
                "returnGeometry": "false",
                "f": "json",
            },
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            print(f"[PAGASA] No results for ({lat}, {lon})")
            return PagasaForecast(
                rainfall_mm=0.0,
                pagasa_class=0,
                pagasa_class_label="No data",
                available=False,
            )

        attrs = results[0].get("attributes", {})

        # The raster returns "Classify.Pixel Value" = rainfall in mm
        pixel_val = float(attrs.get("Classify.Pixel Value", 0))

        # Classify using PAGASA's own thresholds (not the "Class value" field
        # from the response, which seems unreliable — we compute it ourselves)
        pagasa_class, pagasa_label = _classify_pagasa(pixel_val)

        print(
            f"[PAGASA] ({lat}, {lon}) → "
            f"{pixel_val:.1f}mm → Class {pagasa_class}: {pagasa_label}"
        )

        return PagasaForecast(
            rainfall_mm=pixel_val,
            pagasa_class=pagasa_class,
            pagasa_class_label=pagasa_label,
            available=True,
        )

    except Exception as e:
        print(f"[PAGASA] Query failed: {e}")
        return PagasaForecast(
            rainfall_mm=0.0,
            pagasa_class=0,
            pagasa_class_label="Unavailable",
            available=False,
        )
