# API & Infrastructure Research — NM i AI 2026

> Compiled: 2026-03-19
> Sources: app.ainm.no/docs/*, api.ainm.no, existing RESEARCH-*.md files

---

## 1. Competition Overview

- **Dates:** March 19 18:00 CET → March 22 15:00 CET (69 hours)
- **Prize pool:** 1,000,000 NOK
- **Platform:** https://app.ainm.no
- **API Base:** https://api.ainm.no
- **3 tasks** weighted equally (33% each)

---

## 2. Authentication

### JWT Token (Astar Island API)
- Login at https://app.ainm.no → sets `access_token` cookie (JWT)
- Use as **cookie** or extract and send as **Bearer token**:
  ```
  Authorization: Bearer <jwt-token>
  ```
- Cookie name: `access_token`

### Basic Auth (Tripletex API)
- Username: `0` (literal zero)
- Password: `session_token` (provided per submission)
- Header: `Authorization: Basic base64("0:" + session_token)`
- Python: `auth = ("0", session_token)`

### Endpoint Protection (Optional)
- When submitting your endpoint URL, you can set an API key
- The platform sends: `Authorization: Bearer <your-api-key>`

---

## 3. Astar Island API

**Base URL:** `https://api.ainm.no/astar-island/`

**Auth:** JWT cookie or `Authorization: Bearer <token>` from app.ainm.no

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/rounds` | List all active/completed rounds with status and timing |
| GET | `/rounds/{round_id}` | Round details + initial map states for all 5 seeds |
| GET | `/budget` | Check remaining query budget (50/round) |
| POST | `/simulate` | Run one simulation viewport query (costs 1 budget) |
| POST | `/submit` | Submit prediction for one seed |
| GET | `/my-rounds` | Team-specific round data with scores, rank, budget |
| GET | `/my-predictions/{round_id}` | Your team's submitted predictions |
| GET | `/analysis/{round_id}/{seed_index}` | Post-round comparison: prediction vs ground truth |
| GET | `/leaderboard` | Public leaderboard (best round score all time) |

### POST /simulate — Request
```json
{
  "round_id": "string",
  "seed_index": 0,        // 0-4
  "viewport": {
    "x": 10,
    "y": 10,
    "width": 15,          // max 15
    "height": 15          // max 15
  }
}
```

### POST /simulate — Response
```json
{
  "grid": [[...]],        // viewport cells with terrain types
  "settlements": [...],   // settlements within viewport
  "width": 15,
  "height": 15,
  "viewport": {"x": 10, "y": 10, "width": 15, "height": 15}
}
```

### POST /submit — Request
```json
{
  "round_id": "string",
  "seed_index": 0,
  "prediction": [[[0.8, 0.05, 0.02, 0.02, 0.06, 0.05], ...], ...]
}
```
- `prediction[y][x][class]` — 3D array (40×40×6)
- 6 classes: 0=Empty/Ocean/Plains, 1=Settlement, 2=Port, 3=Ruin, 4=Forest, 5=Mountain
- Each cell's 6 probabilities must sum to 1.0 (±0.01)
- **NEVER use 0.0** — floor at ≥0.01, then renormalize

### Rate Limits
- 10 requests/second per endpoint
- 429 Too Many Requests if exceeded
- 50 queries per round (shared across 5 seeds)

### Scoring
- KL divergence: `Σ p_i × log(p_i / q_i)`
- Score: `100 × exp(-mean_KL_divergence)`
- Only dynamic cells count (entropy-weighted)
- Range: 0–100 per seed; round score = avg of 5 seeds

---

## 4. Tripletex API (Competition)

### Competition Flow
1. You register your HTTPS endpoint URL + optional API key at app.ainm.no
2. Platform sends `POST /solve` to your endpoint with task prompt + credentials
3. You call Tripletex API via the provided proxy URL
4. You return `{"status": "completed"}`

### POST /solve — Your Endpoint Receives
```json
{
  "prompt": "Create employee Ola Nordmann with email ola@example.com",
  "files": [
    {
      "filename": "faktura.pdf",
      "content_base64": "base64...",
      "mime_type": "application/pdf"
    }
  ],
  "tripletex_credentials": {
    "base_url": "https://tx-proxy.ainm.no/v2",
    "session_token": "abc123..."
  }
}
```

### Your Response
```json
{"status": "completed"}
```
- HTTP 200 within 300 seconds
- Content-Type: application/json

### Tripletex v2 REST API Endpoints

**Base URL (sandbox):** `https://kkpqfuj-amager.tripletex.dev/v2`
**Base URL (competition):** provided via `tripletex_credentials.base_url`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/employee` | List/search employees |
| POST | `/employee` | Create employee |
| PUT | `/employee/{id}` | Update employee |
| DELETE | `/employee/{id}` | Delete employee |
| GET | `/customer` | List/search customers |
| POST | `/customer` | Create customer |
| PUT | `/customer/{id}` | Update customer |
| POST | `/product` | Create product |
| POST | `/order` | Create order |
| PUT | `/order/{id}/:invoice` | Convert order to invoice |
| POST | `/invoice` | Create invoice |
| POST | `/travelExpense` | Create travel expense |
| POST | `/travelExpense/cost` | Add cost to travel expense |
| DELETE | `/travelExpense/{id}` | Delete travel expense |
| POST | `/project` | Create project |
| POST | `/department` | Create department |
| POST | `/payment` | Register payment |
| PUT | `/token/session/:create` | Create session token |

### Query Parameters
- `fields` — field selection: `?fields=id,firstName,lastName`
- `from` — pagination start: `?from=0`
- `count` — items per page: `?count=100`
- Search: `?name=Ola`, `?email=ola@example.com`

### Response Format (list endpoints)
```json
{
  "fullResultSize": 42,
  "from": 0,
  "count": 100,
  "values": [{"id": 1, "firstName": "Ola", ...}]
}
```

### Auth to Tripletex
```python
import httpx
auth = ("0", session_token)
resp = httpx.get(f"{base_url}/employee", auth=auth)
```

### Rate Limits
| Limit | Verified Teams | Unverified |
|-------|---------------|------------|
| Concurrent submissions | 3 | 1 |
| Per task per day | 5 | 2 |

### Scoring
- Correctness: field-by-field (0.0–1.0)
- Tier multiplier: T1 ×1, T2 ×2, T3 ×3
- Efficiency bonus: up to 2× (perfect score only, fewer API calls + zero 4xx errors)
- Score range: 0.0–6.0
- Best score per task kept; benchmarks recalculate every 12h

### 30 Task Types (7 categories)
| Category | Tasks |
|----------|-------|
| Employees | Create, update, set roles, delete |
| Customers & Products | Create customer, update, create product |
| Invoicing | Create invoice, invoice with customer, payment, credit note |
| Travel Expenses | Create, delete |
| Projects | Create, link to customer, billing |
| Corrections | Reverse entries, error correction (T3), year-end closing (T3) |
| Departments | Create, enable modules, bank reconciliation (T3) |

### Tier Schedule
- **Tier 1** (×1): Competition start — March 19 18:00
- **Tier 2** (×2): Early Friday — March 21
- **Tier 3** (×3): Early Saturday — March 22

---

## 5. NorgesGruppen API

**No HTTP API** — this is a code-upload task.

### Submission Flow
1. Train model locally/cloud
2. Package as ZIP: `run.py` at root + model weights
3. Upload ZIP via app.ainm.no
4. Sandbox executes: `python run.py --input /data/images --output /output/predictions.json`

### Output Format
```json
[
  {
    "image_id": 42,
    "category_id": 155,
    "bbox": [120.5, 45.0, 80.0, 110.0],
    "score": 0.923
  }
]
```

### Sandbox
- GPU: NVIDIA L4 (24GB VRAM), CUDA 12.4
- CPU: 4 vCPU, 8GB RAM
- Python 3.11, PyTorch 2.6.0, YOLOv8 8.1.0, ONNX Runtime 1.20.0
- **No network access**
- Timeout: 300s
- Blocked: os, sys, subprocess, socket, pickle, requests

### Scoring
`Score = 0.7 × detection_mAP@0.5 + 0.3 × classification_mAP@0.5`

### Submission Limits
- 3 submissions/day (2 freebies for infra errors)
- Concurrent: 2

---

## 6. GCP Infrastructure

### What Teams Get
- **@gcplab.me** Google account with dedicated GCP project
- **No credit limits** — free for competition use
- Must apply; priority for Vipps-verified teams

### Available Services
| Service | Details |
|---------|---------|
| Cloud Run | Container hosting, auto-scaling, free tier |
| Vertex AI | Gemini models (2.0 Flash, 2.5 Pro) |
| Cloud Shell | Free Linux VM, 5GB home, Python/Docker/gcloud pre-installed |
| Cloud Build | Build containers from source |
| Artifact Registry | Docker image storage |

### Cloud Run Deployment
```bash
gcloud run deploy my-agent \
  --source . \
  --region europe-north1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 300 \
  --min-instances 1 \
  --max-instances 5 \
  --concurrency 1
```

### Key Config
| Setting | Value | Reason |
|---------|-------|--------|
| Region | `europe-north1` | Closest to validators |
| Timeout | 300s | Competition limit |
| Memory | 1Gi | Enough for API relay |
| min-instances | 1 | Avoid cold starts |
| concurrency | 1 | One request per instance |
| Auth | `--allow-unauthenticated` | Validators need access |

### Vertex AI / Gemini
- `gemini-2.0-flash` — fast, free tier (15 RPM, 1M tokens/day)
- `gemini-2.5-pro-preview-03-25` — better reasoning, for complex tasks
- Auth: service account on Cloud Run (no API key needed)
- SDK: `google-genai` package
- IAM: service account needs `roles/aiplatform.user`

### Required API Enables
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com
```

---

## 7. Tripletex Sandbox

- **URL:** https://kkpqfuj-amager.tripletex.dev
- **API Base:** https://kkpqfuj-amager.tripletex.dev/v2
- **Auth:** Basic Auth (username: 0, password: session token)
- **Token expiry:** March 31, 2026
- **Setup:** Visma Connect account via "Forgot password"
- Returns 401 without valid auth credentials
- Persistent data (unlike competition which gets fresh account per submission)

### Session Token Creation
```python
PUT /token/session/:create
Params: consumerToken, employeeToken, expirationDate
Returns: {"value": {"token": "session-token-string"}}
```

---

## 8. MCP Docs Server

Connect AI tools to competition docs:
```bash
claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp
```
Note: This is MCP protocol, not a regular HTTP page.

---

## 9. Key URLs Summary

| URL | Purpose |
|-----|---------|
| https://app.ainm.no | Competition platform & dashboard |
| https://api.ainm.no/astar-island/* | Astar Island API |
| https://tx-proxy.ainm.no/v2 | Tripletex proxy (competition) |
| https://kkpqfuj-amager.tripletex.dev/v2 | Tripletex sandbox (development) |
| https://mcp-docs.ainm.no/mcp | MCP docs server |
| https://ainm.no | Public competition website |

---

## 10. What's NOT Documented / Gaps

- `api.ainm.no` root, `/docs`, `/swagger`, `/openapi.json` all return 404
- No OpenAPI/Swagger spec for the Astar Island API
- Complete list of all 30 Tripletex task types not published
- Exact tier unlock times for T2/T3 unknown ("early Friday/Saturday")
- Exact efficiency bonus formula not specified
- Tripletex full API schema must be explored via sandbox or https://tripletex.no/v2-docs/
- NorgesGruppen has no API — code upload only
