import os
import csv
from urllib.parse import urlencode
from flask import Flask, request, render_template, jsonify
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

# Config from environment
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_NUMBER = os.getenv("TWILIO_NUMBER", "")
COMPANY_NAME = os.getenv("COMPANY_NAME", "SBFC Finance Ltd")
OFFICER_NAME = os.getenv("OFFICER_NAME", "Collection Officer")
OFFICER_NUMBER = os.getenv("OFFICER_NUMBER", "+910000000000")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
PORT = int(os.getenv("PORT", "5000"))

# Twilio client
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def build_script(payload: dict) -> str:
    name = payload.get("name", "Customer")
    loan_no = payload.get("loan_no", "your loan")
    amount = payload.get("amount", "the due amount")
    due_date = payload.get("due_date", "the due date")
    company = COMPANY_NAME
    officer = OFFICER_NAME
    officer_no = OFFICER_NUMBER

    text = f"""
    Namaste {name} ji. {company} se {officer} bol raha hu.
    Aapke loan number {loan_no} ke baare me important update hai.
    Aapka outstanding amount {amount} hai, jo {due_date} tak clear karna hai.
    Kripya payment jaldi karein taaki late fees, legal notice, ya account impact se bach sake.
    Agar aapne payment kar diya hai, to hume WhatsApp par receipt share karein.
    Kisi bhi madad ke liye hamara contact number hai {officer_no}.
    Dhanyavaad.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return " ".join(lines)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    decoded = file.stream.read().decode("utf-8", errors="ignore").splitlines()
    reader = csv.DictReader(decoded)
    rows = list(reader)
    if not rows:
        return jsonify({"ok": False, "error": "Empty CSV"}), 400

    placed = []
    for r in rows:
        payload = {
            "name": (r.get("name") or "").strip(),
            "phone": (r.get("phone") or "").strip(),
            "loan_no": (r.get("loan_no") or "").strip(),
            "amount": (r.get("amount") or "").strip(),
            "due_date": (r.get("due_date") or "").strip(),
        }
        voice_url = request.url_root.rstrip("/") + "/voice?" + urlencode(payload)

        if DRY_RUN:
            placed.append({"to": payload["phone"], "voice_url": voice_url, "dry_run": True})
        else:
            if not twilio_client:
                return jsonify({"ok": False, "error": "Twilio keys missing"}), 500
            try:
                call = twilio_client.calls.create(to=payload["phone"], from_=TWILIO_NUMBER, url=voice_url)
                placed.append({"to": payload["phone"], "sid": call.sid, "voice_url": voice_url})
            except Exception as e:
                placed.append({"to": payload["phone"], "error": str(e)})
    return jsonify({"ok": True, "count": len(placed), "placed": placed})

@app.route("/voice", methods=["POST", "GET"])
def voice():
    payload = {
        "name": request.values.get("name", "Customer"),
        "loan_no": request.values.get("loan_no", "your loan"),
        "amount": request.values.get("amount", "the due amount"),
        "due_date": request.values.get("due_date", "the due date"),
    }
    script = build_script(payload)

    vr = VoiceResponse()
    vr.say(script, language="en-IN")
    return str(vr)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
