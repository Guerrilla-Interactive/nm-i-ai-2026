# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AI Accounting Agent for the NM i AI 2026 competition Tripletex task. A FastAPI endpoint (`POST /solve`) receives natural-language accounting prompts in 7 languages, classifies them into one of 30 task types, and executes them against the Tripletex ERP API.

## Commands

```bash
# Run locally (from tripletex/ directory)
cd app && uvicorn main:app --port 8080 --reload

# Or use the helper script
bash run_local.sh

# Test against local server (requires server running on :8080)
cd app && python test_local.py

# Test end-to-end against live Tripletex sandbox (no server needed)
python test_e2e_live.py

# Deploy to Cloud Run
GCP_PROJECT=nm-i-ai-490723 bash deploy.sh

# Expose local server via ngrok (for competition submission without Cloud Run)
bash expose_local.sh
```

## Architecture

Request flow: `POST /solve` → classify prompt → execute against Tripletex API → return result.

**`app/main.py`** — FastAPI entrypoint. Detects LLM mode at startup (Gemini on Cloud Run, Claude locally, rule-based fallback). Contains the Claude classifier, rule-based keyword classifier (`_KEYWORD_MAP` + `_extract_fields_rule_based`), and the `/solve` endpoint that orchestrates classify → execute.

**`app/classifier.py`** — Gemini-powered classifier (production). Builds a detailed system prompt from task type specs, calls Gemini with temperature=0, post-processes extracted fields. Used when `GEMINI_MODEL` env var is set.

**`app/executor.py`** — Deterministic task executor. Maps each `TaskType` to a handler function that makes the minimum Tripletex API calls. The LLM never touches the API directly — it only parses text into structured fields.

**`app/tripletex_client.py`** — Async HTTP client wrapping Tripletex v2 REST API. Basic Auth (`"0"`, session_token). Tracks `api_call_count` and `error_count` for efficiency scoring. Single retry on 5xx, never retries 4xx.

**`app/task_types.py`** — `TaskType` enum (30 types across 3 tiers), `TaskClassification` model, field specs per task type, and human-readable descriptions used in classifier prompts.

## LLM Mode Selection

Determined at import time in `main.py`:
1. **Gemini** (production/Cloud Run): `GEMINI_MODEL` or `GCP_PROJECT` env var set → uses `classifier.py`
2. **Claude** (local dev): `ANTHROPIC_API_KEY` env var set → uses `_classify_with_claude()` in `main.py`
3. **Rule-based** (no LLM): neither set → uses `_KEYWORD_MAP` regex patterns in `main.py`

## Tripletex API Gotchas

These are hard-won facts from sandbox testing — violating them causes failures:

- **Bank account prerequisite**: Must `GET /ledger/account?number=1920` then `PUT` with `bankAccountNumber` before any invoice can be created
- **Employee email is immutable**: Cannot change via PUT after creation
- **Employee search**: Only `firstName` and `email` query params work. `lastName`, `name`, `departmentId` do NOT filter — must filter client-side
- **Version field required**: All PUTs need the `version` field (optimistic locking) — always request `fields=*` on GETs
- **Order→Invoice flow**: POST customer → POST order (with orderLines) → `PUT /order/{id}/:invoice` (query params only, no body)
- **Invoice payment**: `PUT /invoice/{id}/:payment` takes query params only (paymentDate, paymentTypeId, paidAmount)
- **Response wrappers**: POST returns `{"value": {...}}`, GET list returns `{"values": [...]}`

## Scoring

- Field-by-field correctness per task
- Tier multipliers: T1 ×1, T2 ×2, T3 ×3
- **Efficiency bonus**: Up to 2× multiplier for minimal API calls and zero errors — every unnecessary call or 4xx hurts
- Score range: 0.0–6.0

## Environment

- Credentials in `tripletex/.env` (TRIPLETEX_BASE_URL, TRIPLETEX_SESSION_TOKEN)
- Tripletex sandbox: `https://kkpqfuj-amager.tripletex.dev/v2`
- GCP Project: `nm-i-ai-490723`, Region: `europe-north1`
- Cloud Run service: `tripletex-agent`
- Competition MCP docs: `claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp`
