# NM i AI 2026 — Team Pelle Parameter

**Norwegian AI Championship** — March 19-22, 2026 (69 hours)
Prize pool: 1,000,000 NOK

## Quick Start

### 1. Clone & set up secrets

```bash
git clone git@github.com:Guerrilla-Interactive/nm-i-ai-2026.git
cd nm-i-ai-2026
```

Create `.env` files in each task directory:

**`astar-island/.env`:**
```
ASTAR_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmNDM4ZmViNS1jNjMzLTRjYzYtOTZlYy00NTBjYmIwMTk0YTkiLCJlbWFpbCI6ImZyaWtrQGd1ZXJyaWxsYS5ubyIsImlzX2FkbWluIjpmYWxzZSwiZXhwIjoxNzc0NTY1OTc0fQ.pwIdgZ7gqx4McCKTc5ngm_WbB8CoEJJ7ZgqZpz27FvY
```

**`tripletex/.env`:**
```
TRIPLETEX_BASE_URL=https://kkpqfuj-amager.tripletex.dev/v2
TRIPLETEX_SESSION_TOKEN=eyJ0b2tlbklkIjoyMTQ3NjUyNjMyLCJ0b2tlbiI6ImQ4NWU3MDZmLWI1MjQtNDk0MS04ZTQ1LWUxZWNiMjVlN2M2MyJ9
TRIPLETEX_EMAIL=frikk@guerrilla.no
```

### 2. GCP Access (required for Tripletex deployment)

1. Go to https://app.ainm.no → Team page → "Apply for GCP account"
2. All team members must be **Vipps-verified** first
3. You'll get `@gcplab.me` credentials
4. Login: `gcloud auth login YOUR_EMAIL@gcplab.me`
5. Set project: `gcloud config set project nm-i-ai-490723`
6. Enable APIs:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com
   ```

**GCP Project ID:** `nm-i-ai-490723`
**Region:** `europe-north1` (required for competition)

### 3. Competition Platform

- **Dashboard:** https://app.ainm.no (login with team credentials)
- **API:** https://api.ainm.no
- **Docs:** https://app.ainm.no/docs
- **Tripletex sandbox:** https://kkpqfuj-amager.tripletex.dev
- **Team email:** frikk@guerrilla.no

### 4. RunPod (GPU training)

API Key: `rpa_ZXH1J0Q0SMBW5U8HD1EBQDRNIYA16MWVYK7IFBSObg3vag`
Balance: ~$9.70

---

## Tasks

### 1. NorgesGruppen — Object Detection
Detect/classify grocery products on store shelves. Submit `run.py` + weights in a `.zip`.
- 248 training images, ~22,700 COCO annotations, 356 categories
- Sandbox: NVIDIA L4 (24GB), PyTorch 2.6, YOLOv8
- Scoring: 70% detection (IoU≥0.5) + 30% classification
- Max weights: 420MB, timeout: 300s
- **Submission:** Upload zip at app.ainm.no → NorgesGruppen submission

**Training data:** Download from https://app.ainm.no → NorgesGruppen → Data

### 2. Tripletex — AI Accounting Agent
Build an HTTPS endpoint that receives accounting task prompts and completes them via Tripletex API.
- POST /solve endpoint, Basic Auth, 300s timeout
- 30 task types (employees, invoicing, expenses, etc.)
- 7 languages, field-by-field scoring with tier multipliers
- Tiers: 1 (now), 2 (Friday), 3 (Saturday)
- **Current deployment:** https://tripletex-agent-785696234845.europe-north1.run.app
- **Deploy:** `cd tripletex/app && gcloud run deploy tripletex-agent --source . --region europe-north1 --allow-unauthenticated --timeout 300 --memory 1Gi`

### 3. Astar Island — World Simulation
Observe Norse civilization sim through limited viewport, predict final terrain probabilities.
- 40×40 map, 8 terrain types, 50-year simulation
- 50 queries/round (15×15 viewport each), 5 seeds
- Submit probability tensor, scored by KL divergence
- Never assign 0.0 probability (use ≥0.001 floor)
- **Auto-watcher:** `cd astar-island && python watch_v6.py` (polls every 30s, auto-submits)

---

## Current Status (Updated 2026-03-20 09:00 CET)

| Task | Status | Score |
|------|--------|-------|
| Astar Island | V6 ensemble running, R5 submitted | R4: 82.33 (rank 23/86) |
| Tripletex | Revision 00034 deployed | Score: 0.29 (grading pending) |
| NorgesGruppen | YOLOv8m ready, YOLOv8x training locally | Not yet submitted |

## Architecture

```
nm-i-ai-2026/
├── astar-island/       # World sim predictions
│   ├── client.py       # API client
│   ├── config.py       # Constants
│   ├── watch_v6.py     # Auto-watcher (run this!)
│   ├── solver_v6.py    # V6 ensemble solver
│   ├── predictor_v3.py # Linear regression predictor
│   ├── build_group_priors.py  # Empirical group priors
│   └── data/           # Models & priors (JSON)
├── tripletex/          # AI accounting agent
│   ├── app/            # FastAPI app (Cloud Run)
│   │   ├── main.py     # Endpoints
│   │   ├── classifier.py  # Task classification
│   │   ├── executor.py    # Task execution
│   │   └── Dockerfile
│   └── docs/           # API research
├── norgesgruppen/      # Object detection
│   ├── run.py          # Inference script (submission)
│   ├── category_map.json
│   ├── data/           # Training data (not in git)
│   └── .venv/          # Python venv (not in git)
└── README.md           # This file
```
