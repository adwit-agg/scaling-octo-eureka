#!/usr/bin/env python3
"""
Test harness for the flood risk pipeline.

Tests each module independently, then the full pipeline end-to-end.
Run from repo root:  python -m tests.test_pipeline

Usage:
    python -m tests.test_pipeline                          # run all tests
    python -m tests.test_pipeline --quick                  # skip slow API calls
    python -m tests.test_pipeline --coord 14.6507 121.1029 "Marikina City"
    python -m tests.test_pipeline --demo                   # simulate a full SMS conversation
"""

import sys
import time

# ---------------------------------------------------------------------------
# Test coordinates
# ---------------------------------------------------------------------------
TEST_CASES = [
    # (lat, lon, name, expected_susceptibility_code)
    (14.6507, 121.1029, "Marikina City",    "VHF"),
    (10.3157, 123.8854, "Cebu City",        "LF"),
    (11.2543, 124.9600, "Tacloban City",    "HF"),
    (7.1907,  125.4553, "Davao City",       "MF"),
    (14.5995, 120.9842, "Manila",           None),
    (8.4542,  124.6319, "Cagayan de Oro",   None),
]


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# 1. Test PAGASA rainfall
# ---------------------------------------------------------------------------
def test_pagasa():
    section("TEST: PAGASA Rainfall Forecast")
    from data.pagasa import fetch_pagasa_rainfall

    lat, lon = 14.6507, 121.1029
    result = fetch_pagasa_rainfall(lat, lon)

    print(f"  Available:  {result.available}")
    print(f"  Rainfall:   {result.rainfall_mm:.1f} mm")
    print(f"  Class:      {result.pagasa_class} — {result.pagasa_class_label}")

    assert result.available, "PAGASA should return data for Marikina"
    assert result.rainfall_mm >= 0, "Rainfall should be non-negative"
    assert result.pagasa_class in (1, 2, 3, 4), f"Unexpected class: {result.pagasa_class}"
    print("  PASS")


# ---------------------------------------------------------------------------
# 2. Test Open-Meteo rainfall
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
    assert result.rain_6h_mm >= 0
    assert len(result.hourly_values) > 0
    print("  PASS")


# ---------------------------------------------------------------------------
# 3. Test MGB susceptibility
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

    # PAGASA rain classification
    cases = [
        (0, 0, "Light"), (20, 0, "Light"), (40, 0, "Light"),
        (41, 1, "Moderate"), (80, 1, "Moderate"),
        (81, 2, "Heavy"), (120, 2, "Heavy"),
        (121, 3, "Intense"), (200, 3, "Intense"),
    ]
    for mm, expected_trigger, expected_label in cases:
        trigger, label = classify_rain_pagasa(mm)
        status = "PASS" if trigger == expected_trigger else "FAIL"
        print(f"  {mm:>5.0f}mm → trigger={trigger} ({label:8s}) {status}")
        assert trigger == expected_trigger

    # Score → tier mapping
    print()
    tier_cases = [
        (1, 0, "SAFE"), (4, 0, "SAFE"),
        (1, 1, "WATCH"), (2, 1, "WATCH"), (3, 1, "WATCH"),
        (2, 2, "WARNING"), (3, 2, "WARNING"),
        (4, 2, "CRITICAL"), (4, 3, "CRITICAL"), (3, 3, "CRITICAL"),
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
# 5. Test response formatting — danger vs safe + menu footer
# ---------------------------------------------------------------------------
def test_response_format():
    section("TEST: Response Formatting (offline)")
    from risk.engine import RiskAssessment
    from risk.response import format_sms, format_twiml

    # CRITICAL — should be danger mode with DO NOW actions
    critical = RiskAssessment(
        tier="CRITICAL", score=12, susceptibility=4,
        suscept_label="Very High", suscept_source="mgb",
        rain_trigger=3, rain_label="Intense", rain_source="pagasa",
        rain_mm=150.0, rain_detail="PAGASA forecast: 150mm",
        forecast_available=True, description="High flood risk.",
    )
    sms = format_sms(critical, "Marikina City")
    assert "CRITICAL" in sms
    assert "DO NOW:" in sms
    assert "EVACUATE" in sms
    assert "Reply" in sms  # menu footer
    print(f"  CRITICAL response: {len(sms)} chars — has DO NOW + menu ✓")

    # SAFE — should be safe mode with full menu
    safe = RiskAssessment(
        tier="SAFE", score=0, susceptibility=1,
        suscept_label="Low", suscept_source="mgb",
        rain_trigger=0, rain_label="Light", rain_source="pagasa",
        rain_mm=10.0, rain_detail="PAGASA forecast: 10mm",
        forecast_available=True, description="No immediate flood risk.",
    )
    sms = format_sms(safe, "Cebu City")
    assert "SAFE" in sms
    assert "DO NOW:" not in sms  # no danger actions
    assert "1 Risk check" in sms  # full menu
    print(f"  SAFE response: {len(sms)} chars — has full menu, no actions ✓")

    # TwiML
    twiml = format_twiml(sms)
    assert twiml.startswith("<?xml")
    assert "<Response>" in twiml
    print(f"  TwiML wrapping ✓")

    print("  PASS")


# ---------------------------------------------------------------------------
# 6. Test menu commands (offline)
# ---------------------------------------------------------------------------
def test_menu_commands():
    section("TEST: Menu Commands (offline)")
    from risk.engine import RiskAssessment
    from pipeline import handle_menu

    # Create a mock assessment
    assessment = RiskAssessment(
        tier="WARNING", score=4, susceptibility=4,
        suscept_label="Very High", suscept_source="mgb",
        rain_trigger=1, rain_label="Moderate", rain_source="pagasa",
        rain_mm=55.0, rain_detail="PAGASA forecast: 55mm",
        forecast_available=True, description="Moderate flood risk.",
    )
    name = "Marikina City"

    # Test each menu command (number + word aliases)
    commands = {
        "1": ("FLOOD", "risk check (number)"),
        "flood": ("FLOOD", "risk check (word)"),
        "2": ("HOME PREP", "home prep (number)"),
        "prep": ("HOME PREP", "home prep (word)"),
        "3": ("TRAVEL", "travel (number)"),
        "travel": ("TRAVEL", "travel (word)"),
        "4": ("FARMER", "farmer (number)"),
        "farm": ("FARMER", "farmer (word)"),
        "why": ("WHY", "explainability"),
        "WHY": ("WHY", "case insensitive"),
        "stop": ("unsubscribed", "stop message"),
    }

    for cmd, (expected_text, desc) in commands.items():
        sms, twiml = handle_menu(cmd, assessment, name)
        found = expected_text.lower() in sms.lower()
        status = "PASS" if found else f"FAIL (missing '{expected_text}')"
        print(f"  Menu '{cmd:5s}' → {desc:30s} {status}")
        assert found, f"Expected '{expected_text}' in response to '{cmd}'"

    # Test no-session
    sms, twiml = handle_menu("2", None, None)
    assert "No location" in sms
    print(f"  Menu no-session → asks for location ✓")

    # Test STOP (no session needed)
    sms, twiml = handle_menu("stop", None, None)
    assert "unsubscribed" in sms.lower()
    print(f"  STOP no-session → still works ✓")

    print("  PASS")


# ---------------------------------------------------------------------------
# 7. Test command detection
# ---------------------------------------------------------------------------
def test_command_detection():
    section("TEST: Command Detection (offline)")
    from pipeline import is_menu_command

    menu_inputs = [
        "1", "2", "3", "4", "5", "WHY", "why", "STOP", "stop", " 2 ", " WHY ",
        "flood", "FLOOD", "prep", "travel", "farm", "loc", "LOC",
    ]
    location_inputs = ["Marikina", "Cebu City", "brgy lahug", "123", "hello", ""]

    for inp in menu_inputs:
        assert is_menu_command(inp), f"Should be menu: '{inp}'"
        print(f"  '{inp:10s}' → menu command ✓")

    for inp in location_inputs:
        assert not is_menu_command(inp), f"Should NOT be menu: '{inp}'"
        print(f"  '{inp:10s}' → location ✓")

    print("  PASS")


# ---------------------------------------------------------------------------
# 8. Full pipeline end-to-end
# ---------------------------------------------------------------------------
def test_full_pipeline():
    section("TEST: Full Pipeline (end-to-end, live APIs)")
    from pipeline import assess

    for lat, lon, name, _ in TEST_CASES[:4]:  # first 4 to save time
        t0 = time.time()
        assessment, sms_text, twiml = assess(lat, lon, name)
        elapsed = time.time() - t0

        print(f"  {name:20s} → {assessment.tier:8s} "
              f"(score={assessment.score:>2d}, rain={assessment.rain_mm:.0f}mm "
              f"[{assessment.rain_source}], suscept={assessment.suscept_label} "
              f"[{assessment.suscept_source}]) "
              f"[{elapsed:.1f}s]")

    print("  PASS")


# ---------------------------------------------------------------------------
# 9. Demo mode — simulate a full SMS conversation
# ---------------------------------------------------------------------------
def test_demo_conversation():
    section("DEMO: Simulated SMS Conversation")
    from pipeline import assess, handle_menu

    # Step 1: User texts "Marikina"
    print("  USER → Marikina")
    assessment, sms, _ = assess(14.6507, 121.1029, "Marikina City")
    print(f"  BOT  ←")
    for line in sms.split("\n"):
        print(f"         {line}")

    # Step 2: User replies "WHY"
    print(f"\n  USER → WHY")
    sms, _ = handle_menu("why", assessment, "Marikina City")
    print(f"  BOT  ←")
    for line in sms.split("\n"):
        print(f"         {line}")

    # Step 3: User replies "2" (Home prep)
    print(f"\n  USER → 2")
    sms, _ = handle_menu("2", assessment, "Marikina City")
    print(f"  BOT  ←")
    for line in sms.split("\n"):
        print(f"         {line}")

    # Step 4: User texts a new location
    print(f"\n  USER → Cebu City")
    assessment2, sms2, _ = assess(10.3157, 123.8854, "Cebu City")
    print(f"  BOT  ←")
    for line in sms2.split("\n"):
        print(f"         {line}")

    print("\n  DEMO COMPLETE")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = sys.argv[1:]

    if "--coord" in args:
        idx = args.index("--coord")
        lat, lon, name = float(args[idx+1]), float(args[idx+2]), args[idx+3]
        section(f"Single coordinate: {name} ({lat}, {lon})")
        from pipeline import assess
        assess(lat, lon, name)
        return

    if "--demo" in args:
        test_demo_conversation()
        return

    quick = "--quick" in args

    tests = [
        ("Risk Engine", test_risk_engine),
        ("Response Format", test_response_format),
        ("Menu Commands", test_menu_commands),
        ("Command Detection", test_command_detection),
    ]

    if not quick:
        tests += [
            ("PAGASA", test_pagasa),
            ("Open-Meteo", test_openmeteo),
            ("MGB Susceptibility", test_susceptibility),
            ("Full Pipeline", test_full_pipeline),
        ]

    passed = failed = 0
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
