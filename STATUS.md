# NM i AI 2026 — Status Report

> **Updated:** 2026-03-19 ~23:55 CET
> **Competition started:** 2026-03-19 18:00 CET
> **Deadline:** 2026-03-22 15:00 CET
> **Time elapsed:** ~6 hours
> **Time remaining:** ~63 hours

---

## Astar Island — Live Leaderboard (from API)

| Rank | Team | Weighted Score | Hot Streak |
|------|------|---------------|------------|
| 1 | Propulsion Optimizers | 85.51 | 81.44 |
| 2 | Token Titans | 85.26 | 81.20 |
| 3 | Kodegutta | 82.48 | 78.56 |
| 4 | Retriever | 81.63 | 77.74 |
| 5 | Skirnir | 80.98 | 77.13 |
| 6 | CAL-culated risks | 79.46 | 75.67 |
| 7 | DS BI | 78.79 | 75.04 |
| 8 | Make no mistakes | 77.47 | 73.78 |
| 9 | Aibo | 72.87 | 69.40 |
| 10 | Popkorn | 72.24 | 68.80 |

**117 teams total.** Top teams already scoring 82-85. Competition is active and teams are scoring.

### Round Status
- **Round 1:** COMPLETED (started 17:57 UTC, closed 20:42 UTC, weight 1.05)
- **Round 2:** ACTIVE (started 21:02 UTC, closes ~23:47 UTC, weight 1.1025)
- Rounds run every ~2h45m with 165-minute prediction windows

---

## MCP Docs Server

- **Status:** CONFIGURED (added to local Claude config)
- Command used: `claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp`

---

## GCP Project Status

- **gcloud CLI:** NOT INSTALLED on this machine
- **GCP project ID:** UNKNOWN — no credentials found in repo
- Teams get `@gcplab.me` Google accounts with dedicated projects
- Deploy region: europe-north1

### To unblock:
1. Install: `brew install google-cloud-sdk`
2. Login: `gcloud auth login` (with @gcplab.me account)
3. Set project: `gcloud config set project <PROJECT_ID>`
4. Enable APIs: `gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com`

---

## Tripletex Sandbox

- **Sandbox URL:** https://kkpqfuj-amager.tripletex.dev/v2
- **Competition proxy:** https://tx-proxy.ainm.no/v2 (per submission)
- **Auth:** Basic Auth — username `0`, password = session_token
- **Token expiry:** March 31, 2026
- **Consumer token:** NOT OBTAINED
- **Employee token:** NOT OBTAINED
- Token creation: `PUT /token/session/:create` with consumerToken + employeeToken

---

## Task Status — All Three

| Task | Code | Deployed | Submitted | Score | Blocker |
|------|------|----------|-----------|-------|---------|
| **Tripletex** | Scaffolded (FastAPI + handlers) | NO (needs GCP) | NO | — | GCP access, tokens |
| **NorgesGruppen** | Pipeline ready (train/export/run.py) | N/A (ZIP upload) | NO | — | Dataset + GPU training |
| **Astar Island** | Research only, no code | N/A (API-based) | NO | — | JWT token + implementation |

### Tripletex (AI Accounting Agent)
**Ready:** `tripletex/app/` — main.py (FastAPI), task_types.py (30 handlers), tripletex_client.py, Dockerfile, deploy.sh
**Missing:** GCP deployment, consumer/employee tokens for sandbox testing

### NorgesGruppen (Object Detection)
**Ready:** train.py, run.py (ONNX Runtime inference), export_onnx.py, convert_coco_to_yolo.py, package_submission.py, validate_submission.py
**Missing:** Training data (864 MB download), GPU training, model export

### Astar Island (Norse World Prediction)
**Ready:** Comprehensive research — query tiling strategy, prediction algorithm, terrain mapping, API docs
**Missing:** Python implementation, JWT auth token from browser login

---

## Critical Blockers (Priority Order)

| # | Blocker | Impact | How to Resolve |
|---|---------|--------|----------------|
| 1 | **GCP access unknown** | Blocks Tripletex deploy + GPU training | Find @gcplab.me credentials, install gcloud |
| 2 | **No JWT auth token** | Blocks Astar Island API calls | Login at app.ainm.no, extract `access_token` cookie |
| 3 | **gcloud not installed** | Blocks all GCP operations | `brew install google-cloud-sdk` |
| 4 | **No Tripletex sandbox tokens** | Blocks agent development/testing | Get from competition dashboard |
| 5 | **Zero submissions across all tasks** | 6h elapsed, 117 teams ahead | Prioritize fastest-to-submit task |

---

## What's Ready vs What Needs Work

| Item | Status |
|------|--------|
| Competition research & strategy | DONE |
| Tripletex code scaffold | DONE |
| NorgesGruppen inference pipeline | DONE |
| Astar Island research & strategy | DONE |
| MCP docs server | DONE |
| GCP access / gcloud setup | BLOCKED |
| Tripletex deployment | BLOCKED (needs GCP) |
| Astar Island implementation | NOT STARTED |
| Astar Island auth token | MISSING |
| NorgesGruppen training data | NOT DOWNLOADED |
| NorgesGruppen model training | NOT STARTED |
| Competition submissions | ZERO on all 3 tasks |

---

## Recommended Next Steps (Immediate)

1. **Sort out GCP access** — Find @gcplab.me credentials, install gcloud CLI
2. **Get JWT from app.ainm.no** — Login in browser, copy `access_token` cookie
3. **Build Astar Island solver** — Round 2 closes soon; quick Python script using research strategy could score 70-80
4. **Deploy Tripletex agent** — Once GCP is up, deploy existing code
5. **Download NorgesGruppen dataset & start training** — Needs GPU
6. **Submit baselines on ALL 3 tasks ASAP** — Every hour without submissions is wasted

---

## Strategy Reminder

**Core: "Fast baselines everywhere, then all-in on Tripletex Tier 2/3."**

- Tier 1 (x1) — available NOW
- Tier 2 (x2) — unlocks early Friday March 21
- Tier 3 (x3) — unlocks early Saturday March 22 (this is where we win)
- Best score per task kept forever — bad runs never hurt
- Overall score = average of 3 tasks (33.33% each)
- **A team scoring 0 on any task loses ~33 points from their average**
