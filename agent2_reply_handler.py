"""
Agent 2 — Reply Handler + Demo Generator + Booking Agent
Uses Instantly.ai API V2 with Bearer token auth
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

INSTANTLY_HEADERS = {
    "Authorization": f"Bearer {INSTANTLY_API_KEY}",
    "Content-Type": "application/json"
}


def get_instantly_headers():
    return {
        "Authorization": f"Bearer {INSTANTLY_API_KEY}",
        "Content-Type": "application/json"
    }


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
    url = "https://api.instantly.ai/api/v2/emails"
    params = {
        "email_type": "received",
        "campaign_id": INSTANTLY_CAMPAIGN_ID,
        "limit": 50,
        "is_unread": true
    }
    resp = requests.get(url, headers=get_instantly_headers(), params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("items", data.get("data", []))


def classify_reply(reply_text):
    prompt = f"""Classify this email reply into exactly one of these categories:
- INTERESTED: they want to learn more, see a demo, or get pricing
- NOT_INTERESTED: they declined, unsubscribed, or said no
- OUT_OF_OFFICE: auto-reply or vacation message
- QUESTION: they asked a question but intent is unclear
- ALREADY_HAS_WEBSITE: they mentioned having a website

Reply: \"\"\"{reply_text}\"\"\"

Respond with ONLY the category label, nothing else."""

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


def generate_demo_url(business_name):
    slug = business_name.lower().replace(" ", "-")[:30]
    return f"https://preview.webcraft.com/demo/{slug}"


def claude_write(prompt):
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=20
    )
    return resp.json()["content"][0]["text"].strip()


def send_reply(email_id, eaccount, body):
    url = "https://api.instantly.ai/api/v2/emails/reply"
    payload = {
        "reply_to_uuid": email_id,
        "eaccount": eaccount,
        "body": {
            "text": body,
            "html": f"<p>{body.replace(chr(10), '<br>')}</p>"
        }
    }
    resp = requests.post(url, headers=get_instantly_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def create_calendar_event(service, prospect_name, prospect_email, meeting_time_iso):
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
    result = service.events().insert(
        calendarId="primary", body=event, sendUpdates="all"
    ).execute()
    print(f"  Calendar event created: {result.get('htmlLink')}")
    return result


def handle_calendly_webhook(payload):
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
            email_id = reply.get("id")
            eaccount = reply.get("eaccount", "")
            to_email = reply.get("from_address_email", "")
            reply_text = reply.get("body", {}).get("text", "") if isinstance(reply.get("body"), dict) else reply.get("body", "")
            lead_name = reply.get("lead_first_name", "there")
            business_name = reply.get("company_name", "your business")

            intent = classify_reply(reply_text)
            print(f"  {to_email}: {intent}")

            if intent == "INTERESTED":
                demo_url = generate_demo_url(business_name)
                body = claude_write(
                    f"Write a reply to {lead_name} of {business_name} who is interested in getting a website. "
                    f"Tell them you built a free mockup at {demo_url} and invite them to book a call at {CALENDLY_LINK}. "
                    f"Under 5 sentences. Sign off as {YOUR_NAME} — WebCraft. Return only email body."
                )
                send_reply(email_id, eaccount, body)
                print(f"    Demo sent to {to_email}")

            elif intent == "QUESTION":
                body = claude_write(
                    f"Answer this question from a prospect about our web design service briefly and professionally:\n\n"
                    f"{reply_text}\n\nSign off as {YOUR_NAME} — WebCraft. Return only the email body."
                )
                send_reply(email_id, eaccount, body)
                print(f"    Question answered for {to_email}")

        except Exception as e:
            print(f"  Error handling reply from {reply.get('from_address_email')}: {e}")

    print(f"[{datetime.now()}] Agent 2 done")


if __name__ == "__main__":
    run_agent2()
