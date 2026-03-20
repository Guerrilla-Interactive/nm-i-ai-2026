# Training Options — NorgesGruppen

Assessed: 2026-03-20

## Current State

| Component | Status |
|---|---|
| Machine | Mac Mini, Apple M4 (10-core GPU), 16GB unified RAM, Metal 3 |
| System Python | 3.9.6 (macOS built-in) |
| Homebrew Python | 3.13 |
| PyTorch | **NOT INSTALLED** (neither system nor homebrew) |
| ultralytics | **NOT INSTALLED** |
| numpy | 2.0.2 (system) |
| onnx | 1.19.1 (system) |
| onnxruntime | 1.19.2 (system) |
| opencv | 4.13.0 headless (system) |
| gcloud CLI | v561.0.0 installed, **NOT authenticated** |
| GCP project | Competition provides GCP accounts (Cloud Run, Vertex AI, Gemini) |
| conda/venv | None configured |

## Option A: Local Mac (MPS) — RECOMMENDED for quick start

**Setup needed:**
```bash
# Create a venv with homebrew python
/opt/homebrew/bin/python3.13 -m venv ~/venvs/nm-ai
source ~/venvs/nm-ai/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics opencv-python-headless onnxruntime pycocotools
```

**Pros:**
- Zero cloud setup, start training in ~5 minutes
- M4 MPS is decent for small datasets (248 images)
- No cost

**Cons:**
- 16GB unified memory limits batch size (probably batch=4-8 for yolov8x at 640px)
- MPS is ~3-5x slower than NVIDIA L4 for YOLO training
- yolov8x @ 640px, 200 epochs, batch=4 on M4: estimated **4-8 hours**
- yolov8x @ 1280px may not fit in 16GB at all

**Estimated training times on M4 (248 images, 640px):**

| Model | Batch | Est. Time |
|---|---|---|
| yolov8n | 16 | ~30 min |
| yolov8s | 8 | ~1 hour |
| yolov8m | 4 | ~2 hours |
| yolov8l | 4 | ~4 hours |
| yolov8x | 4 | ~6 hours |

## Option B: GCP VM with GPU — BEST for final training

**Setup needed:**
```bash
# 1. Authenticate
gcloud auth login

# 2. Set project (competition provides this)
gcloud config set project <PROJECT_ID>

# 3. Check GPU quotas
gcloud compute accelerator-types list --filter="zone:europe-north1-a"

# 4. Create VM with L4 GPU
gcloud compute instances create yolo-trainer \
  --zone=europe-north1-a \
  --machine-type=g2-standard-8 \
  --accelerator=type=nvidia-l4,count=1 \
  --boot-disk-size=100GB \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --maintenance-policy=TERMINATE

# 5. SSH and train
gcloud compute ssh yolo-trainer --zone=europe-north1-a
```

**Pros:**
- L4 GPU (24GB VRAM) — matches sandbox hardware exactly
- Can train yolov8x @ 1280px with batch=8-16
- 200 epochs estimated **1-2 hours** for yolov8x @ 640px

**Cons:**
- Need to authenticate gcloud first (user action required)
- Need to check if competition GCP account has GPU quotas
- Setup overhead ~15 min

**Estimated training times on L4:**

| Model | Batch | Est. Time |
|---|---|---|
| yolov8x @ 640px | 16 | ~1 hour |
| yolov8x @ 1280px | 4 | ~3 hours |

## Option C: Google Colab (Free)

**Pros:** Zero setup, free T4 GPU
**Cons:** Session disconnects, limited runtime (4-12 hours), T4 is slower than L4

Not recommended — unreliable for a 69-hour competition.

## Option D: Cloud GPU Rental (RunPod, Lambda, Vast.ai)

**Setup time:** ~15–20 min (account + SSH)
**Training time:** A100 ≈ 30–60 min, H100 ≈ 20–40 min

| GPU    | $/hour | Est. training time (yolov8x, 200ep) | Total cost |
|--------|--------|-------------------------------------|------------|
| A100   | ~$1.50 | ~1 hour                             | ~$2        |
| H100   | ~$3.00 | ~30 min                             | ~$1.50     |
| A6000  | ~$0.80 | ~2 hours                            | ~$1.60     |

**Pros:** Fast setup, top-tier GPUs, pay per hour, full CUDA
**Cons:** Requires account + payment, data upload time, not GCP-integrated

Only use if GCP has quota issues or we need the fastest possible training.

## Option E: Vertex AI Training Job

```bash
# If GCP project has Vertex AI enabled
gcloud ai custom-jobs create \
  --region=europe-north1 \
  --display-name=yolo-norgesgruppen \
  --worker-pool-spec=machine-type=n1-standard-8,accelerator-type=NVIDIA_TESLA_T4,accelerator-count=1,...
```

More setup but fully managed. Not worth the overhead unless other options fail.

## Recommendation

**Immediate (now):** Set up local venv and start training yolov8x on MPS. This gets us a baseline model in ~6 hours with zero cloud dependencies.

**Parallel (when user can authenticate):** Set up GCP VM for higher-resolution or multi-run training.

### Quick Start Commands

```bash
# 1. Create environment
/opt/homebrew/bin/python3.13 -m venv /Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/.venv
source /Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/.venv/bin/activate

# 2. Install dependencies
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics opencv-python-headless onnxruntime pycocotools

# 3. Download and convert dataset (must have data/annotations.json and data/images/ first)
cd /Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen
python convert_coco_to_yolo.py

# 4. Train (MPS)
python train.py --model yolov8x.pt --epochs 200 --imgsz 640 --batch 4

# 5. Export + package
python train.py --export-only --prepare-submission
python package_submission.py
```

## Blocker

The training dataset (`NM_NGD_coco_dataset.zip`, ~864 MB) needs to be downloaded from the competition portal first. Check if it's already in `data/` or needs to be fetched from https://app.ainm.no.
