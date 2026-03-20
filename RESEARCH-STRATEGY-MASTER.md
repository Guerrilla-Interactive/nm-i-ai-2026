# NM i AI 2026 — MASTER STRATEGY

> **Status:** COMPETITION IS LIVE — Started March 19, 18:00 CET
> **Deadline:** Sunday March 22, 15:00 CET (69 hours)
> **Prize pool:** 1,000,000 NOK (400k/300k/200k/100k)
> **Compiled:** 2026-03-19 ~23:40 CET

---

## Executive Summary

**Core strategy: "Fast baselines everywhere, then all-in on Tripletex Tier 2/3."**

Tripletex is the kingmaker — its tier multiplier system means Saturday work is worth 3× Wednesday work. A team that perfectly solves 5 Tier 3 tasks on Saturday outscores a team that perfectly solves 15 Tier 1 tasks over the entire competition.

**Scoring:** Overall = average of 3 tasks (33.33% each), normalized 0-100. Unsubmitted = 0.

---

## Task Priority Ranking

| Priority | Task | Why |
|----------|------|-----|
| 🥇 **#1** | **Tripletex** | Highest ceiling (0-180 theoretical), tier multipliers (3× Saturday), fast iteration cycle |
| 🥈 **#2** | **NorgesGruppen** | Front-loaded value (YOLO trains in background), solid baseline achievable in hours |
| 🥉 **#3** | **Astar Island** | Quick baseline (2-3h), but lower ceiling and budget-constrained (50 queries/round) |

---

## Time Allocation (69 hours)

### Phase 1: Parallel Sprint — Wed 18:00 → Thu 02:00 (8h)

| Workers | Task | Goal |
|---------|------|------|
| 2 workers | **Tripletex** | Cloud Run + FastAPI + Gemini. Handle 5-10 basic tasks (create employee, customer, product). Deploy endpoint. |
| 2 workers | **NorgesGruppen** | Download data, set up YOLO training, start fine-tuning YOLOv8m. Build ONNX inference run.py (sandbox blocks ultralytics imports). |
| 1 worker | **Astar Island** | Build observation + submission pipeline. Smart query placement. Submit first prediction. |
| 1 worker | **Research/Support** | Explore Tripletex API in sandbox. Map all task types. Read full docs. |

**Exit criteria:** Baseline scores submitted on ALL 3 tasks.

### Phase 2: Deepen — Thu 02:00 → Fri ~06:00 (28h)

| Workers | Task | Goal |
|---------|------|------|
| 1 worker | **NorgesGruppen** | Analyze results. Try YOLOv8l/x. Augmentation. Export ONNX. Submit improved model. |
| 4 workers | **Tripletex** | Expand to 15-20 task types. All 7 languages. Efficiency optimization. Submit Tier 1. |
| 1 worker | **Astar Island** | Bayesian inference. Optimize query placement. Improve predictions. |

**Exit criteria:** NorgesGruppen at 65-75%. Tripletex handling most Tier 1 tasks. Astar at 40-60%.

### Phase 3: Tripletex Tier 2 Focus — Fri ~06:00 → Sat ~06:00 (24h)

**⚡ Tier 2 unlocks early Friday — 2× multiplier!**

| Workers | Task | Goal |
|---------|------|------|
| 1 worker | **NorgesGruppen** | Final polish: ensemble, TTA, two-stage pipeline. LAST submission. |
| 5 workers | **Tripletex** | ALL hands on Tier 2 tasks. Multi-step workflows. Invoicing, payments, credit notes, project billing. |

**Exit criteria:** NorgesGruppen finalized (70-80%). Tripletex scoring on Tier 1 + Tier 2.

### Phase 4: Tripletex Tier 3 Blitz — Sat ~06:00 → Sun 15:00 (33h)

**⚡⚡ Tier 3 unlocks early Saturday — 3× multiplier! THIS IS WHERE WE WIN.**

| Workers | Task | Goal |
|---------|------|------|
| 6 workers | **Tripletex** | ALL hands. Bank reconciliation, ledger corrections, year-end closing. File processing (CSV/PDF). Error corrections. |
| (spare cycles) | **Astar Island** | Final optimization if low-hanging fruit remains |

**Exit criteria:** Maximize Tier 3 task scores (each worth up to 6.0 points).

---

## Critical Competition Rules

### Submission Limits (reset midnight UTC)

| Task | Daily | Concurrent | Notes |
|------|-------|------------|-------|
| Tripletex | 5/task/day (verified), 2 (unverified) | 3 (verified), 1 (unverified) | Best score kept forever |
| NorgesGruppen | 3/day | 2 | Private test set for final ranking |
| Astar Island | Per-round budget (50 queries) | — | Resubmit overwrites per seed |

### Prize Eligibility (MUST DO)
1. ✅ All members Vipps-verified (Norwegian BankID)
2. ✅ Code repository made public before deadline
3. ✅ Repo URL submitted to platform
4. ✅ Code must be MIT licensed (or equivalent)

### Key Technical Constraints

**NorgesGruppen sandbox blocks:** `os, sys, subprocess, socket, pickle, yaml, requests, urllib, threading, multiprocessing`
- **Must use ONNX Runtime** for inference (ultralytics imports fail at runtime)
- Use `pathlib` instead of `os`, `json` instead of `yaml`
- `cv2.dnn.NMSBoxes()` for NMS
- Export model to ONNX before submission

**Tripletex key facts:**
- Proxy URL provided per submission (not direct sandbox)
- Fresh account per submission — create prerequisites before dependents
- Efficiency bonus ONLY applies at perfect correctness (1.0)
- Every 4xx error reduces efficiency bonus — validate before calling
- `?fields=*` discovers available fields
- Auth: `("0", session_token)`

**Astar Island key facts:**
- 6 prediction classes (not 8 terrain types) — Ocean/Plains/Empty merged into class 0
- Prediction tensor: 40×40×6, probabilities sum to 1.0 per cell
- NEVER assign 0.0 — floor at ≥0.01, renormalize
- Mountains are static — easy to predict
- Entropy-weighted scoring — uncertain cells matter most

---

## Infrastructure

### Tripletex Deployment (Cloud Run)
```bash
gcloud run deploy agent --source . --region europe-north1 \
  --allow-unauthenticated --memory 1Gi --timeout 300 \
  --min-instances 1 --max-instances 5 --concurrency 1
```

### Available GCP Services
- Cloud Run (container hosting)
- Vertex AI (Gemini 2.0 Flash / 2.5 Pro)
- Cloud Shell, Cloud Build, Artifact Registry

### MCP Docs Server
```bash
claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Ultralytics blocked in sandbox | Use ONNX Runtime inference (already researched) |
| Unknown Tier 3 task types | Flexible LLM agent architecture, plan-execute fallback |
| Rate limit prevents iteration | Test exhaustively in sandbox before submitting |
| Cold start on Cloud Run | Keep min-instances=1, deploy in europe-north1 |
| Gemini rate limits | Have Claude API as backup LLM |

---

## Points-Per-Hour Heat Map

| Task | Hours 1-6 | Hours 6-20 | Hours 20-48 | Hours 48-69 |
|------|-----------|------------|-------------|-------------|
| **NorgesGruppen** | ★★★★ | ★★★ | ★★ | ★ |
| **Tripletex** | ★★ | ★★★ | ★★★★ | ★★★★★ |
| **Astar Island** | ★★★★ | ★★ | ★ | ★ |

---

## Expected Scores

| Task | Pessimistic | Realistic | Optimistic |
|------|------------|-----------|-----------|
| NorgesGruppen | 45-55% | 65-75% | 75-85% |
| Tripletex (total) | 30-40 pts | 60-80 pts | 90-120 pts |
| Astar Island | 25-40 | 45-65 | 65-85 |

**Where we win or lose:** Tripletex has the widest scoring range and the tier multiplier system makes it the primary differentiator.

---

## Immediate Next Actions

1. **NOW:** Set up Tripletex Cloud Run endpoint (FastAPI + Gemini)
2. **NOW:** Download NorgesGruppen dataset, start YOLO training
3. **NOW:** Build Astar Island observation pipeline
4. **ASAP:** Add MCP docs server to Claude for in-context docs
5. **ASAP:** Explore Tripletex sandbox API — map all endpoints and task types
6. **Before bed:** Have baseline submissions on all 3 tasks

---

*Sources: RESEARCH-competition.md, RESEARCH-api-infra.md, RESEARCH-strategy.md*
