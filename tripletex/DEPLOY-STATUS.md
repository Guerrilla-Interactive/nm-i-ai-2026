# Tripletex Agent — Deployment Status

> Updated: 2026-03-20 00:33 CET

## Current State: NOT DEPLOYED — Action Required

The FastAPI app runs locally on port 8080 and responds correctly, but we have no public HTTPS URL yet.

### What's running locally:
```
Server: http://localhost:8080
Health: curl http://localhost:8080/health → {"status":"ok","llm_mode":"none"}
PID: 97161
```

---

## Attempted Methods

### 1. GCP Cloud Run (BLOCKED — needs auth)
- `gcloud` CLI is installed but **no credentials configured**
- Need `@gcplab.me` credentials from the competition platform (app.ainm.no → team page → "Apply for GCP account")
- All team members must be Vipps-verified first

**To unblock (requires browser + interactive login):**
```bash
# 1. Get @gcplab.me credentials from competition dashboard
# 2. Login
gcloud auth login YOUR_EMAIL@gcplab.me

# 3. Set project (get project ID from Cloud Console after login)
gcloud config set project YOUR_PROJECT_ID

# 4. Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com

# 5. Deploy
cd /Users/pelle/Documents/github/nm-i-ai-2026/tripletex/app
gcloud run deploy tripletex-agent \
  --source . \
  --region europe-north1 \
  --allow-unauthenticated \
  --timeout 300 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 5 \
  --concurrency 1

# 6. Get URL
gcloud run services describe tripletex-agent --region europe-north1 --format='value(status.url)'
```

**Alternative: Use GCP Cloud Shell (no local gcloud needed):**
1. Go to console.cloud.google.com
2. Login with @gcplab.me account
3. Open Cloud Shell (terminal icon top-right)
4. `git clone` the repo or upload the `app/` folder
5. Run the deploy command above

### 2. cloudflared (FAILED — TLS error)
```
Error: tls: failed to verify certificate: x509: certificate is valid for globalconnect.dk,
*.broadnet.no... not api.trycloudflare.com
```
Likely ISP-level DNS/TLS interception issue. Not fixable from our side.

### 3. ngrok (FAILED — needs auth)
```
Error: ERR_NGROK_4018 — Usage of ngrok requires a verified account and authtoken.
```
Would need to create an ngrok account and set authtoken first.

---

## Recommended Next Steps (in order of speed)

### Fastest: GCP Cloud Shell (5 min)
1. Open https://console.cloud.google.com with @gcplab.me credentials
2. Click Cloud Shell icon (top right)
3. Upload or clone the app code
4. Run `gcloud run deploy` — Cloud Shell already has gcloud authenticated

### Alternative: Local gcloud auth (2 min after credentials)
```bash
gcloud auth login
gcloud config set project PROJECT_ID
cd /Users/pelle/Documents/github/nm-i-ai-2026/tripletex/app
gcloud run deploy tripletex-agent --source . --region europe-north1 --allow-unauthenticated --timeout 300 --memory 1Gi
```

### Fallback: ngrok (1 min after auth)
```bash
# Sign up at https://dashboard.ngrok.com/signup
# Get authtoken from https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_TOKEN
ngrok http 8080
```

---

## Competition Deployment Requirements

From https://app.ainm.no/docs/google-cloud/deploy:
- **Region:** `europe-north1` (Finland) for lowest latency to validators
- **Timeout:** 300 seconds
- **Endpoint:** POST /solve with JSON body
- **Auth:** Optional Bearer token (set in competition submission)
- **URL format:** `https://my-agent-xxxxx-lz.a.run.app`
- **Submit URL at:** app.ainm.no → Tripletex submission page

## Important: Endpoint Spec

The `/solve` endpoint receives:
```json
{
  "prompt": "Task description in Norwegian",
  "files": [{"filename": "...", "content_base64": "...", "mime_type": "..."}],
  "tripletex_credentials": {
    "base_url": "https://proxy-url/v2",
    "session_token": "..."
  }
}
```

Must return: `{"status": "completed"}` with HTTP 200.

**Critical:** All Tripletex API calls must go through the provided `base_url` proxy, NOT directly to `kkpqfuj-amager.tripletex.dev`.
