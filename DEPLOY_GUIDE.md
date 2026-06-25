# WebCraft AI Agents — Deployment Guide

## Option A: Railway.app (Recommended — easiest, ~$5/mo)

### Step 1 — Push code to GitHub
1. Create a free account at github.com
2. Click "New repository" → name it `webcraft-agents` → set to Private
3. On your computer, open Terminal and run:

```bash
cd /path/to/your/agent/files
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/webcraft-agents.git
git push -u origin main
```

### Step 2 — Deploy on Railway
1. Go to railway.app and sign up (free)
2. Click "New Project" → "Deploy from GitHub repo"
3. Connect your GitHub account and select `webcraft-agents`
4. Railway auto-detects Python and starts building

### Step 3 — Add environment variables
In your Railway project dashboard:
1. Click your service → "Variables" tab
2. Add each of these one by one:

| Variable               | Where to find it                        |
|------------------------|-----------------------------------------|
| ANTHROPIC_API_KEY      | console.anthropic.com → API Keys        |
| INSTANTLY_API_KEY      | app.instantly.ai → Settings → API       |
| INSTANTLY_CAMPAIGN_ID  | Campaign URL in Instantly               |
| SITESCOUT_API_KEY      | sitescout.com → Account → API           |
| DURABLE_API_KEY        | durable.co → Settings → API            |
| CALENDLY_LINK          | Your Calendly booking URL               |
| YOUR_EMAIL             | Your email address                      |
| YOUR_NAME              | Your first name                         |

### Step 4 — Get your public URL
1. In Railway, click "Settings" → "Domains" → "Generate Domain"
2. You'll get a URL like: `https://webcraft-agents-production.up.railway.app`
3. Copy this URL — you need it for Calendly

### Step 5 — Set Calendly webhook
1. Go to calendly.com → Integrations → Webhooks
2. Add webhook URL: `https://YOUR-RAILWAY-URL/calendly-webhook`
3. Select event: "invitee.created"
4. Save

### Step 6 — Google Calendar one-time auth
This is the only manual step. On your LOCAL computer (not the server):
```bash
python agent2_reply_handler.py
```
A browser opens → log in with Google → approve access.
This creates `google_token.json`. Upload this file to Railway:
1. Railway dashboard → your service → "Files" tab
2. Upload `google_token.json`

That's it. Your agents are running 24/7.

---

## Option B: DigitalOcean App Platform (~$5/mo)

### Step 1 — Push code to GitHub (same as Railway Step 1 above)

### Step 2 — Create app on DigitalOcean
1. Go to cloud.digitalocean.com → Apps → "Create App"
2. Choose GitHub → select your `webcraft-agents` repo
3. DigitalOcean detects Python automatically
4. Set run command: `python main.py`
5. Choose the $5/mo "Basic" tier (512 MB RAM — plenty)

### Step 3 — Add environment variables
In the "Environment Variables" section during setup, add the same
variables listed in the Railway table above. Mark them as "Secret" type.

### Step 4 — Deploy
Click "Create Resources". Build takes ~2 minutes.
Your URL will be: `https://webcraft-agents-xxxxx.ondigitalocean.app`

### Step 5 — Set Calendly webhook
Same as Railway Step 5 above, using your DigitalOcean URL.

### Step 6 — Google Calendar auth
Same as Railway Step 6 above.

---

## Testing your deployment

After deploying, test each endpoint:

```bash
# Health check — should return {"status": "running"}
curl https://YOUR-URL/health

# Manually trigger Agent 3 (after closing a deal)
curl -X POST https://YOUR-URL/build-website \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "client@example.com",
    "customer_name": "John",
    "business_name": "Johns Plumbing",
    "industry": "plumbing",
    "location": "Miami FL",
    "notes": "Family owned 20 years"
  }'
```

## Monitoring

- Railway: dashboard shows live logs in real time
- DigitalOcean: Apps → your app → "Runtime Logs" tab
- Both show Agent 1 firing at 8am and Agent 2 every 30 minutes

## Updating the code

Any time you push to GitHub, both platforms auto-redeploy:
```bash
git add .
git commit -m "Update agents"
git push
```
