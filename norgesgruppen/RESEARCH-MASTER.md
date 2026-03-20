# NorgesGruppen Object Detection — Master Research Report

> **Competition:** NM i AI 2026 | **Timeline:** Thu Mar 19 18:00 – Sun Mar 22 15:00 CET (69h)
> **Prize:** 1,000,000 NOK (shared across 3 tasks) | **Synthesized:** 2026-03-19

---

## Executive Summary

We must detect and classify 356 grocery product categories on store shelf images using only 248 training images (~22,700 annotations). The sandbox runs an NVIDIA L4 (24GB), blocks `os`/`sys`/`yaml`/`pickle` imports, and limits submissions to 420MB with a 300s timeout.

**Critical finding:** `from ultralytics import YOLO` is **impossible** in the sandbox — ultralytics eagerly imports all blocked modules (`os`, `sys`, `socket`, `yaml`, `pickle`) at load time. We **must** use ONNX Runtime for inference.

**Recommended approach:** Train YOLOv8l/x locally (or on GCP), export to ONNX, submit ONNX model + custom `run.py` using only allowed imports.

---

## 1. Recommended Model & Architecture

### Primary: YOLOv8x (ONNX export)

| Property | Value |
|----------|-------|
| Model | YOLOv8x (68.2M params) |
| .pt size | ~136 MB |
| ONNX size | ~130 MB (FP16: ~65 MB) |
| COCO mAP@0.5 | ~70% |
| L4 inference | ~12-18 ms/image |
| Under 420MB? | Yes (massive margin) |

**Why YOLOv8x:** Speed is NOT a constraint (even YOLOv8x processes 16,000+ images in 300s). The 420MB limit accommodates even an ensemble of two models. Therefore, maximize accuracy with the largest variant.

**Fallback:** YOLOv8l (~87 MB .pt) if x proves unstable or we need room for a second classifier model.

### Alternative: Two-Stage Pipeline (Higher ceiling)

```
Stage 1: YOLOv8m/s as class-agnostic detector → high recall on "product" class
Stage 2: EfficientNet-B3 classifier on cropped boxes → 356-class classification
Total: ~52MB (YOLOv8m ONNX) + ~48MB (EfficientNet-B3) = ~100MB
```

**Rationale:** The detector focuses purely on localization (70% of score) without being confused by 356 fine-grained classes. The classifier operates on clean crops with higher resolution. This decoupling could significantly boost the 30% classification component.

**Risk:** Pipeline complexity, two models to train, additional inference latency (still well within 300s budget).

---

## 2. Training Pipeline

### Phase 1: Baseline (Hours 0–8)

```python
from ultralytics import YOLO

model = YOLO('yolov8x.pt')  # COCO pretrained
model.train(
    data='norgesgruppen.yaml',
    epochs=200,
    imgsz=640,
    batch=-1,            # Auto batch (L4: ~8 for x)
    amp=True,            # Mixed precision
    patience=50,         # Early stopping
    lr0=0.001,           # Lower LR to preserve pretrained features
    mosaic=1.0,          # 4-image mosaic (critical for 248 images)
    close_mosaic=10,     # Disable mosaic last 10 epochs
)
```

**Dataset YAML:**
```yaml
path: /path/to/norgesgruppen
train: images/train
val: images/val
nc: 356
names: [cat_0, cat_1, ..., cat_355]
```

**Validation split:** 10-15% (or 5-fold CV if time allows). Stratify by class frequency.

### Phase 2: Heavy Augmentation (Hours 8–20)

```python
model.train(
    data='norgesgruppen.yaml',
    epochs=300,
    imgsz=1280,          # High-res for dense shelves
    batch=4,             # Reduced for 1280 + YOLOv8x
    amp=True,
    mosaic=1.0,
    mixup=0.15,          # Blend images for regularization
    scale=0.9,           # Scale variation
    degrees=10,          # Slight rotation
    translate=0.2,       # Translation
    shear=2.0,           # Slight shear
    hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
    close_mosaic=10,
    patience=50,
    lr0=0.001,
    label_smoothing=0.1, # Helps with many similar classes
)
```

### Phase 3: Scale & Iterate (Hours 20–40)

- Train multiple variants: YOLOv8m (imgsz=1280), YOLOv8l (imgsz=1280), YOLOv8x (imgsz=640)
- Try YOLO11l/x as drop-in replacement (may outperform YOLOv8)
- Different augmentation seeds → candidates for model soup / ensemble

### Phase 4: Two-Stage Pipeline (Hours 30–50) — If time allows

1. Train class-agnostic YOLO (nc=1, "product" class) for maximum detection recall
2. Extract crops from training data using ground truth boxes
3. Train EfficientNet-B3 on crops (356 classes) — use `timm` (pre-installed v0.9.12)
4. Augment crops with product reference images (327 products with multi-angle photos!)

### Phase 5: Ensemble & Polish (Hours 50–69)

- **Model soup:** Average weights of 3-5 YOLOv8x runs with different hyperparameters (free accuracy, no inference cost)
- **WBF ensemble:** Fuse predictions from 2-3 models using `ensemble-boxes` (pre-installed)
- **TTA:** `augment=True` at inference (+1-2% mAP, well within time budget)

---

## 3. Inference Architecture (run.py)

### Critical Constraint: No Ultralytics in Sandbox

Ultralytics eagerly imports `os`, `sys`, `socket`, `yaml`, `pickle` at module load. **Cannot be monkey-patched.** Must use ONNX Runtime.

### Inference Stack

```
Allowed:  pathlib, json, numpy, cv2, onnxruntime, torch, PIL, argparse,
          math, collections, typing, time, functools, itertools,
          ensemble_boxes, scipy, scikit-learn, timm, safetensors
Blocked:  os, sys, subprocess, socket, ctypes, builtins, importlib,
          pickle, marshal, shelve, shutil, yaml, requests, urllib,
          http.client, multiprocessing, threading, signal, gc, code,
          codeop, pty, eval(), exec(), compile(), __import__()
```

### Pipeline

```
Input images → letterbox resize → normalize → ONNX inference → decode boxes → NMS → COCO JSON
```

### run.py Interface

```bash
python run.py --input /data/images --output /output/predictions.json
```

> **BUG IN CURRENT SKELETON:** The existing `run.py` uses **positional** args but docs specify **`--input`/`--output`** flags. Must fix before submission.

### Key Implementation Details

1. **Preprocessing:** BGR→RGB, letterbox to model input size (640 or 1280), normalize to [0,1], HWC→CHW, batch dim
2. **ONNX output:** Shape `(1, 4+num_classes, num_detections)` = `(1, 360, 8400)` for 356 classes
3. **Postprocessing:** Transpose → confidence filter → remove padding → scale to original coords → cx,cy,w,h → x,y,w,h → NMS via `cv2.dnn.NMSBoxes`
4. **image_id:** Extract from filename: `img_00042.jpg` → `42`
5. **category_id:** YOLO 0-indexed → competition category_id (0-355). Save mapping as `category_map.json`
6. **GPU:** Use `CUDAExecutionProvider` with `CPUExecutionProvider` fallback

### Submission ZIP Structure

```
submission.zip (< 420MB uncompressed, ≤ 1000 files, ≤ 10 .py, ≤ 3 weight files)
├── run.py              # Entry point (--input, --output flags)
├── best.onnx           # YOLOv8x exported ONNX model
├── category_map.json   # YOLO index → COCO category_id mapping
└── classifier.onnx     # Optional: second-stage classifier
```

---

## 4. Scoring Optimization

### Detection (70% weight) — Maximize Recall

| Lever | Setting | Rationale |
|-------|---------|-----------|
| Confidence threshold | `conf=0.01–0.05` | Low threshold → high recall. Every missed detection costs 70% weight |
| NMS IoU threshold | `iou=0.5–0.6` | Dense shelves need lower NMS to keep adjacent products |
| Agnostic NMS | `agnostic_nms=True` | Prevents duplicate boxes from different class predictions |
| Image size | `imgsz=1280` | Better for small products on dense shelves |
| TTA | Multi-scale + flip | +1-2% mAP, well within 300s budget |
| Box regression | CIoU (default) | Best overall for IoU optimization |

### Classification (30% weight) — Fine-Grained Challenge

| Lever | Impact | Notes |
|-------|--------|-------|
| Two-stage detect→classify | **HIGH** | Decouples detection from classification |
| Product reference images | **HIGH** | 327 products with multi-angle photos — use as training data for classifier |
| Focal loss / class weighting | Medium | Handle long-tail distribution |
| Label smoothing | Medium | `0.1` helps with 356 similar-looking classes |
| Higher resolution crops | Medium | Feed 224×224 crops to classifier |

### Combined Score Optimization

| Strategy | Inference cost | Expected gain |
|----------|---------------|---------------|
| Lower conf threshold | None | +2-5% detection |
| TTA | 2-3x slower | +1-2% overall |
| Model soup | None | +0.5-1.5% overall |
| WBF ensemble (2-3 models) | 2-3x slower | +1-3% overall |
| Two-stage pipeline | ~2x slower | +3-8% classification |

---

## 5. Estimated Score Range

| Scenario | Detection (70%) | Classification (30%) | Combined Score |
|----------|----------------|---------------------|----------------|
| **Optimistic** | 85–90% | 60–70% | **0.78–0.84** |
| **Realistic** | 70–80% | 40–55% | **0.61–0.72** |
| **Pessimistic** | 50–65% | 25–35% | **0.43–0.56** |

**Winning team prediction:** 70–85% combined. The two-stage pipeline + product reference images could be a key differentiator.

---

## 6. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Ultralytics blocked in sandbox | **CRITICAL** | ✅ Mitigated: use ONNX Runtime inference |
| run.py arg format wrong | **HIGH** | Must use `--input`/`--output` flags (not positional) |
| ONNX export changes output shape | **HIGH** | Validate ONNX output shape matches postprocessing code |
| Category ID mapping error | **HIGH** | Export mapping from training annotations.json, verify end-to-end |
| 3 submissions/day limit | **HIGH** | Test locally first, use infrastructure failures as freebies |
| 8GB RAM OOM (exit code 137) | Medium | Process images one at a time, `torch.no_grad()` |
| Model too large for 420MB | Low | Even YOLOv8x ONNX FP16 is ~65MB |
| 300s timeout | Low | All variants process 10,000+ images in 300s |
| Class imbalance (356 categories) | Medium | Focal loss, class weights, two-stage approach |
| Product reference images unused | Medium | These 327 products with multi-angle photos are a goldmine for the classifier — don't ignore them |

---

## 7. Implementation Plan (Prioritized)

### IMMEDIATE (Hours 0–4)
1. **Download training data** — `NM_NGD_coco_dataset.zip` (864MB) + `NM_NGD_product_images.zip` (60MB)
2. **Analyze annotations** — class distribution, images per class, annotation density
3. **Set up GCP training environment** — Compute Engine with GPU
4. **Fix run.py** — change to `--input`/`--output` argparse flags
5. **Train YOLOv8m baseline** — imgsz=640, default augmentation, 100 epochs

### FIRST SUBMISSION (Hours 4–12)
6. **Export best.pt → ONNX** — `yolo export model=best.pt format=onnx imgsz=640`
7. **Generate category_map.json** from training annotations
8. **Test run.py locally** — end-to-end with ONNX model
9. **Submit baseline** — validate sandbox works, get first score on leaderboard

### ITERATE (Hours 12–48)
10. **Train YOLOv8x at imgsz=1280** with heavy augmentation
11. **Try YOLO11l/x** as drop-in replacement
12. **Implement two-stage pipeline** (class-agnostic YOLO + EfficientNet classifier on crops)
13. **Use product reference images** as additional classifier training data
14. **Tune inference params** — conf threshold, NMS, TTA

### FINAL PUSH (Hours 48–69)
15. **Model soup** — average 3-5 best checkpoints
16. **WBF ensemble** — if weight budget allows
17. **Final submission** — select best for final evaluation

---

## 8. Key Data Assets

| Asset | Size | Use |
|-------|------|-----|
| 248 shelf images + 22,700 annotations | 864 MB | Primary training data |
| 327 product reference images (multi-angle) | 60 MB | Classifier training, few-shot augmentation |
| `metadata.json` | Small | Product names, annotation counts per product |
| Image dimensions: 2000×1500 | — | High-res → train at imgsz=1280 for best results |

---

## 9. Pre-installed Tools We Should Use

| Package | Version | Use Case |
|---------|---------|----------|
| `ensemble-boxes` | 1.0.9 | Weighted Box Fusion for model ensemble |
| `timm` | 0.9.12 | EfficientNet/ConvNeXt classifier backbone |
| `albumentations` | 1.3.1 | Advanced augmentation (CLAHE, noise, compression artifacts) |
| `supervision` | 0.18.0 | Dataset exploration, annotation visualization |
| `pycocotools` | 2.0.7 | COCO evaluation, annotation parsing |
| `safetensors` | 0.4.2 | Safe model weight serialization |

---

## 10. Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Inference framework | ONNX Runtime | Ultralytics blocked in sandbox |
| Model size | YOLOv8x or YOLOv8l | Speed not a constraint; maximize accuracy |
| Training resolution | 1280 | 2000×1500 images with dense small products |
| Two-stage pipeline | YES (if time allows) | Decouples detection (70%) from classification (30%) |
| Product reference images | Use for classifier | 327 products with multi-angle = huge classification boost |
| Ensemble strategy | Model soup first, WBF if budget allows | Soup is free; WBF costs inference time |

---

*Synthesized from 4 parallel research tracks. Competition clock is ticking — execute Phase 1 immediately.*
