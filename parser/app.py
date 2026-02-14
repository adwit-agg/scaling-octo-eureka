"""
app.py — Flask entry point for the SMS Flood Risk Assistant.

Exposes a /sms POST webhook that Twilio calls when an SMS arrives.
Delegates parsing to intent_parser and returns an appropriate TwiML response.
"""

import os
from flask import Flask, request
from dotenv import load_dotenv
from twilio.twiml.messaging_response import MessagingResponse

from intent_parser import parse_intent, COMMAND_MENU

load_dotenv()

app = Flask(__name__)


def _format_location_reply(parsed: dict) -> str:
    """Build the SMS reply for a location resolution."""
    coords = parsed["coordinates"]
    lat = coords["lat"]
    lon = coords["lon"]
    source = coords.get("source", "unknown")
    location = parsed["location"]

    lines = []

    if coords.get("approximate"):
        matched = coords.get("matched_to", "unknown")
        lines.append(
            f"Could not find \"{location}\" exactly.\n"
            f"Showing closest match: {matched}"
        )
    else:
        lines.append(f"Location set: {location}")

    lines.append(f"Coordinates: {lat:.4f}, {lon:.4f}")
    lines.append(f"(source: {source})")
    lines.append("")
    lines.append(COMMAND_MENU)

    return "\n".join(lines)


def _format_command_reply(parsed: dict) -> str:
    """Build the SMS reply for a command action (placeholder for downstream modules)."""
    action = parsed["action"]

    # These will be wired to real risk/prep/travel/farm modules later.
    replies = {
        "flood":  "Running risk assessment for your location... (coming soon)",
        "prep":   "Home prep checklist for your area... (coming soon)",
        "travel": "Travel safety info for your area... (coming soon)",
        "farm":   "Farmer guidance for your area... (coming soon)",
        "why":    "Risk explanation for your area... (coming soon)",
        "loc":    "Send your new location and I'll update your coordinates.",
        "stop":   "You have been unsubscribed. Send any location to re-subscribe.",
    }

    return replies.get(action, "Unknown command.\n" + COMMAND_MENU)


@app.route("/sms", methods=["POST"])
def sms_webhook():
    """
    Twilio webhook endpoint.
    Receives incoming SMS, parses intent, replies with coordinates or command response.
    """
    body = request.form.get("Body", "").strip()
    # from_number = request.form.get("From", "")  # for user profiles later

    if not body:
        resp = MessagingResponse()
        resp.message("Send a location (e.g. 'Brgy Lahug, Cebu City') to get started.\n\n" + COMMAND_MENU)
        return str(resp), 200, {"Content-Type": "text/xml"}

    parsed = parse_intent(body)

    if parsed["type"] == "location":
        reply_text = _format_location_reply(parsed)
    else:
        reply_text = _format_command_reply(parsed)

    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp), 200, {"Content-Type": "text/xml"}


@app.route("/health", methods=["GET"])
def health():
    """Simple health check."""
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
