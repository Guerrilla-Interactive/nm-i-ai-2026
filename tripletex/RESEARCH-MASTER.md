# RESEARCH MASTER — Tripletex AI Accounting Agent

> NM i AI 2026 · Competition live March 19–22 (69h) · 1M NOK prize pool
> Synthesized from: RESEARCH-docs.md, RESEARCH-api.md, RESEARCH-architecture.md, RESEARCH-infrastructure.md

---

## 1. How It Works (Competition Flow)

```
Judge → POST /solve (Bearer auth) → OUR Cloud Run Endpoint
         │                                │
         │  Request body:                  │
         │  - prompt (NL, 7 languages)     ├─▶ Gemini (parse task)
         │  - files[] (optional PDFs)      │
         │  - tripletex_credentials:       ├─▶ Tripletex API (execute)
         │    - base_url (proxy URL)       │
         │    - session_token              │
         │                                 │
         │  Response: {"status":"completed"}◀┘
```

**Key facts:**
- Fresh Tripletex account per submission (starts empty)
- 300s timeout per request
- 30 task types × 7 languages × 8 datasets = 1,680 variants
- Score = correctness × tier_multiplier × efficiency_bonus (max 6.0 per task)
- **Best score per task is kept** — bad runs never hurt you
- Rate limits: 5 submissions/task/day (verified teams), 2 (unverified)

---

## 2. Scoring Strategy (CRITICAL)

### Formula
```
score = correctness × tier × efficiency_bonus
```

| Component | Range | How to maximize |
|-----------|-------|-----------------|
| Correctness | 0.0–1.0 | Field-by-field — must be perfect (1.0) to unlock efficiency bonus |
| Tier multiplier | ×1 / ×2 / ×3 | T1 now, T2 Friday, T3 Saturday |
| Efficiency bonus | 1.0–2.0 | Fewer API calls + zero 4xx errors |

### Max scores per tier
| Tier | Perfect + max efficiency | Perfect, no efficiency |
|------|--------------------------|------------------------|
| T1 | 2.0 | 1.0 |
| T2 | 4.0 | 2.0 |
| T3 | 6.0 | 3.0 |

### Efficiency bonus requirements
1. **Fewer API calls** than the benchmark (recalculated every 12h)
2. **Zero 4xx errors** — every 400/404/422 reduces the bonus
3. **Only applies when correctness = 1.0** — imperfect submissions get no bonus

**IMPLICATION:** Get correctness to 100% first, THEN optimize API call count.

---

## 3. The 30 Task Types (Known + Inferred)

### Tier 1 — Foundational (available now, ×1)

| # | Task | Min API Calls | Endpoint Flow |
|---|------|--------------|---------------|
| 1 | Create employee | 1 | `POST /employee` |
| 2 | Set employee roles | 2 | `GET /employee` → `PUT /employee/{id}` |
| 3 | Update employee contact | 2 | `GET /employee` → `PUT /employee/{id}` |
| 4 | Delete employee | 2 | `GET /employee` → `DELETE /employee/{id}` |
| 5 | Create customer | 1 | `POST /customer` |
| 6 | Update customer | 2 | `GET /customer` → `PUT /customer/{id}` |
| 7 | Create product | 1 | `POST /product` |
| 8 | Create invoice | 2 | `POST /order` → `PUT /order/{id}/:invoice` |
| 9 | Create department | 1 | `POST /department` |
| 10 | Create project | 1 | `POST /project` |

### Tier 2 — Multi-step workflows (Friday March 21, ×2)

| # | Task | Min API Calls | Endpoint Flow |
|---|------|--------------|---------------|
| 11 | Invoice for existing customer | 3 | `GET /customer` → `POST /order` → `PUT /order/:invoice` |
| 12 | Register payment on invoice | 2 | `GET /invoice` → `PUT /invoice/{id}/:payment` |
| 13 | Issue credit note | 2 | `GET /invoice` → `PUT /invoice/{id}/:createCreditNote` |
| 14 | Invoice with payment | 4 | `POST /order` → invoice → payment |
| 15 | Create travel expense | 1-2 | `POST /travelExpense` |
| 16 | Delete travel expense | 2 | `GET /travelExpense` → `DELETE /travelExpense/{id}` |
| 17 | Project linked to customer | 2 | `GET /customer` → `POST /project` |
| 18 | Project billing | 3+ | project → order → invoice |
| 19 | Create contact for customer | 2 | `GET /customer` → `POST /contact` |
| 20 | Search/find customer | 1 | `GET /customer?name=X` |

### Tier 3 — Complex scenarios (Saturday March 22, ×3)

| # | Task | Min API Calls | Notes |
|---|------|--------------|-------|
| 21 | Bank reconciliation from CSV | 3+ | Parse CSV file, create vouchers |
| 22 | Error correction in ledger | 2+ | Find & reverse voucher |
| 23 | Year-end closing | 3+ | Complex accounting workflow |
| 24 | Enable accounting module | 1-2 | Company settings |
| 25-30 | Unknown | ? | Will discover during competition |

**~6 task types remain unknown** — will be discovered live. Fallback architecture handles these.

---

## 4. The 7 Languages

| Language | Code | Key accounting terms |
|----------|------|---------------------|
| Norwegian Bokmål | `nb` | ansatt, kunde, faktura, prosjekt, avdeling |
| Nynorsk | `nn` | tilsett, kunde, faktura, prosjekt, avdeling |
| English | `en` | employee, customer, invoice, project, department |
| Spanish | `es` | empleado, cliente, factura, proyecto, departamento |
| Portuguese | `pt` | funcionário, cliente, fatura, projeto, departamento |
| German | `de` | Mitarbeiter, Kunde, Rechnung, Projekt, Abteilung |
| French | `fr` | employé, client, facture, projet, département |

**Strategy:** Use Gemini directly (multilingual) — no pre-translation step. Include field mapping examples in all 7 languages in the system prompt.

---

## 5. Recommended Architecture

### Hybrid: LLM Parse + Deterministic Execute

```
POST /solve
    │
    ▼
┌─────────────────────────────┐
│  1. PARSE (Gemini Flash)    │  ← 1 LLM call
│  - Classify task type       │
│  - Extract structured fields│
│  - Output: JSON             │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  2. VALIDATE (deterministic)│  ← 0 API calls
│  - Required fields present? │
│  - Format dates/numbers     │
│  - Schema validation        │
└─────────────┬───────────────┘
              │
     ┌────────┴────────┐
     │                 │
  Known type      Unknown type
     │                 │
     ▼                 ▼
┌──────────┐   ┌──────────────┐
│ 3a. EXEC │   │ 3b. FALLBACK │
│ Pre-mapped│   │ LLM plans    │
│ API calls │   │ API sequence │
└──────────┘   └──────────────┘
     │                 │
     └────────┬────────┘
              ▼
┌─────────────────────────────┐
│  4. RETURN                  │
│  {"status": "completed"}    │
└─────────────────────────────┘
```

**Why this architecture wins:**
- **1 LLM call** for parsing (not counted in API efficiency)
- **Minimum Tripletex API calls** (pre-mapped sequences)
- **Zero 4xx errors** (pre-validated payloads)
- **Fast** (well within 300s)
- **Deterministic** for known tasks, flexible for unknown

---

## 6. Tech Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| Runtime | Python 3.12 + FastAPI | Fast dev, async, best Gemini SDK |
| LLM | Gemini 2.0 Flash (Vertex AI) | Free, fast, structured output |
| HTTP client | httpx (async) | Non-blocking API calls |
| Deployment | Cloud Run (europe-north1) | Provided GCP, closest region |
| Auth to us | Bearer token | Competition dashboard config |
| Auth to Tripletex | Basic Auth (0:session_token) | From request body |

---

## 7. Deployment Plan

### Files needed
```
tripletex/
├── main.py              # FastAPI app, /solve endpoint
├── task_classifier.py   # Gemini structured output parsing
├── task_executor.py     # Pre-mapped API call sequences
├── tripletex_client.py  # Tripletex API wrapper
├── validators.py        # Field validation
├── requirements.txt     # fastapi, uvicorn, httpx, google-genai
├── Dockerfile           # python:3.12-slim
└── deploy.sh            # gcloud run deploy one-liner
```

### Deploy commands
```bash
# 1. Enable APIs
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com

# 2. Grant Vertex AI access
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# 3. Deploy
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
```

---

## 8. Implementation Phases

### Phase 1: MVP (4h) → Tier 1 working
- [ ] Cloud Run endpoint + /solve route + Bearer auth
- [ ] Gemini structured output for top 10 task types
- [ ] Pre-mapped API sequences for those 10
- [ ] Test with sandbox

### Phase 2: Coverage (4h) → All Tier 1 perfect
- [ ] All ~24 known task types mapped
- [ ] All 7 languages tested
- [ ] Field validation layer
- [ ] Error retry (1 LLM re-prompt on parse failure)

### Phase 3: Efficiency (4h) → Max efficiency bonus
- [ ] Audit every API sequence for minimum calls
- [ ] Zero 4xx errors (validate before every call)
- [ ] Submit and iterate on scoring

### Phase 4: Tier 2+3 (remaining) → Higher tiers
- [ ] Tier 2 tasks (Friday unlock)
- [ ] Tier 3 tasks (Saturday unlock, file processing)
- [ ] Plan-execute fallback for unknown tasks

---

## 9. Tripletex API Quick Reference

### Authentication
```python
# Credentials come IN the request body:
base_url = body["tripletex_credentials"]["base_url"]  # proxy URL
token = body["tripletex_credentials"]["session_token"]
auth = ("0", token)  # Basic Auth
```

### Key endpoints
| Entity | Create | Read | Update | Delete |
|--------|--------|------|--------|--------|
| Employee | `POST /employee` | `GET /employee` | `PUT /employee/{id}` | `DELETE /employee/{id}` |
| Customer | `POST /customer` | `GET /customer` | `PUT /customer/{id}` | `DELETE /customer/{id}` |
| Product | `POST /product` | `GET /product` | `PUT /product/{id}` | — |
| Order | `POST /order` | `GET /order` | `PUT /order/{id}` | — |
| Invoice | via order | `GET /invoice` | — | — |
| Project | `POST /project` | `GET /project` | `PUT /project/{id}` | `DELETE /project/{id}` |
| Department | `POST /department` | `GET /department` | `PUT /department/{id}` | `DELETE /department/{id}` |
| Travel Exp | `POST /travelExpense` | `GET /travelExpense` | `PUT /travelExpense/{id}` | `DELETE /travelExpense/{id}` |
| Contact | `POST /contact` | `GET /contact` | `PUT /contact/{id}` | — |

### Invoice creation flow (most complex common task)
```
1. POST /order (with customer ref + orderLines) → order_id
2. PUT /order/{order_id}/:invoice → invoice created
```

### References use {id: N} format
```json
{"customer": {"id": 42}, "department": {"id": 1}}
```

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Unknown task types (6+ missing) | Can't pre-map | Plan-execute fallback with LLM |
| Gemini misparses non-English | Wrong fields | Few-shot examples per language |
| 4xx errors from bad payloads | Efficiency penalty | Pre-validate all fields |
| Tier 3 file processing (CSV/PDF) | Can't parse | Add file parsers (csv module, base64 decode) |
| Rate limits (5/task/day) | Limited iterations | Test locally with sandbox first |
| Cold starts on Cloud Run | Timeout risk | min-instances=1 |
| Competition proxy differs from sandbox | API differences | Use base_url from request, never hardcode |

---

## 11. MCP Docs Server (Bonus)

Connect competition docs to Claude Code for AI-assisted development:
```bash
claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp
```

---

## 12. Decision Summary

| Question | Answer |
|----------|--------|
| Architecture? | Hybrid: LLM parse → deterministic execute |
| LLM? | Gemini 2.0 Flash via Vertex AI (free) |
| Language handling? | Direct multilingual (no translation) |
| Framework? | Python + FastAPI + httpx |
| Deployment? | Cloud Run, europe-north1, --source deploy |
| Auth model? | Bearer token (incoming), Basic Auth (Tripletex) |
| Efficiency strategy? | Pre-map all task types, validate before calling, zero 4xx |
| Priority? | Correctness first → efficiency second → higher tiers third |
