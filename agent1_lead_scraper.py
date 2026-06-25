"""
Agent 1 — Lead Scraper + Email Composer
Pulls leads from D7 Lead Finder API, deduplicates, queues cold emails via Instantly.ai
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime

D7_API_KEY = os.environ.get("D7_API_KEY", "YOUR_D7_API_KEY")
INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", "YOUR_INSTANTLY_API_KEY")
INSTANTLY_CAMPAIGN_ID = os.environ.get("INSTANTLY_CAMPAIGN_ID", "YOUR_CAMPAIGN_ID")
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY")
SEEN_LEADS_FILE = "seen_leads.json"

SEARCH_TARGETS = [
    {"keyword": "plumber", "location": "Miami, FL"},
    {"keyword": "electrician", "location": "Miami, FL"},
    {"keyword": "hair salon", "location": "Miami, FL"},
    {"keyword": "restaurant", "location": "Miami, FL"},
    {"keyword": "auto repair", "location": "Miami, FL"},
    {"keyword": "cleaning service", "location": "Miami, FL"},
    {"keyword": "landscaping", "location": "Miami, FL"},
    {"keyword": "dentist", "location": "Miami, FL"},
    {"keyword": "roofing", "location": "Miami, FL"},
    {"keyword": "pest control", "location": "Miami, FL"},
]

def load_seen_leads():
    if os.path.exists(SEEN_LEADS_FILE):
        with open(SEEN_LEADS_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen_leads(seen):
    with open(SEEN_LEADS_FILE, "w") as f:
        json.dump(list(seen), f)

def search_d7_leads(keyword, location):
    url = "https://dash.d7leadfinder.com/api/search"
    params = {
        "key": D7_API_KEY,
        "q": keyword,
        "location": location,
        "country": "US"
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("search_id") or data.get("id")

def fetch_d7_results(search_id, retries=10, wait=15):
    url = "https://dash.d7leadfinder.com/api/results"
    for attempt in range(retries):
        resp = requests.get(url, params={"key": D7_API_KEY, "id": search_id}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", "")
        if status == "complete" or data.get("results"):
            return data.get("results", [])
        if status == "error":
            print(f"  D7 search error: {data}")
            return []
        print(f"  D7 search in progress... waiting {wait}s (attempt {attempt+1}/{retries})")
        time.sleep(wait)
    return []

def filter_no_website(leads):
    filtered = []
    for lead in leads:
        website = lead.get("website", "").strip()
        if not website or website in ("", "N/A", "n/a", "none", "null"):
            filtered.append(lead)
    return filtered

def deduplicate(leads, seen_ids):
    fresh = []
    for lead in leads:
        email = lead.get("email", "").strip().lower()
        if not email:
            continue
        uid = hashlib.md5(email.encode()).hexdigest()
        if uid not in seen_ids:
            lead["_uid"] = uid
            fresh.append(lead)
    return fresh

def generate_cold_email(lead):
    business_name = lead.get("name", "your business")
    category = lead.get("category", "local business")
    city = lead.get("city", "")
    prompt = f"""You are a professional web design agency outreach specialist.
Write a short, friendly cold email to a business owner who does NOT have a website yet.

Business name: {business_name}
Industry: {category}
Location: {city}

Rules:
- 3-4 sentences max
- No fluff, no "I hope this finds you well"
- Mention one specific benefit of having a website for their industry
- End with a soft CTA asking if they'd like to see a free mockup of their website
- Sign off as: "The WebCraft Team"

Return ONLY the email body, no subject line."""
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
    business = lead.get("name", "your business")
    subjects = [
        f"Quick question about {business}'s online presence",
        f"Free website mockup for {business}",
        f"Is {business} showing up on Google?",
    ]
    return subjects[hash(business) % len(subjects)]

def add_lead_to_instantly(lead, email_body, subject):
    url = "https://api.instantly.ai/api/v1/lead/add"
    payload = {
        "api_key": INSTANTLY_API_KEY,
        "campaign_id": INSTANTLY_CAMPAIGN_ID,
        "skip_if_in_workspace": True,
        "leads": [{
            "email": lead.get("email", "").strip(),
            "first_name": lead.get("owner_name", "").split()[0] if lead.get("owner_name") else "",
            "company_name": lead.get("name", ""),
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
    all_leads = []
    for target in SEARCH_TARGETS:
        if len(all_leads) >= daily_limit * 2:
            break
        try:
            print(f"  Searching D7: {target['keyword']} in {target['location']}")
            search_id = search_d7_leads(target["keyword"], target["location"])
            if not search_id:
                print(f"  No search ID returned for {target['keyword']}")
                continue
            results = fetch_d7_results(search_id)
            no_site = filter_no_website(results)
            print(f"  {len(results)} results → {len(no_site)} without website")
            all_leads.extend(no_site)
            time.sleep(5)
        except Exception as e:
            print(f"  Error searching {target['keyword']}: {e}")
    fresh = deduplicate(all_leads, seen)[:daily_limit]
    print(f"  Total fresh leads after dedup: {len(fresh)}")
    added = 0
    for lead in fresh:
        try:
            body = generate_cold_email(lead)
            subject = generate_subject_line(lead)
            add_lead_to_instantly(lead, body, subject)
            seen.add(lead["_uid"])
            added += 1
            print(f"  Queued: {lead.get('email')} ({lead.get('name')})")
            time.sleep(0.5)
        except Exception as e:
            print(f"  Error on {lead.get('email')}: {e}")
    save_seen_leads(seen)
    print(f"[{datetime.now()}] Agent 1 done — {added} leads queued in Instantly")

if __name__ == "__main__":
    run_agent1()
