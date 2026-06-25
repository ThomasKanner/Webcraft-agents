"""
Agent 3 — Website Builder
Takes a closed deal, builds a website via Durable.co API, delivers to customer.
"""

import os
import time
import requests
from datetime import datetime

CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")
DURABLE_API_KEY = os.environ.get("DURABLE_API_KEY", "YOUR_DURABLE_API_KEY")
INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", "YOUR_INSTANTLY_API_KEY")
YOUR_NAME = os.environ.get("YOUR_NAME", "Your Name")


def generate_website_brief(business_name, industry, location, notes=""):
    prompt = f"""
Create a concise website brief for a web builder AI.

Business: {business_name}
Industry: {industry}
Location: {location}
Additional notes: {notes}

Return a JSON object with these keys:
- headline: main hero headline (max 8 words)
- subheadline: supporting text (max 15 words)
- services: list of 3 services they likely offer
- tone: one of [professional, friendly, bold, elegant]
- color_theme: one of [blue, green, orange, purple, red, teal]
- about_blurb: 2-sentence about section

Return ONLY valid JSON, no markdown.
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
            "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30
    )
    import json
    text = resp.json()["content"][0]["text"].strip()
    return json.loads(text)


def build_website_durable(brief, business_name):
    """
    Call Durable.co API to generate the website.
    Durable's AI generates a full site from a business description.
    """
    url = "https://api.durable.co/v1/website/generate"
    headers = {
        "Authorization": f"Bearer {DURABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "business_name": business_name,
        "business_type": brief.get("industry", "local business"),
        "headline": brief.get("headline"),
        "description": brief.get("about_blurb"),
        "color_theme": brief.get("color_theme", "blue"),
        "services": brief.get("services", [])
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data.get("site_url"), data.get("site_id")


def send_delivery_email(customer_email, customer_name, business_name, site_url, campaign_id_or_thread):
    prompt = f"""
Write a warm, professional website delivery email to {customer_name} of {business_name}.

Tell them:
1. Their new website is live at: {site_url}
2. It's fully mobile-friendly and ready to use
3. Reply to this email if they want any changes
4. Their domain can be connected — you'll help with that

Keep it under 6 sentences. Excited but professional. Sign off as "{YOUR_NAME} — WebCraft".
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
    body = resp.json()["content"][0]["text"].strip()

    url = "https://api.instantly.ai/api/v1/emails/send"
    requests.post(url, json={
        "api_key": INSTANTLY_API_KEY,
        "to": customer_email,
        "subject": f"Your new website for {business_name} is live!",
        "body": body
    }, timeout=15)
    print(f"  Delivery email sent to {customer_email}")


def build_and_deliver(customer_email, customer_name, business_name, industry, location, notes=""):
    print(f"[{datetime.now()}] Agent 3 — building site for {business_name}")

    brief = generate_website_brief(business_name, industry, location, notes)
    print(f"  Brief generated: {brief.get('headline')}")

    site_url, site_id = build_website_durable(brief, business_name)
    print(f"  Site built: {site_url}")

    send_delivery_email(customer_email, customer_name, business_name, site_url, None)
    print(f"[{datetime.now()}] Agent 3 done — {business_name} site delivered")

    return site_url


if __name__ == "__main__":
    build_and_deliver(
        customer_email="owner@example.com",
        customer_name="John",
        business_name="Joe's Plumbing",
        industry="plumbing",
        location="Miami, FL",
        notes="Family-owned, 20 years experience"
    )
