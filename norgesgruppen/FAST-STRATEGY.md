# FAST STRATEGY — Maximum Score in Minimum Time

**Date:** 2026-03-20 (Tier 2 active, x2 multiplier)
**Goal:** Highest competition score TODAY. Every hour matters.

---

## TL;DR — Do This NOW

1. **Train YOLO11x at imgsz=1280, 150 epochs** on GCP/RunPod A100 (~1-2 hours)
2. **Train YOLO11l at imgsz=1280, 150 epochs** in parallel (model soup candidate)
3. **Use conf=0.01, NMS IoU=0.5, agnostic NMS** at inference
4. **Model soup** the best 2-3 runs (free accuracy, zero inference cost)
5. **Submit immediately** after first good model finishes

---

## Q&A: Key Decisions

### A. YOLOv8x vs YOLO11x?

**Use YOLO11x.** YOLO11x edges out YOLOv8x on COCO benchmarks:
- YOLO11x: 54.7% mAP@0.5:0.95 (~71% mAP@0.5)
- YOLOv8x: 53.9% mAP@0.5:0.95 (~70% mAP@0.5)
- Same ultralytics API: just change `YOLO('yolo11x.pt')` — drop-in replacement
- Similar parameter count and ONNX size — fits well under 420MB
- YOLO11 has improved C2f blocks and attention mechanisms

**Recommendation:** Primary model = `yolo11x.pt`. Backup/soup candidate = `yolo11l.pt`.

### B. Fastest Path to a HIGH Score?

**Single biggest lever: imgsz=1280 on a fast GPU.**

Priority order (bang for buck):
1. **imgsz=1280** — 86% of boxes are <1% of image area. This is a SMALL OBJECT problem. Going from 640→1280 could gain 5-15% detection recall alone.
2. **YOLO11x** instead of smaller variants — speed is irrelevant (L4 processes 16k+ images in 300s)
3. **conf=0.01 at inference** — maximize recall for the 70% detection score
4. **150-200 epochs with aggressive augmentation** — 248 images need heavy augmentation
5. **Model soup** 2-3 runs — free +0.5-1.5% with zero inference cost

**Fastest timeline to a competitive submission:**
- Hour 0-0.5: Set up GPU, upload data
- Hour 0.5-2.5: Train YOLO11x @ 1280, 150 epochs on A100 (~2 hours)
- Hour 2.5-3: Export ONNX, package, submit
- Total: ~3 hours to first HIGH-quality submission

### C. imgsz=1280 vs 640 — Actual Tradeoff

| Factor | 640 | 1280 |
|--------|-----|------|
| Training time (A100, YOLO11x, 200ep) | ~1 hour | ~3-4 hours |
| Training time (L4, YOLO11x, 200ep) | ~2 hours | ~6-8 hours |
| Batch size (A100 80GB) | 16-32 | 8-16 |
| Batch size (L4 24GB) | 8 | 2-4 |
| Small object detection | Mediocre | **Much better** |
| Detection recall estimate | 65-75% | **75-85%** |
| Score impact | Baseline | **+5-15% detection** |

**Verdict: Use 1280.** The dataset has extremely small objects (median box = 0.37% of image area). Images range from 481x640 to 5712x4284. At 640px, a 4032x3024 image is downscaled 6.3x — tiny products become undetectable. At 1280px, it's 3.15x — much more signal preserved.

**GPU recommendation:** A100 (80GB) is ideal — fits batch=8-16 at 1280. L4 (24GB) works but only batch=2-4 at 1280 with YOLO11x. Use A100/H100 if available via RunPod ($1.50-3/hr).

### D. Two-Stage (Detector + Classifier) vs Single YOLO?

**For TODAY: Single YOLO with all 356 classes.**

Why NOT two-stage right now:
- Two models to train, debug, and integrate = 2-3x the engineering time
- Single YOLO at 1280px with good augmentation will get a competitive detection score
- The 30% classification weight means even perfect classification only adds 0.30 to score
- Two-stage has higher ceiling but MUCH higher implementation risk in a time crunch

**When to go two-stage:**
- Only if single YOLO is already submitted and scoring well
- Only if you have 6+ hours AND a working YOLO baseline
- Best classifier: EfficientNet-B3 via `timm` (pre-installed in sandbox, ~48MB ONNX)
- Train on crops extracted from GT boxes + product reference images (344 products, 4.6 angles each)

### E. Augmentation Settings for 248 Images

These settings are already in `train.py` and are well-tuned:

```python
# KEEP THESE — they're optimized for small dataset
mosaic=1.0          # CRITICAL: 4-image combination, 4x effective diversity
close_mosaic=10     # Clean fine-tuning last 10 epochs
mixup=0.15          # Image blending for regularization
scale=0.9           # Wide scale variation (small objects!)
degrees=10.0        # Slight rotation (shelves aren't perfectly aligned)
translate=0.2       # Translation augmentation
shear=2.0           # Slight shear
hsv_h=0.015, hsv_s=0.7, hsv_v=0.4  # Color jitter (lighting variation)
label_smoothing=0.1 # Essential for 356 similar classes
erasing=0.1         # Random erasing (occlusion robustness)
```

**Additional recommendations:**
- `copy_paste=0.1` — already set, good for dense scenes (requires instance masks, may be ignored if only bbox)
- Consider `lr0=0.0005` for YOLO11x (slightly more conservative for larger model)
- `patience=30` instead of 50 to save time if model plateaus early
- `warmup_epochs=5` instead of 3 for 1280px (larger images need gentler warmup)

### F. Model Soup / Ensemble with ONNX

#### Model Soup (RECOMMENDED — free accuracy)

Average the .pt weights of 2-3 models BEFORE exporting to ONNX. Zero inference cost.

```python
import torch

# Load state dicts from multiple runs
paths = ["run1/best.pt", "run2/best.pt", "run3/best.pt"]
state_dicts = []
for p in paths:
    ckpt = torch.load(p, map_location='cpu')
    # ultralytics saves model in ckpt['model'].state_dict()
    sd = ckpt['model'].float().state_dict()
    state_dicts.append(sd)

# Average weights
avg_sd = {}
for key in state_dicts[0]:
    avg_sd[key] = sum(sd[key] for sd in state_dicts) / len(state_dicts)

# Load into model and save
model = YOLO("yolo11x.pt")
model.model.load_state_dict(avg_sd)
model.export(format="onnx", imgsz=1280)
```

**What to vary between runs:**
- Run 1: YOLO11x, imgsz=1280, lr0=0.001, seed=42
- Run 2: YOLO11x, imgsz=1280, lr0=0.0005, seed=123
- Run 3: YOLO11l, imgsz=1280, lr0=0.001, seed=42 (different architecture — soup may not work, but try)

**Model soup only works with SAME architecture.** YOLO11x + YOLO11x = good. YOLO11x + YOLO11l = won't work.

#### WBF Ensemble (if time allows — costs inference time)

Run 2-3 ONNX models and fuse predictions with Weighted Box Fusion:

```python
from ensemble_boxes import weighted_boxes_fusion

# boxes_list: list of [N, 4] arrays (normalized 0-1)
# scores_list: list of [N] arrays
# labels_list: list of [N] arrays
boxes, scores, labels = weighted_boxes_fusion(
    boxes_list, scores_list, labels_list,
    weights=[1.0, 0.8],  # weight per model
    iou_thr=0.5,
    skip_box_thr=0.01
)
```

**Fits in 420MB:** YOLO11x ONNX (~130MB) + YOLO11l ONNX (~90MB) = ~220MB — plenty of room.
**Inference time:** 2x models but still <60s for 500 images on L4.

### G. Confidence Threshold & NMS Settings

**For maximum competition score:**

```python
CONF_THRESHOLD = 0.01    # Very low — maximize recall (70% of score is detection)
NMS_IOU_THRESHOLD = 0.5  # Lower than default 0.7 — dense shelves need more boxes
AGNOSTIC_NMS = True      # Prevent duplicate boxes from different class predictions
MAX_DET = 300            # Dense images can have 235+ objects per image
```

**Rationale:**
- Detection is 70% of score — every missed box is expensive
- False positives are "free" (they just don't match a GT box and are ignored)
- Dense retail shelves: products are tightly packed, NMS at 0.7 would suppress adjacent detections
- The current `run.py` already uses `CONF_THRESHOLD=0.01` — this is correct
- `MAX_DET` should be 300+ since images have up to 235 annotations

---

## Execution Plan — TODAY

### Phase 1: First High-Quality Submission (0-3 hours)

```bash
# On GPU machine (A100/L4/RunPod):
python train.py --model yolo11x.pt --epochs 150 --imgsz 1280 --batch 8 \
  --lr 0.001 --patience 30 --name yolo11x_1280_v1 --prepare-submission
```

- If A100: batch=8-16, ~2 hours
- If L4: batch=2-4, ~4-6 hours (start ASAP)
- If Mac M4: batch=1-2, probably won't fit at 1280 with 16GB RAM. Use 640 instead.

**Fallback if 1280 OOMs:** Drop to imgsz=960 or use YOLO11l instead of 11x.

### Phase 2: Parallel Soup Candidate (0-3 hours)

```bash
# Second GPU or sequential:
python train.py --model yolo11x.pt --epochs 150 --imgsz 1280 --batch 8 \
  --lr 0.0005 --patience 30 --name yolo11x_1280_v2
```

### Phase 3: Model Soup + Submit (3-4 hours)

1. Average weights of v1 and v2
2. Export soup to ONNX
3. Test locally with `test_inference.py`
4. Package and submit

### Phase 4: If Time Remains (4+ hours)

- Try WBF ensemble of YOLO11x + YOLO11l
- Try TTA (multi-scale inference) in run.py
- Consider two-stage pipeline only if detection score is already good

---

## Critical Reminders

- **ONNX export must match inference imgsz.** If you train at 1280, export at 1280, and run.py must use 1280.
- **run.py already handles variable input sizes** via letterbox — just make sure the ONNX model's expected input size matches.
- **Category mapping** — `category_map.json` must map YOLO 0-indexed classes back to competition category_ids correctly. Verify end-to-end.
- **3 submissions/day limit** — test locally before submitting. Use `test_inference.py` to validate.
- **Mac M4 (16GB) limitation:** Cannot train YOLO11x @ 1280. Use 640 on Mac, 1280 on cloud GPU.
- **Re-split data?** 90 categories are train-only, 11 are val-only. Consider merging train+val annotations and creating a proper stratified split to ensure all categories are represented in both sets.

---

## Expected Score Ranges

| Strategy | Detection (70%) | Classification (30%) | Combined | Time to Submit |
|----------|----------------|---------------------|----------|---------------|
| YOLO11x @ 640 (baseline) | 70-78% | 40-50% | 0.61-0.70 | 2-3 hours |
| **YOLO11x @ 1280** | **78-88%** | **45-55%** | **0.68-0.78** | 3-4 hours |
| YOLO11x @ 1280 + soup | 80-89% | 47-57% | 0.70-0.80 | 5-6 hours |
| YOLO11x + 11l WBF ensemble | 82-90% | 48-58% | 0.72-0.81 | 6-8 hours |
| Two-stage (YOLO + EfficientNet) | 82-90% | 55-68% | 0.74-0.83 | 10+ hours |

**The sweet spot is YOLO11x @ 1280 — best score per hour invested.**

---

*Strategy synthesized 2026-03-20. Execute Phase 1 immediately.*
