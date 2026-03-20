# NorgesGruppen Detection Model — Improvement Plan

## Current Baseline

| Metric | Value |
|--------|-------|
| mAP@0.50 | 0.6482 |
| mAP@0.50:0.95 | 0.4023 |
| mAP small | 0.1000 |
| mAP medium | 0.4663 |
| mAP large | 0.4180 |
| AR@100 | 0.4634 |
| Categories with AP=0 | 139/356 |
| Model | YOLOv8m, 640px, 100MB ONNX |
| Detections/Annotations | 6805/4508 (~1.5x) |

## Scoring Formula Context

**70% detection (IoU>=0.5) + 30% classification.** This means:
- Recall matters more than precision — missing a detection is very costly
- Getting the class right is worth 30% — classification accuracy on detected boxes is important
- IoU threshold is 0.5, so bbox precision doesn't need to be perfect

---

## Issue 1: Class-Agnostic NMS Suppresses Valid Detections

**Problem:** `cv2.dnn.NMSBoxes` performs class-agnostic NMS — if two different products overlap on the shelf, the lower-confidence one gets suppressed even though they are different classes. In grocery shelf images, products are tightly packed and boxes frequently overlap.

**Evidence:** AR@100 = 0.4634 is low, meaning the model misses over half the objects. Some of this is genuine model failure, but class-agnostic NMS makes it worse.

**Fix — Per-class NMS:**
```python
def nms_per_class(boxes_norm, scores, class_ids, orig_w, orig_h, iou_thresh=0.5):
    """Run NMS independently per class to avoid cross-class suppression."""
    all_dets = []
    unique_classes = np.unique(class_ids)

    for cls_id in unique_classes:
        mask = class_ids == cls_id
        cls_boxes = boxes_norm[mask]
        cls_scores = scores[mask]

        # Convert to xywh for cv2.dnn.NMSBoxes
        boxes_xywh = np.zeros_like(cls_boxes)
        boxes_xywh[:, 0] = cls_boxes[:, 0] * orig_w
        boxes_xywh[:, 1] = cls_boxes[:, 1] * orig_h
        boxes_xywh[:, 2] = (cls_boxes[:, 2] - cls_boxes[:, 0]) * orig_w
        boxes_xywh[:, 3] = (cls_boxes[:, 3] - cls_boxes[:, 1]) * orig_h

        indices = cv2.dnn.NMSBoxes(
            boxes_xywh.tolist(), cls_scores.tolist(),
            CONF_THRESH, iou_thresh,
        )
        if len(indices) == 0:
            continue
        if isinstance(indices, np.ndarray):
            indices = indices.flatten()

        for idx in indices:
            x, y, w, h = boxes_xywh[idx]
            all_dets.append({
                "category_id": int(cls_id),
                "bbox": [round(float(x), 2), round(float(y), 2),
                         round(float(w), 2), round(float(h), 2)],
                "score": round(float(cls_scores[idx]), 5),
            })
    return all_dets
```

**Expected impact:** +2-5% mAP@0.50 from recovering suppressed detections of different classes at overlapping locations.

---

## Issue 2: Small Object Detection is Terrible (mAP small = 0.10)

**Problem:** At 640px input, small products on shelves get downscaled to just a few pixels. The model has 8400 anchor positions at 640px — at 1280px it would have 33,600, giving 4x more spatial resolution.

**Evidence:** mAP small = 0.10 vs mAP medium = 0.47 — a 4.7x gap.

**Fix options (ranked by effort):**

### A. Multi-scale inference (test-time augmentation) — no retraining needed
Run the same 640px model at multiple scales (640, 960, 1280) and merge detections:
```python
SCALES = [640, 960, 1280]
for scale in SCALES:
    blob, scale_f, pad_left, pad_top = preprocess(img_bgr, scale)
    # ... run inference, collect boxes
# Then merge all boxes with NMS or WBF
```
**Caveat:** 3x slower inference. With 300s time limit and ~48 images, that's ~6s/image at 640px → ~18s at triple scale. Should still fit within time budget (~860s needed vs 285s available... wait, 300s limit). Actually 300s / 48 images = 6.25s/image. Multi-scale at 3 scales might be tight. Need to benchmark.

**Safer variant:** Just do 2 scales (640, 1280) — 2x cost.

### B. Train a 1280px model — requires GPU retraining
The `finetune_1280.py` script exists but was run on CPU (very slow). A proper GPU training at 1280px with YOLOv8m would significantly help small objects.
- Model size stays under 420MB
- Input shape changes to [1, 3, 1280, 1280]
- 4x more FLOPs per image — ~24s/image on L4 GPU... should still fit 300s for 48 images

### C. Tile-based inference — no retraining, handles very small objects
Split each image into overlapping tiles (e.g., 2x2 grid with 20% overlap), run each tile at 640px, then stitch detections back together. Effectively 1280px resolution without needing a 1280px model.

**Recommended:** Option A (multi-scale inference at 640+1280) as immediate improvement, with Option B as the best medium-term fix.

---

## Issue 3: 139 Categories with AP=0 — Analysis

Looking at the bottom categories:

| Category | GT Instances | Issue |
|----------|-------------|-------|
| STEKEMARGARIN 500G FIRST PRICE | 0 | No GT — can't score |
| SOFT FLORA ORIGINAL 540G | 0 | No GT — can't score |
| POTETCHIPS SORT TRØFFEL 125G TORRES | 0 | No GT — can't score |
| **SANDWICH PIZZA 37G WASA** | **6** | **Model fails completely** |
| **STORFE SHORT RIBS GREATER OMAHA LV** | **1** | **Model fails** |
| **SANDWICH SOUR CREAM&ONION 33G WASA** | **3** | **Model fails** |

Many AP=0 categories have 0 GT instances (so they can't be evaluated — these are "free" categories that don't hurt the score). But categories like SANDWICH PIZZA (6 instances!) and SANDWICH SOUR CREAM (3 instances) with AP=0 represent real failures.

**Root cause:** With 356 classes and only 248 training images (200 train, 48 val), many classes have <5 training examples. The model can't learn rare classes well.

**Fix — Lower confidence threshold for rare/hard classes:** Not practical without knowing which classes are rare at inference time.

**Fix — More training data:** The `create_synthetic_data.py` script exists. Generating synthetic data for underrepresented classes could help.

---

## Issue 4: Confidence Threshold Tuning

**Current:** CONF_THRESH = 0.01 (very low — good for recall).

**Analysis:** With 6805 detections for 4508 annotations (1.5x ratio), the model is already producing a reasonable number of detections. The low threshold is correct given that scoring prioritizes detection (70%) over precision.

**However:** After NMS, we should consider a post-NMS confidence filter. Very low-confidence detections after NMS are likely false positives. A post-NMS threshold of 0.05-0.10 could remove noise without hurting recall significantly.

**Recommendation:** Keep CONF_THRESH = 0.01 pre-NMS, add optional post-NMS threshold of 0.05. Needs validation data testing.

---

## Issue 5: NMS IoU Threshold

**Current:** NMS_IOU_THRESH = 0.5

**Problem:** For tightly packed grocery shelves, IoU=0.5 is quite aggressive — it will suppress overlapping detections. Products on shelves often overlap in bounding box space.

**Fix:** Increase NMS IoU threshold to 0.6-0.65. This allows more overlapping boxes to survive, which is important for packed shelves.

```python
NMS_IOU_THRESH = 0.6  # was 0.5 — allow more overlapping detections
```

**Expected impact:** +1-3% mAP@0.50 from recovering valid overlapping detections.

---

## Issue 6: Model Architecture — Room to Grow

**Current:** YOLOv8m at 640px = 100MB ONNX. Limit is 420MB.

**Options:**
1. **YOLOv8x at 640px** (~270MB) — more capacity for 356 classes
2. **YOLOv8m at 1280px** (~100MB, same model, higher res) — better small objects
3. **YOLOv8x at 1280px** (~270MB) — both benefits, fits under 420MB
4. **Ensemble: YOLOv8m@640 + YOLOv8m@1280** (~200MB) — diversity helps, WBF code already exists

The current run.py already supports multi-model ensemble with WBF. Shipping two complementary models (different resolutions or architectures) is the highest-value improvement if GPU training time is available.

---

## Priority-Ranked Action Items

| Priority | Change | Expected Impact | Effort |
|----------|--------|----------------|--------|
| **P0** | Per-class NMS (replace class-agnostic NMS) | +2-5% mAP | Code change only |
| **P0** | Increase NMS IoU threshold to 0.6 | +1-3% mAP | One-line change |
| **P1** | Multi-scale inference (640+1280) with same model | +3-7% mAP (esp. small) | Code change, test timing |
| **P1** | Train YOLOv8x at 640px (use full 420MB budget) | +3-5% mAP | GPU training ~2h |
| **P2** | Train 1280px model for ensemble | +5-10% mAP total | GPU training ~4h |
| **P2** | Synthetic data for rare classes | +2-4% on zero-AP classes | Script exists, needs GPU |
| **P3** | Post-NMS confidence filter (0.05) | +0-1% mAP | One-line change |
| **P3** | Tile-based inference for very small objects | +2-5% small mAP | Medium code change |

## Quick Wins (Code-Only, No Retraining)

These changes to `run.py` require zero retraining and should be implemented first:

1. **Per-class NMS** — replace `nms_single_model` with per-class variant
2. **NMS IoU 0.5 → 0.6** — single constant change
3. **Multi-scale inference** — run model at 640+1280, merge with NMS (if timing allows within 300s)

## Timing Budget Analysis

- 300s total, 15s reserve = 285s usable
- 48 images in eval set
- Single model @ 640px on L4 GPU: ~0.5-1s/image → ~48s total (plenty of headroom)
- Single model @ 1280px on L4 GPU: ~2-4s/image → ~192s total (still fits)
- Dual-scale (640+1280): ~3-5s/image → ~240s (tight but feasible)
- Triple-scale: likely exceeds budget

**Recommendation:** Dual-scale (640+1280) with the current model is the best bang-for-buck code-only improvement.
