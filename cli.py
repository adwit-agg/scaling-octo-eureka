"""
cli.py -- Command-line test client for the SMS Flood Risk Assistant.

Simulates the SMS conversation loop locally without Twilio/Flask.
Enter a location to get a flood risk assessment, then use menu commands
(1-5, WHY, STOP, or word aliases) just like you would via SMS.

Usage:  python cli.py
"""

from pipeline import assess, handle_menu, is_menu_command
from parser.intent_parser import resolve_location


def main():
    session = {}  # {assessment, name, lat, lon}

    print("=== Flood Risk Assistant (CLI) ===")
    print("Type a location to get started, or a command (1-5, WHY, STOP).")
    print("Type 'quit' or 'exit' to leave.\n")

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not text:
            print("Send a location (e.g. 'Marikina') to get a flood risk assessment.\n")
            continue

        if text.lower() in ("quit", "exit"):
            print("Bye!")
            break

        # Menu command
        if is_menu_command(text):
            sms_text, _ = handle_menu(
                text,
                session.get("assessment"),
                session.get("name"),
            )
            print(f"\n{sms_text}\n")
            continue

        # Location
        location = resolve_location(text)
        assessment, sms_text, _ = assess(
            location["lat"], location["lon"], location["name"]
        )
        session = {
            "assessment": assessment,
            "name": location["name"],
            "lat": location["lat"],
            "lon": location["lon"],
        }
        print(f"\n{sms_text}\n")


if __name__ == "__main__":
    main()
