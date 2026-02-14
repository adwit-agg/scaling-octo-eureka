#!/usr/bin/env python3
"""
Test harness for the flood risk pipeline.

Tests each module independently, then the full pipeline end-to-end.
Run from repo root:  python -m tests.test_pipeline

Usage:
    python -m tests.test_pipeline                          # run all tests
    python -m tests.test_pipeline --quick                  # skip slow API calls
    python -m tests.test_pipeline --coord 14.6507 121.1029 "Marikina City"
"""

import sys
import time

# ---------------------------------------------------------------------------
# Test coordinates — covering different susceptibility levels and regions
# ---------------------------------------------------------------------------
TEST_CASES = [
    # (lat, lon, name, expected_susceptibility_code)
    (14.6507, 121.1029, "Marikina City",    "VHF"),  # Very High — river basin
    (10.3157, 123.8854, "Cebu City",        "LF"),   # Low — elevated city center
    (11.2543, 124.9600, "Tacloban City",    "HF"),   # High — coastal, Haiyan-affected
    (7.1907,  125.4553, "Davao City",       "MF"),   # Moderate
    (14.5995, 120.9842, "Manila",           None),   # no expected — just verify it runs
    (8.4542,  124.6319, "Cagayan de Oro",   None),
]


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# 1. Test PAGASA rainfall (portal.georisk.gov.ph)
# ---------------------------------------------------------------------------
def test_pagasa():
    section("TEST: PAGASA Rainfall Forecast")
    from data.pagasa import fetch_pagasa_rainfall

    lat, lon = 14.6507, 121.1029  # Marikina
    result = fetch_pagasa_rainfall(lat, lon)

    print(f"  Available:  {result.available}")
    print(f"  Rainfall:   {result.rainfall_mm:.1f} mm")
    print(f"  Class:      {result.pagasa_class} — {result.pagasa_class_label}")

    assert result.available, "PAGASA should return data for Marikina"
    assert result.rainfall_mm >= 0, "Rainfall should be non-negative"
    assert result.pagasa_class in (1, 2, 3, 4), f"Unexpected class: {result.pagasa_class}"
    print("  PASS")


# ---------------------------------------------------------------------------
# 2. Test Open-Meteo rainfall (api.open-meteo.com)
# ---------------------------------------------------------------------------
def test_openmeteo():
    section("TEST: Open-Meteo Hourly Forecast")
    from data.weather import fetch_rainfall

    lat, lon = 14.6507, 121.1029
    result = fetch_rainfall(lat, lon)

    print(f"  Available:  {result.forecast_available}")
    print(f"  6hr total:  {result.rain_6h_mm:.1f} mm")
    print(f"  3hr total:  {result.rain_3h_mm:.1f} mm")
    print(f"  Peak hour:  {result.peak_hourly_mm:.1f} mm")
    print(f"  Hourly pts: {len(result.hourly_values)}")

    assert result.forecast_available, "Open-Meteo should return data"
    assert result.rain_6h_mm >= 0, "Rainfall should be non-negative"
    assert len(result.hourly_values) > 0, "Should have hourly values"
    print("  PASS")


# ---------------------------------------------------------------------------
# 3. Test MGB susceptibility (controlmap.mgb.gov.ph)
# ---------------------------------------------------------------------------
def test_susceptibility():
    section("TEST: MGB Flood Susceptibility")
    from data.susceptibility import get_susceptibility

    for lat, lon, name, expected in TEST_CASES:
        result = get_susceptibility(lat, lon)
        status = "PASS" if (expected is None or
            (expected == "VHF" and result.level == 4) or
            (expected == "HF" and result.level == 3) or
            (expected == "MF" and result.level == 2) or
            (expected == "LF" and result.level == 1)) else "MISMATCH"

        print(f"  {name:20s} → {result.label:10s} ({result.level}/4) "
              f"[source: {result.source}] {status}")

    print("  PASS (all queries returned)")


# ---------------------------------------------------------------------------
# 4. Test risk engine (pure logic, no API calls)
# ---------------------------------------------------------------------------
def test_risk_engine():
    section("TEST: Risk Engine (offline)")
    from risk.engine import assess_risk, classify_rain_pagasa

    # Verify PAGASA rain classification
    cases = [
        (0,   0, "Light"),
        (20,  0, "Light"),
        (40,  0, "Light"),
        (41,  1, "Moderate"),
        (80,  1, "Moderate"),
        (81,  2, "Heavy"),
        (120, 2, "Heavy"),
        (121, 3, "Intense"),
        (200, 3, "Intense"),
    ]
    for mm, expected_trigger, expected_label in cases:
        trigger, label = classify_rain_pagasa(mm)
        status = "PASS" if trigger == expected_trigger else "FAIL"
        print(f"  {mm:>5.0f}mm → trigger={trigger} ({label:8s}) {status}")
        assert trigger == expected_trigger, f"Expected {expected_trigger}, got {trigger}"

    # Verify score → tier mapping
    print()
    tier_cases = [
        # (suscept, rain_trigger, expected_tier)
        (1, 0, "SAFE"),
        (4, 0, "SAFE"),       # no rain = safe even in VH area
        (1, 1, "WATCH"),      # score 1
        (2, 1, "WATCH"),      # score 2
        (3, 1, "WATCH"),      # score 3
        (2, 2, "WARNING"),    # score 4
        (3, 2, "WARNING"),    # score 6
        (4, 2, "CRITICAL"),   # score 8
        (4, 3, "CRITICAL"),   # score 12
        (3, 3, "CRITICAL"),   # score 9
    ]
    for suscept, rain_trig, expected_tier in tier_cases:
        result = assess_risk(
            susceptibility=suscept, suscept_label="test", suscept_source="test",
            pagasa_mm=rain_trig * 40.0 + 0.1 if rain_trig > 0 else 0.0,
            pagasa_available=True,
            openmeteo_6h_mm=None, openmeteo_3h_mm=None,
            openmeteo_peak_mm=None, openmeteo_available=False,
        )
        status = "PASS" if result.tier == expected_tier else f"FAIL (got {result.tier})"
        print(f"  suscept={suscept} × rain={rain_trig} = score {result.score:>2d} → {result.tier:8s} {status}")
        assert result.tier == expected_tier

    print("  PASS")


# ---------------------------------------------------------------------------
# 5. Test response formatting (offline)
# ---------------------------------------------------------------------------
def test_response_format():
    section("TEST: Response Formatting (offline)")
    from risk.engine import RiskAssessment
    from risk.response import format_sms, format_twiml

    assessment = RiskAssessment(
        tier="CRITICAL", score=12, susceptibility=4,
        suscept_label="Very High", suscept_source="mgb",
        rain_trigger=3, rain_label="Intense", rain_source="pagasa",
        rain_mm=150.0, rain_detail="PAGASA forecast: 150mm",
        forecast_available=True, description="High flood risk. Act immediately.",
    )
    sms = format_sms(assessment, "Marikina City")
    twiml = format_twiml(sms)

    print(f"  SMS length: {len(sms)} chars")
    print(f"  Contains CRITICAL: {'CRITICAL' in sms}")
    print(f"  Contains EVACUATE: {'EVACUATE' in sms}")
    print(f"  TwiML starts with XML: {twiml.startswith('<?xml')}")
    print(f"  TwiML has <Response>: {'<Response>' in twiml}")
    print()
    print("  --- SMS preview ---")
    for line in sms.split("\n"):
        print(f"  | {line}")
    print("  ---")

    assert "CRITICAL" in sms
    assert "EVACUATE" in sms
    assert "PAGASA" in sms
    assert twiml.startswith("<?xml")
    print("  PASS")


# ---------------------------------------------------------------------------
# 6. Full pipeline end-to-end
# ---------------------------------------------------------------------------
def test_full_pipeline():
    section("TEST: Full Pipeline (end-to-end, live APIs)")
    from pipeline import assess

    for lat, lon, name, _ in TEST_CASES:
        t0 = time.time()
        assessment, sms_text, twiml = assess(lat, lon, name)
        elapsed = time.time() - t0

        print(f"  {name:20s} → {assessment.tier:8s} "
              f"(score={assessment.score:>2d}, rain={assessment.rain_mm:.0f}mm "
              f"[{assessment.rain_source}], suscept={assessment.suscept_label} "
              f"[{assessment.suscept_source}]) "
              f"[{elapsed:.1f}s]")

    print("  PASS (all cities assessed)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]

    if "--coord" in args:
        idx = args.index("--coord")
        lat = float(args[idx + 1])
        lon = float(args[idx + 2])
        name = args[idx + 3]
        section(f"Single coordinate: {name} ({lat}, {lon})")
        from pipeline import assess
        assess(lat, lon, name)
        return

    quick = "--quick" in args

    passed = 0
    failed = 0

    tests = [
        ("Risk Engine", test_risk_engine),
        ("Response Format", test_response_format),
    ]

    if not quick:
        tests += [
            ("PAGASA", test_pagasa),
            ("Open-Meteo", test_openmeteo),
            ("MGB Susceptibility", test_susceptibility),
            ("Full Pipeline", test_full_pipeline),
        ]

    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    section("SUMMARY")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
