# NM i AI 2026 — Competition Research

## Overview

- **What:** Norwegian AI Championship 2026 — a task-oriented AI competition
- **When:** March 19, 2026 18:00 CET → March 22, 2026 15:00 CET (69 hours)
- **Prize pool:** 1,000,000 NOK
- **Organizer:** Astar Technologies AS (erik@astarconsulting.no, +47 932 87 479)
- **Platform:** https://app.ainm.no
- **Task reveal:** 2026-03-19T17:15:00 UTC (tasks hidden until then)

## Prize Structure

| Place | Prize |
|-------|-------|
| 1st | 400,000 NOK |
| 2nd | 300,000 NOK |
| 3rd | 200,000 NOK |
| Best U23 team (all members <23) | 100,000 NOK (stackable with placement) |

- Paid out individually, split equally among team members (gross, no tax withheld)
- Tiebreaker: team that achieved score first (by submission timestamp) wins

## Scoring — Overall

- **Overall score = average of normalized scores across 3 tasks (33.33% each)**
- Each task normalized to 0–100 scale
- Unsubmitted tasks receive 0 points
- Real-time leaderboard; deadline snapshot determines preliminary rankings
- Official results after code review verification

## Team Rules

- 1–4 members (main competition)
- Roster locked after first submission
- Minimum age: 15
- Each person on one team only
- **Prize eligibility requires:**
  1. All members Vipps-verified (Norwegian BankID)
  2. Code repository made public + URL submitted before deadline
  3. Code must be MIT licensed (or equivalent permissive)

## Schedule

| Time | Event |
|------|-------|
| Thu Mar 19 18:00 CET | Competition kickoff |
| Early Friday | Tier 2 Tripletex tasks unlock |
| Early Saturday | Tier 3 Tripletex tasks unlock |
| Sun Mar 22 15:00 CET | Deadline — all submissions close |
| Sun Mar 22 ~17:00 CET | Winners announced |

## Fair Play

**Allowed:**
- AI coding assistants (ChatGPT, Claude, Copilot, etc.)
- Public models, datasets, research papers, open-source libraries
- Discussing general AI/ML techniques

**Prohibited:**
- Sharing code/solutions/model weights between teams
- Multiple accounts/teams
- Circumventing rate limits
- Attacking platform infrastructure
- Hardcoded/pre-computed responses
- Score manipulation

**Enforcement:** Automated code similarity analysis, submission pattern analysis, API log cross-referencing

---

## Task 1: Tripletex (AI Accounting Agent)

### Description
Build an AI agent that completes accounting operations in Tripletex. Receive task prompts in 7 languages, execute via API calls, get scored on correctness and efficiency.

### How It Works
1. Submit HTTPS endpoint URL to platform
2. Receive fresh sandbox account for each submission
3. Agent receives task prompt at POST `/solve` endpoint
4. Agent calls Tripletex API through authenticated proxy
5. Results verified field-by-field

### Endpoint Specification

**POST `/solve`** (HTTPS required)

Request body:
```json
{
  "prompt": "task description string",
  "tripletex_credentials": {
    "base_url": "proxy URL",
    "session_token": "auth token"
  },
  "files": [{"filename": "...", "content_base64": "..."}]
}
```

Response: `{"status": "completed"}` with HTTP 200

Auth: Basic Auth with username `"0"`, password = session_token

### Task Scope
- 30 task types × 56 variants (7 languages × 8 datasets) = 1,680 unique prompts
- Languages: Norwegian (bokmål), English, Spanish, Portuguese, Nynorsk, German, French
- Categories: employee management, customer/product registration, invoicing, payments, travel expenses, projects, departments, error correction, deletion
- Timeout: 5 minutes per submission

### Scoring

**Correctness:** points_earned / max_points (0–1)

**Tier multipliers:**
| Tier | Multiplier | Availability |
|------|-----------|-------------|
| Tier 1 | ×1.0 | From start |
| Tier 2 | ×2.0 | Early Friday |
| Tier 3 | ×3.0 | Early Saturday |

**Efficiency bonus** (only for perfect correctness = 1.0):
- Measures API call efficiency vs best-known solution
- 4xx errors (400, 404, 422) reduce bonus
- Can up to double the tier score

**Score range per task:** 0.0 – 6.0 (perfect Tier 3 + max efficiency)

**Best score per task tracked; bad runs never lower your score.**

### Rate Limits

| Limit | Verified | Unverified |
|-------|----------|------------|
| Concurrent submissions | 3 | 1 |
| Per task per day | 5 | 2 |

Resets at midnight UTC. Infrastructure errors (max 2/day) don't count.

### Key Tips
- Sandbox starts empty — create prerequisites before dependent entities
- Use `?fields=*` to discover available fields
- Some tasks require enabling modules first (e.g., department accounting)
- Norwegian characters (æ, ø, å) work fine as UTF-8
- Parse prompt completely before making API calls (efficiency matters)
- Avoid trial-and-error — each 4xx error reduces efficiency bonus
- Deploy in europe-north1 for optimal latency

---

## Task 2: Astar Island (Norse World Prediction)

### Description
ML challenge: observe a black-box Norse civilization simulator through limited viewports, predict final world state probability distributions.

### Key Parameters
- Map: 40×40 cells
- Simulation: 50 years
- Query budget: 50 per round (shared across 5 seeds)
- Viewport: max 15×15 cells per query
- Prediction: W×H×6 probability tensor

### Terrain Classes (6 prediction classes from 8 terrain types)
| Class | Terrain |
|-------|---------|
| 0 | Ocean, Plains, Empty |
| 1 | Settlement |
| 2 | Port |
| 3 | Ruin |
| 4 | Forest |
| 5 | Mountain (static) |

### Simulation Mechanics
- **Growth Phase:** Settlements produce food, expand population, develop ports, establish new settlements
- **Conflict Phase:** Settlements raid each other; longships extend raiding range
- **Trade Phase:** Ports exchange resources when accessible and not at war
- **Winter Phase:** All settlements lose food; starvation/raids cause collapse into ruins
- **Environment Phase:** Natural reclamation; settlements may rebuild ruins

### API Endpoints (Base: https://api.ainm.no)

Auth: Cookie (`access_token`) or Bearer token (JWT from app.ainm.no)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/astar-island/rounds` | GET | List active rounds |
| `/astar-island/rounds/{round_id}` | GET | Round details + initial maps |
| `/astar-island/budget` | GET | Remaining queries |
| `/astar-island/simulate` | POST | Run one observation (costs 1 query) |
| `/astar-island/submit` | POST | Submit predictions |
| `/astar-island/my-predictions/{round_id}` | GET | Retrieve submissions |

### Scoring

**Entropy-weighted KL divergence:**
```
KL(p || q) = Σ pᵢ × log(pᵢ / qᵢ)
entropy(cell) = -Σ pᵢ × log(pᵢ)
weighted_kl = Σ entropy(cell) × KL(ground_truth, prediction) / Σ entropy(cell)
score = max(0, min(100, 100 × exp(-3 × weighted_kl)))
```

- Only dynamic cells contribute (static ocean/mountains excluded)
- Higher-entropy (more uncertain) cells weighted more
- Score range: 0–100
- Per-round score = average of 5 seed scores
- Leaderboard = best round score of all time

### CRITICAL: Never assign 0.0 probability to any class!
If ground truth has non-zero probability but prediction is 0.0, KL divergence → infinity, destroying that cell's score. **Enforce minimum floor of 0.01 per class, then renormalize.**

### Strategy Notes
- 50 queries across 5 seeds = ~10 queries per seed for a 40×40 map
- Strategic viewport placement is essential
- Learn hidden parameters from observations, extrapolate beyond viewports
- Uniform baseline scores ~1–5 points; good models score much higher
- Resubmission overwrites previous prediction for that seed only

---

## Task 3: NorgesGruppen Data (Object Detection)

### Description
Build object detection models to identify grocery products on store shelves. Submit as .zip file, executed in sandboxed Docker container with GPU.

### Dataset
- **COCO dataset (~864 MB):** 248 shelf images, ~22,700 bounding box annotations, 356 product categories (IDs 0–355), 4 store sections (Egg, Frokost, Knekkebrod, Varmedrikker)
- **Product reference images (~60 MB):** 327 products with multi-angle photos, organized by barcode

### Submission Format

**Zip structure:**
```
submission.zip
├── run.py          (required, at root!)
├── model.onnx      (optional)
└── utils.py        (optional)
```

**Constraints:**
| Constraint | Limit |
|-----------|-------|
| Uncompressed zip | 420 MB |
| Total files | 1,000 |
| Python files | 10 |
| Weight files | 3 |
| Weight size | 420 MB |
| Timeout | 300 seconds |

**Allowed file types:** .py, .json, .yaml, .yml, .cfg, .pt, .pth, .onnx, .safetensors, .npy

**Execution:** `python run.py --input /data/images --output /output/predictions.json`

**Output format:**
```json
[
  {
    "image_id": 1,
    "category_id": 42,
    "bbox": [x, y, width, height],
    "score": 0.95
  }
]
```
BBox format: COCO `[x, y, width, height]`

### Sandbox Environment
- Python 3.11, 4 vCPU, 8 GB RAM
- **NVIDIA L4 GPU (24 GB VRAM)**, CUDA 12.4
- Pre-installed: PyTorch 2.6.0, ultralytics 8.1.0, ONNX Runtime GPU 1.20.0, OpenCV, timm, etc.
- **No network access, no pip install at runtime**
- Blocked imports: os, sys, subprocess, socket, pickle, requests, urllib, threading, multiprocessing

### Scoring

**Score = 0.7 × detection_mAP + 0.3 × classification_mAP**

Both at IoU ≥ 0.5:
- Detection: correct box placement (category ignored) — max 0.70
- Classification: correct box + correct category_id — adds up to 0.30

Setting all `category_id: 0` caps score at 0.70.

Public leaderboard = public test set. **Final ranking = private test set.**

### Submission Limits
| Constraint | Limit |
|-----------|-------|
| In-flight submissions | 2 per team |
| Daily submissions | 3 per team |
| Infrastructure freebies | 2 per day |

Resets at midnight UTC.

### Key Tips
- Fine-tune on competition data with nc=357 (pretrained COCO model has wrong class IDs)
- YOLOv8m/l/x feasible within 300s timeout on L4 GPU
- FP16 quantization recommended for larger models
- Process images one at a time for memory safety
- Use `torch.no_grad()` during inference
- Use pathlib instead of os for file operations
- Test locally before uploading

---

## Google Cloud Resources

Selected teams get free GCP accounts:
- `@gcplab.me` Google account with dedicated project
- No credit limits
- Cloud Shell with pre-installed tools (Python, Docker, gcloud)
- Cloud Run for endpoint deployment

**Deploy region:** europe-north1 for optimal validator latency

Alternative hosting allowed — competition only cares about a public HTTPS URL.

---

## Useful Links & Tools

- **MCP docs server:** `claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp`
- **Competition Slack:** primary channel for announcements
- **Contact:** erik@astarconsulting.no / +47 932 87 479

---

## Quick Reference: Submission Deadlines & Limits

| Task | Type | Daily Limit | Concurrent |
|------|------|------------|------------|
| Tripletex | HTTPS endpoint | 5/task/day (verified) | 3 |
| Astar Island | API predictions | Per-round budget (50 queries) | — |
| NorgesGruppen | ZIP upload | 3/day | 2 |

**All limits reset at midnight UTC.**
**Competition deadline: Sunday March 22, 2026 at 15:00 CET.**
