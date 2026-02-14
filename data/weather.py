"""
Open-Meteo forecast client.

Given (lat, lon), returns rainfall metrics for the next few hours.
Free API, no key required.
"""

import requests
from dataclasses import dataclass


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 10


@dataclass
class RainfallForecast:
    """Rainfall summary for a single coordinate."""
    rain_6h_mm: float          # total precipitation in next 6 hours (mm)
    rain_3h_mm: float          # total precipitation in next 3 hours (mm)
    peak_hourly_mm: float      # max single-hour precipitation in next 6 hours
    hourly_values: list[float] # raw hourly mm list (up to 12 entries)
    forecast_available: bool   # False if API call failed


def fetch_rainfall(lat: float, lon: float) -> RainfallForecast:
    """
    Call Open-Meteo and return a RainfallForecast for the given coordinate.

    On failure (timeout, bad response, etc.) returns a "no data" forecast
    so the rest of the pipeline still works.
    """
    try:
        resp = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation",
                "forecast_hours": 12,
                "timezone": "Asia/Manila",
            },
            timeout=TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()

        hourly = data["hourly"]["precipitation"]
        # Guard against fewer entries than expected
        h6 = hourly[:6] if len(hourly) >= 6 else hourly
        h3 = hourly[:3] if len(hourly) >= 3 else hourly

        return RainfallForecast(
            rain_6h_mm=sum(h6),
            rain_3h_mm=sum(h3),
            peak_hourly_mm=max(h6) if h6 else 0.0,
            hourly_values=hourly,
            forecast_available=True,
        )

    except Exception as e:
        print(f"[WEATHER] Open-Meteo call failed: {e}")
        return RainfallForecast(
            rain_6h_mm=0.0,
            rain_3h_mm=0.0,
            peak_hourly_mm=0.0,
            hourly_values=[],
            forecast_available=False,
        )
