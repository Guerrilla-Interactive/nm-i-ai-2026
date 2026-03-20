# Tripletex Competition — Complete Research (NM i AI 2026)

> Source: https://app.ainm.no/docs/tripletex/*
> Fetched: 2026-03-19
> Competition: March 19 18:00 CET → March 22 15:00 CET (69 hours)
> Prize pool: 1,000,000 NOK (Tripletex is 1/3 of overall score)

---

## 1. Competition Overview

Build an AI accounting agent that receives task prompts via a POST `/solve` HTTPS endpoint, executes accounting operations via the Tripletex v2 REST API, and returns `{"status": "completed"}`.

- **30 different accounting tasks**
- **56 variants per task** (7 languages × 8 data sets) = **1,680 unique task variants**
- **5-minute timeout** per submission (300 seconds)
- Fresh sandbox account provisioned per submission (starts empty)

---

## 2. The 7 Languages

Prompts are delivered in these languages (ISO codes from docs):

| # | Language | Code |
|---|----------|------|
| 1 | Norwegian (Bokmål) | `nb` |
| 2 | English | `en` |
| 3 | Spanish | `es` |
| 4 | Portuguese | `pt` |
| 5 | Nynorsk | `nn` |
| 6 | German | `de` |
| 7 | French | `fr` |

The agent must handle ALL 7 languages. No example prompts are provided in the docs — the agent must parse natural language task descriptions in any of these languages.

---

## 3. Tier System

### Release Schedule

| Tier | Multiplier | Opens | Description |
|------|-----------|-------|-------------|
| Tier 1 | ×1 | Competition start (March 19, 18:00 CET) | Foundational tasks |
| Tier 2 | ×2 | "Early Friday" (March 21) — exact time TBD | Multi-step workflows |
| Tier 3 | ×3 | "Early Saturday" (March 22) — exact time TBD | Complex scenarios |

### Tier Task Examples (from docs)

**Tier 1 — Foundational tasks:**
- Create employee
- Create customer
- Create invoice

**Tier 2 — Multi-step workflows:**
- Invoice with payment
- Credit notes
- Project billing

**Tier 3 — Complex scenarios:**
- Bank reconciliation from CSV
- Error correction in ledger
- Year-end closing

---

## 4. Task Categories & Inferred Task Types

The docs describe **30 tasks** across 7 categories but do NOT enumerate all 30 individually. Below is every task mentioned or inferable:

### Category: Employees
1. Create employee
2. Set employee roles (e.g., administrator)
3. Update employee contact info (phone, email)
4. Delete employee

### Category: Customers & Products
5. Register/create customer
6. Update customer info
7. Create product
8. Search/find customer

### Category: Invoicing
9. Create invoice (single step)
10. Create invoice for existing customer (multi-step: find customer → create order → create invoice)
11. Register payment on invoice
12. Issue credit note
13. Invoice with payment (combined workflow)

### Category: Travel Expenses
14. Register travel expense report
15. Delete travel expense report

### Category: Projects
16. Create project
17. Create project linked to customer
18. Project billing

### Category: Corrections
19. Delete/reverse incorrect entries
20. Error correction in ledger (Tier 3)

### Category: Departments & Accounting
21. Create department
22. Enable accounting modules
23. Bank reconciliation from CSV (Tier 3)
24. Year-end closing (Tier 3)

**Note:** The full list of all 30 tasks is not published in the documentation. The remaining ~6 tasks will only be discovered during competition. Expect variants like: update employee, delete customer, create multiple invoices, register multiple payments, etc.

---

## 5. POST /solve Endpoint Specification

### Request Schema

```json
{
  "prompt": "string — task description in one of 7 languages",
  "files": [
    {
      "filename": "faktura.pdf",
      "content_base64": "base64-encoded-content",
      "mime_type": "application/pdf"
    }
  ],
  "tripletex_credentials": {
    "base_url": "https://tx-proxy.ainm.no/v2",
    "session_token": "your-session-token"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `prompt` | string | Yes | Natural language task in nb/en/es/pt/nn/de/fr |
| `files` | array | No | Can be empty or absent |
| `files[].filename` | string | Yes (if files) | e.g., "faktura.pdf", "kvittering.png" |
| `files[].content_base64` | string | Yes (if files) | Base64-encoded file data |
| `files[].mime_type` | string | Yes (if files) | e.g., "application/pdf", "image/png" |
| `tripletex_credentials.base_url` | string | Yes | Proxy URL to Tripletex API |
| `tripletex_credentials.session_token` | string | Yes | Auth token for API calls |

### Response Format

```json
{"status": "completed"}
```

- Must return **HTTP 200** within **300 seconds**
- Protocol: **HTTPS required**
- Content-Type: application/json

### Authentication TO Your Endpoint (Optional)

If you configure an API key during submission, the platform sends:
```
Authorization: Bearer <your-api-key>
```

### Authentication FROM Your Endpoint to Tripletex API

**Basic Auth:**
- Username: `0` (literal zero)
- Password: `session_token` (from request body)

```
Authorization: Basic base64("0:" + session_token)
```

Python example:
```python
auth = ("0", session_token)
requests.get(f"{base_url}/employee", auth=auth)
```

---

## 6. Tripletex API Details

### Base URL
- Sandbox: `https://kkpqfuj-amager.tripletex.dev/v2` (team-specific)
- Competition: Provided via `tripletex_credentials.base_url` (proxy URL)

### Common Endpoints

| Method | Endpoint | Use |
|--------|----------|-----|
| GET | `/employee` | List/search employees |
| POST | `/employee` | Create employee |
| PUT | `/employee/{id}` | Update employee |
| DELETE | `/employee/{id}` | Delete employee |
| GET | `/customer` | List/search customers |
| POST | `/customer` | Create customer |
| PUT | `/customer/{id}` | Update customer |
| POST | `/invoice` | Create invoice |
| POST | `/order` | Create order (linked to invoice) |
| DELETE | `/travelExpense/{id}` | Delete travel expense |

### Query Parameters
- `fields` — Select specific fields: `?fields=id,firstName,lastName,email`
- `from` — Pagination start: `?from=0`
- `count` — Items per page: `?count=100`
- Search by name: `?name=Ola`

### Response Structure (List endpoints)
```json
{
  "fullResultSize": 42,
  "from": 0,
  "count": 100,
  "values": [
    { "id": 1, "firstName": "Ola", ... }
  ]
}
```

---

## 7. Scoring System (CRITICAL)

### 7a. Correctness Score (0.0 – 1.0)

Field-by-field verification. Each task has specific checks with point values.

**Example — "Create Employee" task (max 10 points):**

| Check | Points |
|-------|--------|
| Employee found | 2 |
| Correct first name | 1 |
| Correct last name | 1 |
| Correct email | 1 |
| Administrator role assigned | 5 |

Formula: `correctness = points_earned / max_points` (e.g., 8/10 = 0.8)

### 7b. Tier Multiplier

`base_score = correctness × tier_multiplier`

| Tier | Multiplier |
|------|-----------|
| Tier 1 | ×1 |
| Tier 2 | ×2 |
| Tier 3 | ×3 |

### 7c. Efficiency Bonus (up to 2× multiplier)

**Only applies to PERFECT correctness (1.0).** Non-perfect submissions score only `correctness × tier`.

Two factors:
1. **Call efficiency** — Fewer API calls vs. best-known solution = higher bonus
2. **Error cleanliness** — Fewer 4xx errors (400, 404, 422) = higher bonus

**Every 4xx error reduces your efficiency bonus.** Avoid trial-and-error.

### 7d. Score Examples (Tier 2 task, ×2 multiplier)

| Scenario | Score |
|----------|-------|
| Failed all checks | 0.0 |
| 80% correct | 1.6 |
| Perfect, many errors/extra calls | ~2.1 |
| Perfect, efficient, few errors | ~2.6 |
| Perfect, best-in-class efficiency, zero errors | **4.0** |

### 7e. Score Range

- Minimum: 0.0 (failed)
- Maximum: **6.0** (perfect Tier 3 + best efficiency = 1.0 × 3 × 2)

### 7f. Best Score Tracking

- **Your score per task is your all-time best.** Bad runs never lower your score.
- Each of 30 tasks tracked independently
- **Efficiency benchmarks recalculated every 12 hours** — your best scores update accordingly
- **Total leaderboard score = sum of best scores across all 30 task types**

### 7g. Maximum Theoretical Score

30 tasks × 6.0 max per task = **180.0 total** (if all were Tier 3 — not realistic since tiers are fixed per task)

---

## 8. Rate Limits

| Limit | Verified Teams | Unverified Teams |
|-------|---------------|-----------------|
| Concurrent submissions | 3 | 1 |
| Per task per day | 5 | 2 |

**Complete Vipps verification early for 3× more submissions.**

---

## 9. Sandbox vs. Competition

| Aspect | Sandbox | Competition |
|--------|---------|-------------|
| Account | Persistent, retained by team | Fresh account per submission |
| API Access | Direct to Tripletex | Via authenticated proxy |
| Data | Accumulates over time | Starts empty each time |
| Scoring | None | Automated field-by-field |
| Token expiry | March 31, 2026 | Per-submission |

Sandbox URL: `https://kkpqfuj-amager.tripletex.dev`
First login: Set up Visma Connect account via "Forgot password"

---

## 10. Deployment Recommendations

### Google Cloud Run (Recommended)

```bash
gcloud run deploy my-agent \
  --source . \
  --region europe-north1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 300
```

- **Region:** `europe-north1` (Finland) — closest to validator, lowest latency
- **Timeout:** 300 seconds (matches competition timeout)
- **Memory:** 1Gi sufficient for LLM API relay
- **Auth:** `--allow-unauthenticated` so validators can reach endpoint

---

## 11. Common Task Patterns & API Flows

| Pattern | Example | API Flow |
|---------|---------|----------|
| Single entity creation | "Create employee Ola Nordmann" | POST /employee |
| Entity with linking | "Create invoice for customer X" | GET /customer → POST /order → POST /invoice |
| Modify existing | "Add phone to customer contact" | GET /customer → PUT /customer/{id} |
| Delete/reverse | "Delete travel expense" | GET /travelExpense → DELETE /travelExpense/{id} |
| Multi-step setup | "Register payment on invoice" | Multiple POSTs in sequence |

---

## 12. Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| 401 Unauthorized | Wrong auth format | Use Basic Auth with username `"0"` and session_token |
| 404 Not Found | Wrong endpoint path | Verify against Tripletex v2 API docs |
| 422 Validation Error | Missing required fields | Read error message — it specifies which fields |
| Empty values array | No matching results | Check/broaden search parameters |

---

## 13. Efficiency Tips (from official docs)

1. **Plan before calling** — parse prompts fully before making any API calls
2. **Avoid trial-and-error** — every 4xx error reduces efficiency bonus
3. **Minimize GET calls** — don't fetch unnecessary entities
4. **Use batch endpoints** where available
5. **Read error messages** — Tripletex error messages tell you exactly what's wrong

---

## 14. Minimal FastAPI Example (from docs)

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests

app = FastAPI()

@app.post("/solve")
async def solve(request: Request):
    body = await request.json()
    prompt = body["prompt"]
    files = body.get("files", [])
    creds = body["tripletex_credentials"]

    base_url = creds["base_url"]
    token = creds["session_token"]
    auth = ("0", token)

    # TODO: Parse prompt, determine task type, execute API calls

    return JSONResponse({"status": "completed"})
```

Run with: `uvicorn main:app --host 0.0.0.0 --port 8080`

---

## 15. MCP Docs Server

Connect the docs server to Claude Code for AI-assisted development:
```bash
claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp
```

---

## 16. Key Strategic Notes

1. **Tier 3 tasks involve file processing** — bank reconciliation from CSV, so PDF/image parsing is critical
2. **Efficiency bonus doubles the score** — worth optimizing for after correctness is 100%
3. **7 languages** — use an LLM to extract structured data from prompts regardless of language
4. **Fresh account per submission** — no state carries over, every entity must be created from scratch
5. **Benchmarks update every 12 hours** — early efficient solutions may lose advantage as others improve
6. **Rate limits are tight** — only 5 attempts per task per day (verified), plan submissions carefully
7. **All Tripletex calls go through proxy** — use `base_url` from request, never hardcode

---

## 17. Pages Fetched

| URL | Status |
|-----|--------|
| /docs | ✅ Main docs page |
| /docs/tripletex/overview | ✅ Full content |
| /docs/tripletex/sandbox | ✅ Full content |
| /docs/tripletex/endpoint | ✅ Full content |
| /docs/tripletex/scoring | ✅ Full content |
| /docs/tripletex/examples | ✅ Full content |
| /docs/tripletex/tasks | ❌ 404 |
| /docs/tripletex/api | ❌ 404 |
| /docs/tripletex/getting-started | ❌ 404 |
| /docs/tripletex/submission | ❌ 404 |
| /docs/google-cloud/deploy | ✅ Deployment info |
| /mcp-docs.ainm.no/mcp | ❌ 406 (MCP protocol, not HTTP) |

---

## 18. What's NOT in the Docs (Gaps)

- **Complete list of all 30 task types** — only categories and examples given
- **Exact tier assignments** — which specific tasks are T1/T2/T3
- **Example prompts in each language** — no translated examples provided
- **Exact efficiency formula** — only described qualitatively
- **Exact tier unlock times** — only "early Friday" and "early Saturday"
- **Full field specifications per task** — only "Create Employee" scoring shown
- **Tripletex API schema details** — must be explored via sandbox or Tripletex docs
