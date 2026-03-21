# NorgesGruppen Dataset Analysis

**Dataset:** NM i AI 2026 — NorgesGruppen Object Detection
**Date:** 2026-03-20 (updated)

---

## Overview

| Metric | Value |
|--------|-------|
| Total images | 248 |
| Total annotations | 22,731 |
| Categories | 356 (all have at least 1 annotation) |
| Synthetic images | 768 (generated) |
| Product reference folders | 344 (12 fewer than categories) |
| Images location | `data/train/images/` (all 248 originals) |

---

## 1. Class Distribution

### Summary Statistics

| Stat | Value |
|------|-------|
| Mean annotations/class | 63.9 |
| Median annotations/class | 28 |
| Min | 1 (41 classes) |
| Max | 422 |

### Distribution Shape: **Severe long-tail**

The median (28) is less than half the mean (64), indicating heavily right-skewed distribution.

```
Percentiles:
  P10:   1      <- 10% of classes have just 1 annotation
  P25:   6
  P50:  28
  P75: 101
  P90: 178
  P95: 244
  P99: 366
```

### Scarcity Thresholds

| Threshold | # Classes | % of 356 |
|-----------|-----------|----------|
| = 1 annotation | 41 | 11.5% |
| < 5 annotations | 74 | 20.8% |
| < 10 annotations | 110 | 30.9% |
| < 20 annotations | 158 | 44.4% |
| < 50 annotations | 214 | 60.1% |

**Critical finding:** 41 classes have exactly 1 annotation. Over 20% have fewer than 5 examples.

### Top 20 Most Common Classes

| Rank | ID | Name | Count |
|------|----|------|-------|
| 1 | 355 | unknown_product | 422 |
| 2 | 86 | HAVRE KNEKKEBROED 300G WASA | 398 |
| 3 | 109 | KNEKKEBROED 100 FROE&HAVSALT 245G WASA | 374 |
| 4 | 100 | EVERGOOD CLASSIC FILTERMALT 250G | 368 |
| 5 | 349 | KNEKKEBROED SPORT+ 210G WASA | 364 |
| 6 | 246 | HUSMAN KNEKKEBROED 260G WASA | 322 |
| 7 | 296 | FIBER BALANCE 230G WASA | 309 |
| 8 | 271 | FRUKOST KNEKKEBROED 240G WASA | 307 |
| 9 | 132 | FRUKOST FULLKORN 320G WASA | 300 |
| 10 | 207 | LEKSANDS KNEKKE FIBERBIT 240G | 297 |
| 11 | 307 | MAISKAKER OST 125G FRIGGS | 283 |
| 12 | 250 | LEKSANDS KNEKKE NORMALT STEKT 200G | 271 |
| 13 | 21 | KNEKKEBROED RUNDA SESAM&HAVSALT 290G WASA | 271 |
| 14 | 38 | KNEKKEBROED DIN STUND CHIA&HAVSALT 270G | 265 |
| 15 | 280 | RISKAKER 100G FIRST PRICE | 262 |
| 16 | 233 | LEKSANDS KNEKKE GODT STEKT 200G | 260 |
| 17 | 96 | FLATBROED 275G KORNI | 247 |
| 18 | 92 | KNEKKEBROED GODT FOR DEG 235G SIGDAL | 247 |
| 19 | 80 | FROKOSTEGG FRITTGAAENDE L 12STK PRIOR | 243 |
| 20 | 239 | MAISKAKER CHIA/HAVSALT 130G FRIGGS | 240 |

Top classes dominated by knekkebrod (crispbread). Class 355 "unknown_product" is a catch-all.

---

## 2. Image Analysis

### Image Dimensions

**Highly variable** -- 114 unique dimensions from 481x640 to 5712x4284.

| Dimension | Count | Notes |
|-----------|-------|-------|
| 4032x3024 | 59 | Most common (iPhone) |
| 3024x4032 | 26 | Portrait orientation |
| 4000x3000 | 17 | Common phone resolution |
| 960x1280 | 6 | Lower resolution |
| 3000x4000 | 5 | Portrait |
| 3264x2448 | 5 | |
| 2000x1500 | 4 | |
| Other | 126 | ~100+ unique sizes |

### Objects Per Image

| Stat | Value |
|------|-------|
| Mean | 91.7 |
| Median | 84 |
| Min | 14 |
| Max | 235 |
| P25 | 59 |
| P75 | 116 |

Densely packed grocery shelf scenes with 50-100+ products per image.

### Bounding Box Sizes (Relative to Image)

| Stat | Value |
|------|-------|
| Mean | 0.55% of image area |
| Median | 0.37% |
| < 1% of image | 85.9% of boxes |
| < 0.1% of image | 5.0% of boxes |

**Objects are SMALL.** 86% of bounding boxes occupy <1% of image area. This strongly favors high input resolution (1280+).

### Aspect Ratios (width/height)

| Shape | Count | % |
|-------|-------|---|
| Portrait (w/h < 0.8) | 9,579 | 42.1% |
| Square-ish (0.8-1.2) | 6,834 | 30.1% |
| Landscape (w/h > 1.2) | 6,318 | 27.8% |

Products are mostly taller than wide (bottles, cartons, packages).

---

## 3. Train/Val Split Analysis

### Original Split (CURRENTLY ACTIVE in YOLO dirs)

| Metric | Value |
|--------|-------|
| Train images | 200 (80.6%) |
| Val images | 48 (19.4%) |
| Train annotations | 18,223 |
| Val annotations | 4,508 |
| Categories in both | 255 |
| **Train-only categories** | **90** |
| **Val-only categories** | **11** |

**CRITICAL PROBLEM:** 90 categories appear ONLY in training data (never validated). 11 categories appear only in validation (zero training examples). This split is very poor for a 356-class problem.

### Stratified Split (annotation JSONs exist but NOT applied to YOLO dirs)

| Metric | Value |
|--------|-------|
| Train images | 232 (93.5%) |
| Val images | 60 (24.2%) |
| Image overlap (duplicated) | 44 |
| Categories in both | **356** |
| Train-only categories | **0** |
| Val-only categories | **0** |
| Train fraction per category (mean) | 0.689 |

The `resplit_dataset.py` script correctly computed a stratified split where ALL 356 classes appear in both train and val, by duplicating 44 images that contain rare single-image classes. The stratified annotation JSONs (`annotations_train_stratified.json`, `annotations_val_stratified.json`) are saved but **the actual YOLO symlinks/labels in `data/images/train`, `data/labels/train`, etc. were NOT updated**.

### Action Required

Run `python resplit_dataset.py` to apply the stratified split, then delete cache files:
```bash
rm -f data/labels/train.cache data/labels/val.cache
python resplit_dataset.py
```

---

## 4. Synthetic Data

| Metric | Value |
|--------|-------|
| Synthetic images | 768 |
| Location | `data/images/synthetic/` + `data/labels/synthetic/` |
| YAML config | `norgesgruppen_with_synthetic.yaml` (includes synthetic in train) |

The `norgesgruppen_with_synthetic.yaml` includes synthetic images as additional training data.

---

## 5. Product Reference Images

| Metric | Value |
|--------|-------|
| Product folders | 344 |
| Categories | 356 |
| Gap | 12 categories without reference images |
| Mean angles/product | 4.6 |
| Angles available | main (all), front (316), left (266), back (254), right (240), top (144), bottom (35) |

---

## 6. Key Implications for Training

### Critical Challenges

1. **Extreme class imbalance** -- 41 classes have 1 example, top class has 422. Need class weighting or oversampling.
2. **Small objects** -- 86% of boxes <1% image area. **Use imgsz=1280+.** Consider SAHI for inference.
3. **Variable image sizes** -- 114 unique sizes. Letterboxing essential.
4. **Broken train/val split** -- Current YOLO dirs have old split with 90 train-only + 11 val-only categories. Must re-apply stratified split.
5. **Category 355 "unknown_product"** -- Most common class (422 annotations). Consider excluding from classification scoring.

### Recommended Actions

1. **Re-apply stratified split**: Run `resplit_dataset.py` and delete `.cache` files
2. **Train at imgsz=1280** minimum for small object detection
3. **Use class-balanced sampling** or focal loss for rare classes
4. **Heavy augmentation**: mosaic, mixup, scale variation critical with only 248 images
5. **SAHI for inference**: Tile large images for better small object detection
6. **Consider synthetic data**: 768 synthetic images available via `norgesgruppen_with_synthetic.yaml`

---

*Analysis generated 2026-03-20*
