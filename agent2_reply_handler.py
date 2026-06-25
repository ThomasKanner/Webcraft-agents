"""
Agent 2 — Reply Handler + Demo Generator + Booking Agent
Monitors Instantly replies, classifies intent, sends demo, books meetings via Google Calendar
"""

import os
import json
import requests
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", "YOUR_INSTANTLY_API_KEY")
INSTANTLY_CAMPAIGN_ID = os.environ.get("INSTANTLY_CAMPAIGN_ID", "YOUR_CAMPAIGN_ID")
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")
YOUR_EMAIL = os.environ.get("YOUR_EMAIL", "you@yourdomain.com")
YOUR_NAME = os.environ.get("YOUR_NAME", "Your Name")
CALENDLY_LINK = os.environ.get("CALENDLY_LINK", "https://calendly.com/yourname/30min")
GOOGLE_CREDS_FILE = "google_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_google_calendar_service():
    creds = None
    if os.path.exists(GOOGLE_CREDS_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_CREDS_FILE, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open(GOOGLE_CREDS_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def fetch_new_replies():
    url = "https://api.instantly.ai/api/v1/emails/list"
    resp = requests.post(url, json={
        "api_key": INSTANTLY_API_KEY,
        "campaign_id": INSTANTLY_CAMPAIGN_ID,
        "type": "reply",
        "limit": 50
    }, timeout=15)
    resp.raise_for_status()
    return resp.json().get("emails", [])


def classify_reply(reply_text):
    prompt = f"""
Classify this email reply into exactly one of these categories:
- INTERESTED: they want to learn more, see a demo, or get pricing
- NOT_INTERESTED: they declined, unsubscribed, or said no
- OUT_OF_OFFICE: auto-reply or vacation message
- QUESTION: they asked a question but intent is unclear
- ALREADY_HAS_WEBSITE: they mentioned having a website

Reply: \"\"\"{reply_text}\"\"\"

Respond with ONLY the category label, nothing else.
"""
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 20,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=15
    )
    return resp.json()["content"][0]["text"].strip()


def generate_demo_url(business_name, industry):
    """
    Generate a demo preview URL.
    In production: call Durable.co API or a custom Next.js preview endpoint.
    Here we return a placeholder that your preview service would handle.
    """
    slug = business_name.lower().replace(" ", "-")[:30]
    return f"https://preview.yourwebcraftdomain.com/demo/{slug}"


def compose_demo_email(lead_name, business_name, industry, demo_url):
    prompt = f"""
Write a short, excited reply email to {lead_name} from {business_name} who expressed interest in getting a website.

Tell them:
1. You built a free mockup of their website (link: {demo_url})
2. Invite them to book a 15-min call to go over it and discuss pricing
3. Booking link: {CALENDLY_LINK}

Keep it under 5 sentences. Warm but professional. Sign off as "{YOUR_NAME} — WebCraft".
Return ONLY the email body.
"""
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 250,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=20
    )
    return resp.json()["content"][0]["text"].strip()


def send_reply_via_instantly(thread_id, to_email, body):
    url = "https://api.instantly.ai/api/v1/emails/reply"
    resp = requests.post(url, json={
        "api_key": INSTANTLY_API_KEY,
        "thread_id": thread_id,
        "to": to_email,
        "body": body
    }, timeout=15)
    resp.raise_for_status()


def create_calendar_event(service, prospect_name, prospect_email, meeting_time_iso):
    """Add a meeting to your Google Calendar when prospect books."""
    start = datetime.fromisoformat(meeting_time_iso)
    end = start + timedelta(minutes=30)
    event = {
        "summary": f"Sales call — {prospect_name}",
        "description": f"Website sales call with {prospect_name} ({prospect_email})\n\nBooked via AI agent.",
        "start": {"dateTime": start.isoformat(), "timeZone": "America/New_York"},
        "end": {"dateTime": end.isoformat(), "timeZone": "America/New_York"},
        "attendees": [{"email": prospect_email}, {"email": YOUR_EMAIL}],
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 60},
                {"method": "popup", "minutes": 15}
            ]
        }
    }
    result = service.events().insert(calendarId="primary", body=event, sendUpdates="all").execute()
    print(f"  Calendar event created: {result.get('htmlLink')}")
    return result


def handle_calendly_webhook(payload):
    """
    Webhook handler — call this from your Flask/FastAPI server when Calendly fires.
    Calendly sends a POST when a meeting is booked.
    """
    event_type = payload.get("event", "")
    if "invitee.created" not in event_type:
        return

    invitee = payload.get("payload", {}).get("invitee", {})
    scheduled_event = payload.get("payload", {}).get("scheduled_event", {})

    prospect_name = invitee.get("name", "Prospect")
    prospect_email = invitee.get("email", "")
    start_time = scheduled_event.get("start_time", "")

    service = get_google_calendar_service()
    create_calendar_event(service, prospect_name, prospect_email, start_time)
    print(f"  Booked: {prospect_name} at {start_time}")


def run_agent2():
    print(f"[{datetime.now()}] Agent 2 starting — checking replies")
    replies = fetch_new_replies()
    print(f"  Found {len(replies)} replies")

    for reply in replies:
        try:
            thread_id = reply.get("thread_id")
            to_email = reply.get("from_email")
            reply_text = reply.get("body", "")
            lead_name = reply.get("lead_first_name", "there")
            business_name = reply.get("company_name", "your business")
            industry = reply.get("category", "local business")

            intent = classify_reply(reply_text)
            print(f"  {to_email}: {intent}")

            if intent == "INTERESTED":
                demo_url = generate_demo_url(business_name, industry)
                email_body = compose_demo_email(lead_name, business_name, industry, demo_url)
                send_reply_via_instantly(thread_id, to_email, email_body)
                print(f"    Demo sent to {to_email}")

            elif intent == "QUESTION":
                prompt = f"Answer this question from a prospect about our web design service briefly and professionally:\n\n{reply_text}\n\nSign off as {YOUR_NAME} — WebCraft. Return only the email body."
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": CLAUDE_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": "claude-sonnet-4-6", "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]},
                    timeout=20
                )
                answer = resp.json()["content"][0]["text"].strip()
                send_reply_via_instantly(thread_id, to_email, answer)

        except Exception as e:
            print(f"  Error handling reply from {reply.get('from_email')}: {e}")

    print(f"[{datetime.now()}] Agent 2 done")


if __name__ == "__main__":
    run_agent2()
