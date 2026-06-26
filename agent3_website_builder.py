"""
Agent 3 — Website Builder
Uses Claude to write a complete custom HTML/CSS website
then deploys it automatically to Netlify via API
"""

import os
import json
import base64
import zipfile
import tempfile
import requests
from datetime import datetime

CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")
NETLIFY_API_KEY = os.environ.get("NETLIFY_API_KEY", "YOUR_NETLIFY_API_KEY")
INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", "YOUR_INSTANTLY_API_KEY")
YOUR_NAME = os.environ.get("YOUR_NAME", "Thomas")


def generate_website_html(business_name, industry, location, notes=""):
    prompt = f"""You are an expert web designer. Create a complete, professional, beautiful single-page website for a local business.

Business name: {business_name}
Industry: {industry}
Location: {location}
Additional info: {notes}

Requirements:
- Write complete HTML with embedded CSS and no external dependencies
- Modern, clean design with a hero section, services, about, and contact sections
- Mobile responsive
- Professional color scheme appropriate for the industry
- Include the business name, location, and relevant services
- Add a contact form section
- Make it look like it cost $1,000+ to build
- Use Google Fonts via CDN link only

Return ONLY the complete HTML code starting with <!DOCTYPE html>, nothing else."""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 4000,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"].strip()


def deploy_to_netlify(html_content, site_name):
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        with zipfile.ZipFile(tmp.name, 'w') as zf:
            zf.writestr('index.html', html_content)
        zip_path = tmp.name

    with open(zip_path, 'rb') as f:
        resp = requests.post(
            "https://api.netlify.com/api/v1/sites",
            headers={
                "Authorization": f"Bearer {NETLIFY_API_KEY}",
                "Content-Type": "application/zip"
            },
            data=f,
            timeout=60
        )
    resp.raise_for_status()
    data = resp.json()
    site_id = data.get("id")
    site_url = data.get("ssl_url") or data.get("url")

    slug = site_name.lower().replace(" ", "-").replace("'", "")[:30]
    requests.patch(
        f"https://api.netlify.com/api/v1/sites/{site_id}",
        headers={"Authorization": f"Bearer {NETLIFY_API_KEY}"},
        json={"name": slug},
        timeout=30
    )

    return site_url, site_id


def send_delivery_email(customer_email, customer_name, business_name, site_url):
    prompt = f"""Write a warm, professional website delivery email to {customer_name} of {business_name}.

Tell them:
1. Their new website is live at: {site_url}
2. It's fully mobile-friendly and ready to use
3. Reply to this email if they want any changes
4. You can help connect their custom domain

Keep it under 6 sentences. Sign off as "{YOUR_NAME} — WebCraft".
Return ONLY the email body."""

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
    body = resp.json()["content"][0]["text"].strip()

    requests.post(
        "https://api.instantly.ai/api/v2/emails",
        headers={
            "Authorization": f"Bearer {INSTANTLY_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "to": customer_email,
            "subject": f"Your new website for {business_name} is live!",
            "body": {"text": body, "html": f"<p>{body.replace(chr(10), '<br>')}</p>"}
        },
        timeout=15
    )
    print(f"  Delivery email sent to {customer_email}")


def build_and_deliver(customer_email, customer_name, business_name, industry, location, notes=""):
    print(f"[{datetime.now()}] Agent 3 — building site for {business_name}")

    print("  Generating website with Claude...")
    html = generate_website_html(business_name, industry, location, notes)
    print(f"  Website generated ({len(html)} characters)")

    print("  Deploying to Netlify...")
    site_url, site_id = deploy_to_netlify(html, business_name)
    print(f"  Site live at: {site_url}")

    send_delivery_email(customer_email, customer_name, business_name, site_url)

    print(f"[{datetime.now()}] Agent 3 done — {business_name} delivered at {site_url}")
    return site_url


if __name__ == "__main__":
    build_and_deliver(
        customer_email="owner@example.com",
        customer_name="John",
        business_name="Joe's Plumbing",
        industry="plumbing",
        location="Miami, FL",
        notes="Family-owned, 20 years experience, emergency services"
    )
