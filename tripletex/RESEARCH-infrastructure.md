# Infrastructure Research — Tripletex AI Accounting Agent

> GCP Cloud Run deployment guide. Copy-paste ready.

---

## 1. Architecture Overview

```
Judge (POST /solve) ──Basic Auth──▶ Cloud Run (FastAPI)
                                        │
                                        ├──▶ Gemini API (Vertex AI)
                                        └──▶ Tripletex Sandbox API
```

- **Runtime:** Python 3.12 + FastAPI + uvicorn
- **Region:** europe-north1 (Finland)
- **Timeout:** 300s (matches competition limit)
- **Auth:** Basic Auth on incoming requests

---

## 2. Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run sets PORT env var (default 8080)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**requirements.txt:**
```
fastapi==0.115.*
uvicorn[standard]==0.34.*
httpx==0.28.*
google-genai==1.*
```

> `google-genai` is the new unified Gemini SDK (replaces `google-generativeai` and Vertex AI SDK). Works with both API key and service account auth.

---

## 3. Basic Auth Implementation

The judges send `POST /solve` with Basic Auth. We validate against credentials we define.

```python
# auth.py
import secrets
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

def verify_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """Validate Basic Auth credentials from environment variables."""
    correct_username = os.environ["BASIC_AUTH_USER"]
    correct_password = os.environ["BASIC_AUTH_PASS"]

    username_ok = secrets.compare_digest(credentials.username, correct_username)
    password_ok = secrets.compare_digest(credentials.password, correct_password)

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials
```

```python
# In main.py
from auth import verify_auth

@app.post("/solve")
async def solve(request: Request, credentials=Depends(verify_auth)):
    body = await request.json()
    # ... handle task
```

**Where are credentials defined?** On the competition dashboard at https://app.ainm.no — you set your endpoint URL and Basic Auth credentials there. The judges use those credentials when calling your endpoint.

---

## 4. Gemini API Access from Cloud Run

### Option A: Vertex AI (Recommended for Cloud Run)

Uses the service account already attached to Cloud Run — **no API key needed**.

```python
from google import genai

# Vertex AI mode — uses service account automatically on Cloud Run
client = genai.Client(
    vertexai=True,
    project=os.environ["GCP_PROJECT"],
    location="europe-north1",
)

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
)
```

**Required IAM role:** The Cloud Run service account needs `roles/aiplatform.user`.

```bash
# Grant Vertex AI access to default compute service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

### Option B: AI Studio API Key (Simpler)

```python
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
)
```

### Which Gemini model?

| Model | Speed | Quality | Recommendation |
|-------|-------|---------|----------------|
| `gemini-2.0-flash` | ~1-3s | Good | **Default choice** — fast enough for 300s timeout, good reasoning |
| `gemini-2.0-flash-lite` | ~0.5-1s | OK | Simple tasks only |
| `gemini-2.5-pro-preview-03-25` | ~5-15s | Excellent | Complex Tier 3 tasks, or if flash isn't accurate enough |
| `gemini-2.5-flash-preview-04-17` | ~2-5s | Very good | Best balance if available |

**Start with `gemini-2.0-flash`** — it's fast, free on Vertex AI, and good enough for most accounting tasks. Upgrade to 2.5-pro for Tier 3 if needed.

### Structured Output / Function Calling

```python
from google.genai import types

# JSON mode for structured responses
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.0,  # deterministic for accounting
    ),
)

# Parse the JSON response
import json
result = json.loads(response.text)
```

---

## 5. Tripletex Session Token Management

Tripletex API auth: `Basic base64(0:<sessionToken>)`

Session tokens are created via the API and **expire at midnight CET on the specified expiration date**.

### Token Creation

```python
import httpx
import base64
from datetime import date, timedelta

TRIPLETEX_BASE = "https://kkpqfuj-amager.tripletex.dev/v2"

async def create_session_token(consumer_token: str, employee_token: str) -> str:
    """Create a new Tripletex session token."""
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{TRIPLETEX_BASE}/token/session/:create",
            params={
                "consumerToken": consumer_token,
                "employeeToken": employee_token,
                "expirationDate": (date.today() + timedelta(days=1)).isoformat(),
            },
        )
        resp.raise_for_status()
        return resp.json()["value"]["token"]
```

### Cache Strategy: **Create on startup + lazy refresh**

```python
import time
import asyncio

class TripletexAuth:
    def __init__(self, consumer_token: str, employee_token: str):
        self.consumer_token = consumer_token
        self.employee_token = employee_token
        self._token: str | None = None
        self._created_at: float = 0
        self._lock = asyncio.Lock()

    async def get_token(self) -> str:
        """Get a valid session token, creating a new one if needed."""
        async with self._lock:
            # Refresh if older than 20 hours (tokens last 24h)
            if self._token is None or (time.time() - self._created_at) > 72000:
                self._token = await create_session_token(
                    self.consumer_token, self.employee_token
                )
                self._created_at = time.time()
            return self._token

    async def get_auth_header(self) -> str:
        """Get the Basic auth header value."""
        token = await self.get_token()
        encoded = base64.b64encode(f"0:{token}".encode()).decode()
        return f"Basic {encoded}"
```

> **For the competition:** Since instances are ephemeral and short-lived, creating a token per cold start is fine. The 20h TTL refresh is a safety net.

---

## 6. Cloud Run Deployment

### Prerequisites

```bash
# Set project
export PROJECT_ID="your-gcp-project-id"  # from competition dashboard
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com
```

### Deploy Command (All-in-One)

```bash
# Deploy directly from source (no manual Docker build needed!)
gcloud run deploy tripletex-agent \
  --source . \
  --region europe-north1 \
  --allow-unauthenticated \
  --timeout 300 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 5 \
  --concurrency 1 \
  --set-env-vars "BASIC_AUTH_USER=team,BASIC_AUTH_PASS=yourpassword,GCP_PROJECT=$PROJECT_ID,TRIPLETEX_CONSUMER_TOKEN=xxx,TRIPLETEX_EMPLOYEE_TOKEN=xxx"
```

**Key flags explained:**

| Flag | Value | Why |
|------|-------|-----|
| `--source .` | Build from source | Skips manual `docker build` + `docker push` — GCP builds it for you |
| `--allow-unauthenticated` | Public | Judges need to reach the endpoint without GCP IAM auth |
| `--timeout 300` | 5 min | Competition allows up to 300s per task |
| `--memory 1Gi` | 1 GB RAM | Enough for Python + httpx + genai SDK |
| `--cpu 1` | 1 vCPU | Sufficient for I/O-bound work (API calls) |
| `--min-instances 1` | Always warm | Avoids cold start delay on first judge request |
| `--max-instances 5` | Scale up | Handle concurrent judge requests |
| `--concurrency 1` | 1 req/instance | **Each request gets its own instance** — simpler, no race conditions on shared state |

### Concurrency: Why 1?

- Each `/solve` request may take up to 300s
- Tasks involve multiple sequential API calls (Gemini + Tripletex)
- With `--concurrency 1`, each instance handles one request at a time
- Cloud Run auto-scales to more instances if judges send concurrent tasks
- Simpler code — no need to worry about shared state or locks

### Update Environment Variables (Without Redeploying)

```bash
gcloud run services update tripletex-agent \
  --region europe-north1 \
  --set-env-vars "KEY=value"
```

### Get the Deployed URL

```bash
gcloud run services describe tripletex-agent \
  --region europe-north1 \
  --format='value(status.url)'
```

Register this URL on the competition dashboard at https://app.ainm.no.

---

## 7. Logging & Debugging

### Structured Logging (Cloud Run → Cloud Logging)

Cloud Run automatically captures stdout/stderr. Use JSON format for structured logs:

```python
import json
import sys
import logging

class CloudRunHandler(logging.StreamHandler):
    """Emit JSON logs that Cloud Logging parses automatically."""
    def emit(self, record):
        log_entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "task_id"):
            log_entry["task_id"] = record.task_id
        if record.exc_info:
            log_entry["exception"] = self.format(record)
        print(json.dumps(log_entry), file=sys.stderr, flush=True)

# Setup
logger = logging.getLogger("tripletex")
logger.setLevel(logging.INFO)
logger.addHandler(CloudRunHandler())
```

### Log Requests and Responses

```python
@app.post("/solve")
async def solve(request: Request, credentials=Depends(verify_auth)):
    body = await request.json()
    task_id = body.get("taskId", "unknown")

    logger.info(f"Received task", extra={"task_id": task_id})
    logger.info(f"Task body: {json.dumps(body)}", extra={"task_id": task_id})

    try:
        result = await process_task(body)
        logger.info(f"Task completed: {json.dumps(result)}", extra={"task_id": task_id})
        return result
    except Exception as e:
        logger.error(f"Task failed: {e}", extra={"task_id": task_id})
        raise
```

### View Logs

```bash
# Tail live logs
gcloud run services logs tail tripletex-agent --region europe-north1

# Read recent logs
gcloud run services logs read tripletex-agent --region europe-north1 --limit 50

# Or in Cloud Console:
# https://console.cloud.google.com/run/detail/europe-north1/tripletex-agent/logs
```

---

## 8. Local Development & Testing

### Run Locally

```bash
# Install deps
pip install -r requirements.txt

# Set env vars
export BASIC_AUTH_USER=team
export BASIC_AUTH_PASS=testpass
export GCP_PROJECT=your-project
export TRIPLETEX_CONSUMER_TOKEN=xxx
export TRIPLETEX_EMPLOYEE_TOKEN=xxx

# Run
uvicorn main:app --reload --port 8080
```

### Test with curl

```bash
# Test Basic Auth
curl -X POST http://localhost:8080/solve \
  -u "team:testpass" \
  -H "Content-Type: application/json" \
  -d '{"taskId": "test-1", "prompt": "Create an employee named Test Person"}'
```

### Docker Locally

```bash
docker build -t tripletex-agent .
docker run -p 8080:8080 \
  -e BASIC_AUTH_USER=team \
  -e BASIC_AUTH_PASS=testpass \
  -e GCP_PROJECT=your-project \
  tripletex-agent
```

---

## 9. Deploy Script

Save as `deploy.sh` in the tripletex directory:

```bash
#!/usr/bin/env bash
set -euo pipefail

# ── Config ──
SERVICE_NAME="tripletex-agent"
REGION="europe-north1"
PROJECT_ID="${GCP_PROJECT:?Set GCP_PROJECT env var}"

echo ">>> Deploying $SERVICE_NAME to $REGION..."

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --allow-unauthenticated \
  --timeout 300 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 5 \
  --concurrency 1

URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format='value(status.url)')

echo ""
echo ">>> Deployed to: $URL"
echo ">>> Test: curl -X POST $URL/solve -u \$BASIC_AUTH_USER:\$BASIC_AUTH_PASS -H 'Content-Type: application/json' -d '{\"taskId\":\"test\"}'"
```

```bash
chmod +x deploy.sh
```

---

## 10. Quick-Start Checklist

1. [ ] Get GCP project ID from competition dashboard
2. [ ] `gcloud auth login` + `gcloud config set project PROJECT_ID`
3. [ ] Enable APIs: `gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com`
4. [ ] Grant Vertex AI access to service account (see Section 4)
5. [ ] Get Tripletex consumer + employee tokens from competition
6. [ ] Create `main.py`, `auth.py`, `requirements.txt`, `Dockerfile`
7. [ ] Test locally: `uvicorn main:app --reload --port 8080`
8. [ ] Deploy: `./deploy.sh`
9. [ ] Register URL + Basic Auth credentials on https://app.ainm.no
10. [ ] Tail logs: `gcloud run services logs tail tripletex-agent --region europe-north1`

---

## 11. Environment Variables Summary

| Variable | Description | Example |
|----------|-------------|---------|
| `BASIC_AUTH_USER` | Username for incoming judge requests | `team` |
| `BASIC_AUTH_PASS` | Password for incoming judge requests | `securepass123` |
| `GCP_PROJECT` | GCP project ID | `ainm-2026-team-42` |
| `TRIPLETEX_CONSUMER_TOKEN` | From competition dashboard | `abc123...` |
| `TRIPLETEX_EMPLOYEE_TOKEN` | From competition dashboard | `def456...` |
| `GEMINI_API_KEY` | Only if using AI Studio (not Vertex) | `AIza...` |

---

## 12. Cost & Limits

- **Cloud Run:** Free tier covers 2M requests/month + 360k vCPU-seconds. Competition traffic is negligible.
- **Gemini on Vertex AI:** Free tier for `gemini-2.0-flash` (15 RPM, 1M tokens/day). Likely sufficient for competition.
- **Artifact Registry:** Stores Docker images. Minimal cost.
- **min-instances=1:** Costs ~$0.05/hour for the always-on instance. Worth it to avoid cold starts.

---

## Key Decisions

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Language | Python + FastAPI | Team familiarity, fastest to deploy, best Gemini SDK |
| Gemini model | gemini-2.0-flash | Fast, free, good enough. Upgrade if accuracy matters |
| Concurrency | 1 req/instance | Simpler code, no shared state issues |
| Token caching | Lazy refresh at 20h | Simple, handles Cloud Run instance lifecycle |
| Auth method | Vertex AI (service account) | Zero config on Cloud Run, no API key to manage |
| Deploy method | `gcloud run deploy --source .` | No manual Docker build/push, fastest iteration |
