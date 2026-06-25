"""
Agent 1 — Lead Scraper + Email Composer
Pulls leads from SiteScout, deduplicates, and queues cold emails via Instantly.ai
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime

SITESCOUT_API_KEY = os.environ.get("SITESCOUT_API_KEY", "YOUR_SITESCOUT_API_KEY")
INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", "YOUR_INSTANTLY_API_KEY")
INSTANTLY_CAMPAIGN_ID = os.environ.get("INSTANTLY_CAMPAIGN_ID", "YOUR_CAMPAIGN_ID")
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")
SEEN_LEADS_FILE = "seen_leads.json"


def load_seen_leads():
    if os.path.exists(SEEN_LEADS_FILE):
        with open(SEEN_LEADS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_leads(seen):
    with open(SEEN_LEADS_FILE, "w") as f:
        json.dump(list(seen), f)


def fetch_leads_from_sitescout(limit=270):
    """
    Pull businesses with no website from SiteScout.
    Adjust filter params to match SiteScout's actual API schema.
    """
    url = "https://api.sitescout.com/v1/businesses"
    headers = {"Authorization": f"Bearer {SITESCOUT_API_KEY}"}
    params = {
        "has_website": False,
        "limit": limit,
        "status": "active"
    }
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("businesses", [])


def deduplicate(leads, seen_ids):
    fresh = []
    for lead in leads:
        uid = hashlib.md5(lead.get("email", lead.get("id", "")).encode()).hexdigest()
        if uid not in seen_ids:
            lead["_uid"] = uid
            fresh.append(lead)
    return fresh


def generate_cold_email(lead):
    """Use Claude to write a personalised cold email for this lead."""
    prompt = f"""
You are a professional web design agency outreach specialist.
Write a short, friendly cold email to a business owner who does NOT have a website yet.

Business name: {lead.get('business_name', 'your business')}
Industry: {lead.get('category', 'local business')}
Location: {lead.get('city', '')}, {lead.get('state', '')}

Rules:
- 3-4 sentences max
- No fluff, no "I hope this finds you well"
- Mention one specific benefit of having a website for their industry
- End with a soft CTA asking if they'd like to see a free mockup
- Sign off as: "The WebCraft Team"

Return ONLY the email body, no subject line.
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
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"].strip()


def generate_subject_line(lead):
    business = lead.get("business_name", "your business")
    subjects = [
        f"Quick question about {business}'s online presence",
        f"Free website mockup for {business}",
        f"Is {business} on Google yet?",
    ]
    idx = hash(business) % len(subjects)
    return subjects[idx]


def add_lead_to_instantly(lead, email_body, subject):
    """Push a single lead + personalised email into Instantly campaign."""
    url = "https://api.instantly.ai/api/v1/lead/add"
    payload = {
        "api_key": INSTANTLY_API_KEY,
        "campaign_id": INSTANTLY_CAMPAIGN_ID,
        "skip_if_in_workspace": True,
        "leads": [{
            "email": lead.get("email"),
            "first_name": lead.get("owner_first_name", ""),
            "last_name": lead.get("owner_last_name", ""),
            "company_name": lead.get("business_name", ""),
            "custom_variables": {
                "personalized_email": email_body,
                "subject_line": subject
            }
        }]
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def run_agent1(daily_limit=270):
    print(f"[{datetime.now()}] Agent 1 starting — target {daily_limit} leads")
    seen = load_seen_leads()
    leads = fetch_leads_from_sitescout(limit=daily_limit * 2)
    fresh = deduplicate(leads, seen)[:daily_limit]
    print(f"  Fetched {len(leads)} leads, {len(fresh)} are new")

    added = 0
    for lead in fresh:
        try:
            body = generate_cold_email(lead)
            subject = generate_subject_line(lead)
            add_lead_to_instantly(lead, body, subject)
            seen.add(lead["_uid"])
            added += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"  Error on lead {lead.get('email')}: {e}")

    save_seen_leads(seen)
    print(f"[{datetime.now()}] Agent 1 done — {added} leads queued in Instantly")


if __name__ == "__main__":
    run_agent1()
