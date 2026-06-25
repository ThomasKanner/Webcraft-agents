"""
Main entry point — runs Flask webhook server + scheduler in parallel threads
Deploy this on Railway or DigitalOcean and it runs 24/7
"""

import threading
import schedule
import time
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# Import agents (they read env vars at runtime)
import sys
sys.path.insert(0, os.path.dirname(__file__))

from agent1_lead_scraper import run_agent1
from agent2_reply_handler import run_agent2, handle_calendly_webhook
from agent3_website_builder import build_and_deliver

# ── Calendly webhook endpoint ──────────────────────────────────────────────
@app.route("/calendly-webhook", methods=["POST"])
def calendly_webhook():
    payload = request.get_json(force=True)
    try:
        handle_calendly_webhook(payload)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

# ── Manual trigger endpoint for Agent 3 ───────────────────────────────────
@app.route("/build-website", methods=["POST"])
def build_website():
    data = request.get_json(force=True)
    required = ["customer_email", "customer_name", "business_name", "industry", "location"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields", "required": required}), 400
    try:
        site_url = build_and_deliver(
            customer_email=data["customer_email"],
            customer_name=data["customer_name"],
            business_name=data["business_name"],
            industry=data["industry"],
            location=data["location"],
            notes=data.get("notes", "")
        )
        return jsonify({"status": "delivered", "site_url": site_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Health check ───────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running", "agents": ["agent1", "agent2", "agent3"]}), 200

# ── Scheduler thread ───────────────────────────────────────────────────────
def run_scheduler():
    schedule.every().day.at("08:00").do(run_agent1)
    schedule.every(30).minutes.do(run_agent2)
    print("Scheduler started — Agent 1 at 8am daily, Agent 2 every 30 min")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # Start scheduler in background thread
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()

    # Start Flask server (Calendly webhooks + Agent 3 trigger)
    port = int(os.environ.get("PORT", 5000))
    print(f"Server running on port {port}")
    app.run(host="0.0.0.0", port=port)
