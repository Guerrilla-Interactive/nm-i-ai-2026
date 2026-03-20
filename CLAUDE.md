# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NM i AI 2026 competition codebase (Norwegian AI Championship, March 19-22, 2026). Three independent tasks, each in its own directory. Overall score = average of all three tasks.

## Task Commands

### Astar Island (World Simulation Prediction)

```bash
cd astar-island
python watch_v6.py              # Main entry: auto-polls + submits every 30s
python solver_v6.py [round_id]  # Single round submission
```

- API auth: JWT token in `astar-island/.env` (ASTAR_TOKEN)
- Rate limits: 5 req/s simulate, 2 req/s submit
- 50 queries per round, 15×15 viewport, predicts 40×40 terrain probabilities
- Never assign 0.0 probability — use ≥0.001 floor

### Tripletex (AI Accounting Agent)

```bash
cd tripletex/app
python -m uvicorn main:app --port 8080   # Run locally
python test_local.py                      # Test locally
python test_e2e_live.py                   # Test against sandbox API
bash ../deploy.sh                         # Deploy to Cloud Run
```

Deploy command (if deploy.sh unavailable):
```bash
gcloud run deploy tripletex-agent --source tripletex/app/ \
  --region europe-north1 --allow-unauthenticated \
  --memory 2Gi --timeout 300 --min-instances 1
```

- FastAPI app receiving POST /solve with {prompt, files, tripletex_credentials}
- Classifier detects task type (30 types, 7 languages) → executor calls Tripletex API
- LLM backends: Vertex AI Gemini (production), Anthropic Claude (local dev), rule-based fallback
- Credentials in `tripletex/.env`
- GCP Project: `nm-i-ai-490723`, Region: `europe-north1`

### NorgesGruppen (Object Detection)

```bash
cd norgesgruppen
python train.py                    # Train YOLOv8 (needs GPU)
python train.py --export-only      # Export best.pt → ONNX
python run.py --image test.jpg     # Local inference test
python package_submission.py       # Create submission.zip for upload
```

- Training: YOLOv8 with ultralytics, 248 images, 356 categories
- Inference (sandbox): ONNX Runtime only — ultralytics/os/sys/subprocess/socket/pickle/yaml/requests are blocked
- Sandbox: NVIDIA L4, max 420MB model, 300s timeout
- Output: COCO format detections
- Scoring: 70% detection (IoU≥0.5) + 30% classification

## Architecture

Three independent modules — no shared code between tasks.

**astar-island/**: `client.py` (API wrapper) → `solver_v6.py` (ensemble: regime detection + regression + group priors blending) → `predictor_v3.py` (linear regression features). Pre-trained models in `data/`.

**tripletex/app/**: `main.py` (FastAPI) → `classifier.py` (LLM-based task classification, 30 task types) → `executor.py` (Tripletex API calls) → `tripletex_client.py` (HTTP client, Basic auth). Dockerfile for Cloud Run deployment.

**norgesgruppen/**: `train.py` (YOLOv8 training + ONNX export) → `run.py` (standalone ONNX inference with manual letterbox/NMS, no ultralytics). `category_map.json` maps COCO IDs to class indices.

## Competition Scoring

- Tier multipliers: Tier 1 (×1, available now), Tier 2 (×2, Friday), Tier 3 (×3, Saturday)
- Best score per task is kept — bad submissions never hurt
- Overall = average of 3 tasks (33.33% each)

## Testing

No test framework — test files are standalone scripts run directly:
```bash
python astar-island/test_predictor.py
python norgesgruppen/test_inference.py
python tripletex/app/test_local.py
```

## Dependencies

Each task has its own requirements. No monorepo package manager.
- `astar-island/requirements.txt`: httpx, numpy
- `tripletex/app/requirements.txt`: fastapi, uvicorn, httpx, pydantic, google-genai, anthropic
- NorgesGruppen training: ultralytics, opencv-python (not in requirements.txt)
- NorgesGruppen sandbox: onnxruntime, opencv-python, numpy, json, pathlib only

## External Services

- Competition API: `https://api.ainm.no`
- Competition dashboard: `https://app.ainm.no`
- Tripletex sandbox: `https://kkpqfuj-amager.tripletex.dev/v2`
- MCP docs: `claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp`
