"""
Agent 3 — Website Builder
Uses Claude to write a complete custom HTML/CSS website
then deploys it automatically to Netlify via API
"""

import os
import re
import hashlib
import requests
from datetime import datetime

CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")
NETLIFY_API_KEY = os.environ.get("NETLIFY_API_KEY", "YOUR_NETLIFY_API_KEY")
INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", "YOUR_INSTANTLY_API_KEY")
YOUR_NAME = os.environ.get("YOUR_NAME", "Thomas")


def generate_website_html(business_name, industry, location, notes=""):
    prompt = f"""Build a one-page website for "{business_name}", a {industry} business in {location}. {notes}

Return ONE complete HTML file. Budget your length so the FULL page fits — the body content is the priority, keep the CSS compact.

CRITICAL STRUCTURE (must appear in this order, all tags present):
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>...</title>
<style>
/* keep CSS concise - under 150 lines */
</style>
</head>
<body>
<!-- header, hero, services, about, contact sections with REAL text content -->
</body>
</html>

HARD RULES:
- The <style> block MUST be closed with </style> before <body>.
- The page MUST have a <body> with visible text: business name, a headline, 3-4 services, an about paragraph, and contact info (phone, address, email).
- NO opacity:0, NO display:none, NO visibility:hidden, NO animations that hide content, NO JavaScript needed to display anything.
- White or light background, dark text, fully visible on load.
- Keep CSS compact so the whole document completes. Finish with </body></html>.

Output ONLY the HTML, no explanation, no markdown fences."""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=120
    )
    resp.raise_for_status()
    html = resp.json()["content"][0]["text"].strip()

    if html.startswith("```"):
        html = re.sub(r'^```[a-zA-Z]*\n', '', html)
        html = re.sub(r'\n```$', '', html)

    if "<body" not in html.lower() or "</html>" not in html.lower():
        raise ValueError("Generated HTML is incomplete. Retry.")

    return html.strip()


def deploy_to_netlify(html_content, site_name):
    slug = site_name.lower().replace(" ", "-").replace("'", "")[:30]
    html_bytes = html_content.encode("utf-8")
    sha1 = hashlib.sha1(html_bytes).hexdigest()

    resp = requests.post(
        "https://api.netlify.com/api/v1/sites",
        headers={
            "Authorization": f"Bearer {NETLIFY_API_KEY}",
            "Content-Type": "application/json"
        },
        json={"name": slug},
        timeout=30
    )
    resp.raise_for_status()
    site_id = resp.json().get("id")
    site_url = resp.json().get("ssl_url") or resp.json().get("url")

    resp2 = requests.post(
        f"https://api.netlify.com/api/v1/sites/{site_id}/deploys",
        headers={
            "Authorization": f"Bearer {NETLIFY_API_KEY}",
            "Content-Type": "application/json"
        },
        json={"files": {"/index.html": sha1}},
        timeout=30
    )
    resp2.raise_for_status()
    deploy_id = resp2.json().get("id")
    required = resp2.json().get("required", [])

    if sha1 in required:
        resp3 = requests.put(
            f"https://api.netlify.com/api/v1/deploys/{deploy_id}/files/index.html",
            headers={
                "Authorization": f"Bearer {NETLIFY_API_KEY}",
                "Content-Type": "text/html; charset=utf-8"
            },
            data=html_bytes,
            timeout=60
        )
        resp3.raise_for_status()

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
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=60
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
        customer_name="Thomas",
        business_name="Miami Plumbing Experts",
        industry="plumbing",
        location="Miami, FL",
        notes="Family-owned, emergency services, licensed and insured"
    )
