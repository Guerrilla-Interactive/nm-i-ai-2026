# Scoring Optimization Research — NorgesGruppen Object Detection

**Scoring formula:** 70% detection (bounding box at IoU ≥ 0.5) + 30% classification (correct `category_id`)
**Dataset:** 248 images, ~22,700 annotations, 356 categories (~64 examples/class average)
**Constraints:** NVIDIA L4 (24GB), 420MB max weights, 300s timeout, blocked imports (os, sys, subprocess, etc.)

---

## 1. Detection Optimization (70% of Score)

### 1.1 Confidence Threshold Tuning

- **Default in YOLOv8:** `conf=0.25`, `iou=0.7` (NMS)
- **For maximizing mAP:** Lower confidence threshold (e.g., `conf=0.001` or `conf=0.01`) dramatically increases recall by keeping more detections, at the cost of more false positives that NMS then filters
- **For this competition (IoU ≥ 0.5 binary):** We want HIGH RECALL — every missed object costs 70% weight. False positives are less harmful than missed detections
- **Recommendation:** Use `conf=0.01` to `conf=0.05` at inference to maximize recall, then let NMS handle duplicates
- **How to tune:** Run validation with different thresholds, plot precision-recall curve, pick threshold that maximizes F1 or the competition metric

### 1.2 NMS Parameters

| Parameter | Default | Recommendation | Rationale |
|-----------|---------|---------------|-----------|
| `iou` (NMS threshold) | 0.7 | 0.5–0.6 | Retail shelves have dense, adjacent products — lower NMS IoU suppresses fewer overlapping boxes, keeping detections for closely packed items |
| `conf` | 0.25 | 0.01–0.05 | Maximize recall for the 70% detection component |
| Class-agnostic NMS | Off | Consider ON | Products of different categories can overlap visually; per-class NMS may keep redundant boxes from different classes for the same object |

- **Soft-NMS** reduces scores of overlapping boxes instead of eliminating them — useful for dense scenes but not natively supported in ultralytics predict
- **Class-agnostic vs per-class:** For dense shelves, class-agnostic NMS (`agnostic_nms=True` in ultralytics) can reduce duplicate detections where the model predicts multiple classes for the same box

### 1.3 Test-Time Augmentation (TTA)

**Ultralytics supports TTA natively:**
```python
from ultralytics import YOLO
model = YOLO("best.pt")
results = model.predict(source=image, augment=True)  # TTA enabled
```

- **What it does:** Runs inference at 3 scales + horizontal flip, merges outputs before NMS
- **Typical improvement:** +1–2% mAP on COCO benchmarks
- **Cost:** 2–3x inference time
- **Competition concern:** 300s timeout for all test images. If test set is ~50 images, that's ~6s/image budget. TTA at 2-3x might be feasible for a fast model (YOLOv8s/m) but risky for larger models
- **Recommendation:** Enable TTA if inference time allows; benchmark first. Consider TTA only on a faster model variant

### 1.4 Anchor-Free vs Anchor-Based

- **YOLOv8/v11 are anchor-free** — they predict object centers directly without predefined anchor boxes
- **Anchor-free advantages for retail shelves:**
  - Better at detecting objects of varying aspect ratios (tall bottles, wide boxes, small items)
  - No anchor tuning required for unusual product shapes
  - More flexible for dense, overlapping objects
- **Anchor-based (YOLOv5, Faster R-CNN):** Requires anchor optimization but can be more stable for known size distributions
- **Recommendation:** Stick with anchor-free (YOLOv8/v11). The dense retail shelf scenario with 356 diverse product shapes benefits from anchor-free flexibility

### 1.5 Box Regression Loss

| Loss | What it optimizes | Convergence | Best for |
|------|-------------------|-------------|----------|
| **IoU Loss** | Overlap area only | Slow | Baseline |
| **GIoU** | Overlap + enclosing box | Moderate | Non-overlapping boxes |
| **DIoU** | Overlap + center distance | Fast | Fast convergence |
| **CIoU** | Overlap + center distance + aspect ratio | Fastest | Best overall accuracy |

- **CIoU is the default in YOLOv8** and is generally considered the best choice
- CIoU simultaneously optimizes overlap area, center point distance, and aspect ratio — all factors that directly improve IoU scores
- **Recommendation:** Keep CIoU (default). No need to change unless experimenting with newer losses like Focaler-IoU or WIoU

---

## 2. Classification Optimization (30% of Score)

### 2.1 Class Imbalance Analysis

- **356 categories, ~22,700 annotations → ~64 avg examples/class**
- Real distribution is likely highly skewed: popular products (milk, bread) may have 200+ annotations; niche products may have <10
- With only 248 training images, some classes may appear in only 1–2 images
- **This is the hardest part of the problem** — 356 fine-grained classes with limited data

### 2.2 Focal Loss

- **Already used in YOLOv8** — the classification head uses BCE with implicit focal-like behavior
- Focal loss down-weights easy examples (confident correct predictions), forcing the model to focus on hard/rare classes
- **Key parameters:** `gamma` (focusing parameter, default 1.5 in YOLOv8) and `alpha` (class weight)
- **For 356 classes:** Consider increasing `gamma` to 2.0 to further down-weight easy classes
- Can also apply class-frequency-based weights to the loss

### 2.3 Two-Stage Strategy: Detect → Classify

**This is likely the highest-impact strategy for the 30% classification score.**

**Approach:**
1. **Stage 1 — Class-agnostic detector:** Train YOLO to detect ALL products as a single "product" class (or few super-categories). This maximizes detection recall since the model only needs to learn "is this a product?" rather than distinguishing 356 categories
2. **Stage 2 — Separate classifier:** Crop detected boxes, resize to 224×224, classify with a dedicated image classifier (EfficientNet-B0/B3, ResNet-50, or ConvNeXt-Tiny)

**Advantages:**
- Detector focuses purely on localization (70% of score) without classification confusion
- Classifier can use techniques specifically designed for fine-grained recognition: larger input resolution, better augmentation, mixup/cutmix
- Classifier can be trained on crops + synthetic augmentations
- Research confirms: "the success of object recognition decreases as the number of classes increases, making direct product recognition insufficient"

**Disadvantages:**
- Two models must fit in 420MB weight limit
- Additional inference time for cropping and classifying
- Pipeline complexity

**Classifier options (for Stage 2):**

| Model | Size | Accuracy | Speed |
|-------|------|----------|-------|
| EfficientNet-B0 | ~20MB | Good | Fast |
| EfficientNet-B3 | ~48MB | Better | Moderate |
| ResNet-50 | ~98MB | Good | Fast |
| ConvNeXt-Tiny | ~112MB | Best | Moderate |
| MobileNetV3 | ~16MB | Decent | Fastest |

**Weight budget:** If YOLO detector is ~25MB (YOLOv8s), that leaves ~395MB for classifier — plenty of room. Even YOLOv8m (~52MB) + EfficientNet-B3 (~48MB) = ~100MB total.

### 2.4 Hybrid Alternative: YOLO Multi-Class + Classifier Refinement

Instead of fully class-agnostic detection:
1. Train YOLO on all 356 classes normally (gets both detection + initial classification)
2. Use a separate classifier on low-confidence predictions only (where YOLO's class confidence < threshold)
3. This avoids re-classifying easy/obvious products while improving hard cases

---

## 3. Combined / Ensemble Strategies

### 3.1 Weighted Box Fusion (WBF)

- **What:** Fuses predictions from multiple models by averaging box coordinates weighted by confidence
- **Unlike NMS:** WBF uses ALL boxes to construct averaged boxes, rather than discarding overlapping ones
- **Typical gain:** +1–3% mAP over single-model predictions
- **Library:** `pip install ensemble-boxes` → `from ensemble_boxes import weighted_boxes_fusion`
- **How to use:**
  ```python
  from ensemble_boxes import weighted_boxes_fusion
  boxes, scores, labels = weighted_boxes_fusion(
      boxes_list, scores_list, labels_list,
      weights=[1, 1, 1],  # model weights
      iou_thr=0.5,
      skip_box_thr=0.01
  )
  ```
- **Competition strategy:** Train 2–3 YOLO variants (different sizes, augmentation seeds) and fuse predictions
- **Concern:** Must fit within 420MB weight limit. 3× YOLOv8s (~75MB) is feasible. 3× YOLOv8m (~156MB) also works.

### 3.2 Model Soup (Weight Averaging)

- **What:** Average the weights of multiple models fine-tuned with different hyperparameters into a single model
- **Key advantage:** NO additional inference cost — single model at test time
- **Requirement:** Models must share the same architecture (e.g., all YOLOv8m)
- **How to create:**
  ```python
  # Average state dicts
  state_dicts = [torch.load(f"run{i}/best.pt") for i in range(3)]
  avg_state = {}
  for key in state_dicts[0]:
      avg_state[key] = sum(sd[key] for sd in state_dicts) / len(state_dicts)
  torch.save(avg_state, "soup.pt")
  ```
- **Typical gain:** +0.5–1.5% accuracy improvement over best single model
- **Recommendation:** Train 3–5 models with different hyperparameters (learning rate, augmentation strength, image size), then average. Free accuracy boost with no inference cost.

### 3.3 Knowledge Distillation

- **What:** Train a smaller "student" model supervised by a larger "teacher" model
- **Relevance:** If the best model exceeds the 420MB or 300s limit, distill it into a smaller model
- **Typical gain:** Student achieves ~1–2% mAP improvement over training from scratch
- **Ultralytics doesn't natively support distillation** — requires custom training loop
- **Recommendation:** Lower priority than WBF and model soup. Only pursue if time permits and the best model is too large.

### 3.4 Multi-Scale Training & Inference

- Train at multiple image sizes (640, 1024, 1280) and ensemble at inference
- Or train at 1280 for best accuracy (retail shelves benefit from high resolution for small products)
- **Recommendation:** Train at `imgsz=1280` if L4 GPU memory allows (24GB should handle YOLOv8m at 1280)

---

## 4. Practical Score Estimation

### 4.1 COCO Benchmarks (80 classes)

| Model | COCO mAP@0.5:0.95 | COCO mAP@0.5 |
|-------|-------------------|---------------|
| YOLOv8n | 37.3% | ~52% |
| YOLOv8s | 44.9% | ~62% |
| YOLOv8m | 50.2% | ~67% |
| YOLOv8l | 52.9% | ~69% |
| YOLOv8x | 53.9% | ~70% |
| YOLOv11l | 53.4% | ~69% |
| YOLOv11x | 54.7% | ~71% |

Note: COCO mAP@0.5 is typically 15–20 points higher than mAP@0.5:0.95. **This competition uses IoU ≥ 0.5 threshold, which is closer to mAP@0.5.**

### 4.2 Expected Performance with 356 Classes / 248 Images

**Challenges vs COCO:**
- 356 classes vs 80 → ~4.5x more categories, much harder classification
- ~64 examples/class vs thousands → severe data scarcity
- Fine-grained distinctions (similar packaging, similar products)
- Dense scenes with heavy occlusion

**Rough estimates:**

| Metric | Optimistic | Realistic | Pessimistic |
|--------|-----------|-----------|-------------|
| Detection recall (IoU≥0.5) | 85–90% | 70–80% | 50–65% |
| Classification accuracy | 60–70% | 40–55% | 25–35% |
| **Combined score** | **75–82%** | **60–70%** | **42–55%** |

**Calculation:** `score = 0.7 × detection + 0.3 × classification`
- Optimistic: `0.7 × 0.87 + 0.3 × 0.65 = 0.609 + 0.195 = 0.80`
- Realistic: `0.7 × 0.75 + 0.3 × 0.47 = 0.525 + 0.141 = 0.67`
- Pessimistic: `0.7 × 0.57 + 0.3 × 0.30 = 0.399 + 0.090 = 0.49`

### 4.3 Competitive Score Prediction

- **Winning team** in a 69-hour hackathon with pre-installed YOLOv8: likely **70–85%** combined score
- **Top 5 teams:** likely **60–75%**
- **Detection is easier to optimize** (70% weight) — focus here first for maximum point gain
- **Classification** will separate top teams — the two-stage approach could be a differentiator

### 4.4 Maximum Impact Actions (Priority Order)

1. **Train YOLOv8m/l at imgsz=1280** — best single-model baseline for dense shelves (+high)
2. **Lower conf threshold at inference** (`conf=0.01`) — maximize recall for detection score (+medium)
3. **Two-stage detect→classify pipeline** — biggest classification improvement (+high for 30%)
4. **TTA at inference** (`augment=True`) — free +1–2% if time budget allows (+low-medium)
5. **Model soup** from multiple training runs — free accuracy, no inference cost (+medium)
6. **WBF ensemble** of 2–3 models — if weight budget allows (+medium)
7. **Aggressive data augmentation** — mosaic, mixup, copy-paste especially for rare classes (+medium)
8. **NMS tuning** (`iou=0.5`, `agnostic_nms=True`) — small but free improvement (+low)

---

## 5. Key Recommendations Summary

### Must-Do (Hours 1–24)
- Train YOLOv8m on all 356 classes with `imgsz=1280`, strong augmentation
- Analyze class distribution — identify rare classes needing extra attention
- Set up validation split stratified by class frequency

### Should-Do (Hours 24–48)
- Implement two-stage pipeline: YOLO detector + EfficientNet classifier on crops
- Train 2–3 YOLO variants with different hyperparameters for model soup / WBF
- Tune inference parameters: `conf=0.01–0.05`, `iou=0.5–0.6`

### Nice-to-Have (Hours 48–69)
- WBF ensemble of best models
- TTA at inference if time budget allows
- Class-balanced sampling or oversampling for rare categories
- Pseudo-labeling on test images (if competition rules allow)

---

## 6. Blocked Import Workarounds

Key constraint: `os`, `sys`, `subprocess`, `yaml`, `pickle` are blocked.

- Use `pathlib` for all file operations
- Use `json` instead of `yaml` for config
- Model loading: `torch.load()` works (not pickle directly)
- Ultralytics YOLO loading: `from ultralytics import YOLO; model = YOLO("weights.pt")` — internally uses torch, should work
- **Test run.py in a sandboxed environment** mimicking blocked imports before submitting
