"""
app.py — Flask entry point for the SMS Flood Risk Assistant.

Exposes:
    POST /sms   — Twilio webhook (receives SMS, returns TwiML)
    GET  /health — Simple health check

Bridges:
    parser/  → resolves raw SMS text to (lat, lon, name)
    pipeline → runs risk assessment or handles menu commands
"""

import os
from flask import Flask, request
from dotenv import load_dotenv
from twilio.twiml.messaging_response import MessagingResponse

from pipeline import assess, handle_menu, is_menu_command
from parser.intent_parser import resolve_location
from risk.response import format_no_session, format_twiml

load_dotenv()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# In-memory session store: phone_number → {assessment, name, lat, lon}
# (In production, replace with Redis or a database.)
# ---------------------------------------------------------------------------
sessions: dict = {}


@app.route("/sms", methods=["POST"])
def sms_webhook():
    """
    Twilio webhook endpoint.

    Flow:
      1. Read Body + From from Twilio POST
      2. If Body is a menu command (1-4, flood, prep, etc.) → handle_menu()
      3. If Body is a location → resolve → assess() → store session
      4. Return TwiML response
    """
    body = request.form.get("Body", "").strip()
    from_number = request.form.get("From", "")

    # Empty message → help text
    if not body:
        resp = MessagingResponse()
        resp.message(
            "Send a location (e.g. 'Marikina' or 'Brgy Lahug, Cebu City') "
            "to get a flood risk assessment."
        )
        return str(resp), 200, {"Content-Type": "text/xml"}

    # --- Menu command ---
    if is_menu_command(body):
        session = sessions.get(from_number)
        if session:
            sms_text, twiml = handle_menu(
                body, session["assessment"], session["name"]
            )
        else:
            sms_text, twiml = handle_menu(body, None, None)

        return twiml, 200, {"Content-Type": "text/xml"}

    # --- Location ---
    location = resolve_location(body)

    print(
        f"[APP] Location resolved: {location['name']} "
        f"({location['lat']:.4f}, {location['lon']:.4f}) "
        f"[source: {location['source']}]"
    )

    # Run the full risk pipeline
    assessment, sms_text, twiml = assess(
        location["lat"], location["lon"], location["name"]
    )

    # Store session for menu follow-ups
    sessions[from_number] = {
        "assessment": assessment,
        "name": location["name"],
        "lat": location["lat"],
        "lon": location["lon"],
    }

    return twiml, 200, {"Content-Type": "text/xml"}


@app.route("/health", methods=["GET"])
def health():
    """Simple health check."""
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
