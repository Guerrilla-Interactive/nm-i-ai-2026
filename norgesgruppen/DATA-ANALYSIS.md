# NorgesGruppen Data Analysis Report

**Dataset:** NM i AI 2026 — NorgesGruppen Object Detection
**Date:** 2026-03-20

---

## Overview

| Metric | Value |
|--------|-------|
| Total images | 248 (200 train + 48 val) |
| Total annotations | 22,731 (18,223 train + 4,508 val) |
| Categories | 356 (all have at least 1 annotation) |
| Product reference folders | 344 (12 fewer than categories) |
| Train/val split ratio | ~80/20 (no image overlap) |
| Annotation files | `annotations.json`, `annotations_train.json`, `annotations_val.json` |
| Images location | `data/train/images/` (all 248 images in one dir, split defined by JSON) |

---

## 1. Class Distribution

### Summary Statistics

| Stat | Value |
|------|-------|
| Mean annotations/class | 63.9 |
| Median annotations/class | 28.0 |
| Std deviation | 81.3 |
| Min | 1 |
| Max | 422 |

### Distribution Shape: **Severe long-tail**

The median (28) is less than half the mean (64), indicating a heavily right-skewed distribution. A small number of classes dominate.

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
| < 5 annotations | 74 | 20.8% |
| < 10 annotations | 110 | 30.9% |
| < 20 annotations | 158 | 44.4% |
| < 50 annotations | 214 | 60.1% |

**Critical finding:** Over 20% of classes have fewer than 5 examples. Nearly half have fewer than 20.

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

**Note:** Class 355 "unknown_product" is the most common -- likely a catch-all for unidentifiable items. The top classes are dominated by knekkebrod (crispbread) products.

### Bottom 20 Least Common (all have exactly 1 annotation)

| ID | Name |
|----|------|
| 149 | KNEKKEBROED SESAM&HAVSALT GL.FRI 240G |
| 241 | SANDWICH CHEESE GRESSLOEK 37G WASA |
| 279 | KNEKKEBROED NATURELL GL.FRI 240G WASA |
| 91 | SANDWICH PESTO 37G WASA |
| 317 | POWERKNEKKEBROED GL.FRI 225G SCHAER |
| 140 | SURDEIGKJEKS 100G SAETRES BESTE |
| 274 | VESTLANDSLEFSA TOERRE 10STK 360G |
| 234 | LANO SAAPE 2X125G |
| 123 | ASPARGES GROENN |
| 57 | MORENEPOTETER GULE 650G |
| 291 | PREMIUM DARK ORANGE 100G FREIA |
| 69 | DAVE&JON'S DADLER SOUR COLA 125G |
| 76 | BRUSCHETTA LIGURISK 130G OLIVINO |
| 26 | OB PROCOMFORT NORMAL 16ST |
| 258 | EXTRA SWEET FRUIT 14G |
| 335 | STORFE SHORT RIBS GREATER OMAHA LV |
| 154 | KRYDDERMIKS SHISH KEBAB 10G POS HINDU |
| 242 | BOG 390G GILDE |
| 327 | POTETCHIPS SORT TROEFFEL 125G TORRES |
| 230 | JARLSBERG 27% SKIVET 120G TINE |

---

## 2. Image Analysis

### Image Dimensions

**Highly variable** -- NOT uniform 2000x1500 as initially expected.

| Dimension | Count | Notes |
|-----------|-------|-------|
| 4032x3024 | 59 | Most common -- iPhone camera resolution |
| 3024x4032 | 26 | Same but portrait orientation |
| 4000x3000 | 17 | Another common phone resolution |
| 960x1280 | 6 | Lower resolution |
| 3000x4000 | 5 | Portrait |
| 3264x2448 | 5 | |
| 2000x1500 | 4 | Only 4 images match expected size! |
| Other | 126 | ~94 unique dimensions |

**Total unique dimensions: ~110+**

**Key insight:** Images come from multiple cameras/phones with no standardization. This means:
- Letterbox resize in preprocessing is essential
- Object sizes vary dramatically across images
- Some images are as small as 481x640, others up to 5712x4284

### Orientation
Mix of landscape and portrait orientations. The model must handle both.

### Filenames
- Pattern: `img_XXXXX.jpg` (zero-padded 5-digit IDs)
- Range: img_00001 to img_00382 (not contiguous -- some IDs missing)
- One `.jpeg` file: `img_00378.jpeg`
- **No section identifiers in filenames** -- all generic `img_XXXXX`

### Store Sections (Inferred from Category Names)

| Section | # Categories | # Annotations | Notes |
|---------|-------------|---------------|-------|
| Knekkebrod (crispbread) | ~44 | ~7,157 | **Dominant section** (31.5% of all annotations) |
| Frokost (breakfast) | ~46 | ~3,200 | Cereal, muesli, granola |
| Varmedrikker (hot drinks) | ~67 | ~1,978 | Coffee, tea, cocoa |
| Egg | ~30 | ~1,479 | Various egg brands |
| **Other/misc** | ~169 | ~8,917 | Non-section products |

The knekkebrod section is massively overrepresented.

---

## 3. Annotation Density

### Per-Image Statistics

| Stat | Value |
|------|-------|
| Mean | 91.7 annotations/image |
| Median | 84.0 |
| Min | 14 (image 86) |
| Max | 235 (image 267) |
| Std | 41.7 |

### Distribution

| Range | # Images |
|-------|----------|
| 0-20 | 1 |
| 21-50 | 40 |
| 51-100 | 117 |
| 101-200 | 87 |
| 200+ | 3 |

Most images have 50-100 annotations -- densely packed shelf scenes.

### Bounding Box Sizes

| Metric | Width (px) | Height (px) |
|--------|-----------|-------------|
| Mean | 185.4 | 190.1 |
| Median | 161.0 | 165.0 |
| Min | 10 | 11 |
| Max | 1003 | 1016 |
| P10 | 75 | 81 |
| P90 | 317 | 333 |

### Relative Size (% of image area)

| Stat | Value |
|------|-------|
| Mean | 0.55% |
| Median | 0.37% |
| Min | 0.0018% |
| Max | 5.92% |
| < 1% of image | 85.9% of boxes |
| < 0.1% of image | 5.0% of boxes |

**Key insight:** Objects are SMALL relative to image size. 86% of bounding boxes occupy less than 1% of the image area. This strongly favors higher input resolution (1280 or even larger) for better small object detection.

### Aspect Ratios (width/height)

| Shape | Count | % |
|-------|-------|---|
| Portrait (w/h < 0.8) | 9,579 | 42.1% |
| Square-ish (0.8-1.2) | 6,834 | 30.1% |
| Landscape (w/h > 1.2) | 6,318 | 27.8% |

Products are mostly **taller than wide** (portrait orientation) -- typical for bottles, cartons, and standing packages. Aspect ratio range: 0.05 to 14.0 (extreme outliers exist).

---

## 4. Product Reference Images

### Overview

| Metric | Value |
|--------|-------|
| Product folders | 344 |
| Categories | 356 |
| Gap | 12 categories without reference images |
| Folder naming | EAN barcodes or `CUSTOM_XXX` |

### Images Per Product (Angles)

| Angle | # Products with this angle |
|-------|---------------------------|
| main | 344 (all) |
| front | 316 |
| left | 266 |
| back | 254 |
| right | 240 |
| top | 144 |
| bottom | 35 |

| Stat | Value |
|------|-------|
| Mean angles/product | 4.6 |
| Median | 5.0 |
| Min | 1 |
| Max | 7 |

### Missing Reference Images
12 categories have no product reference images. These may include the "unknown_product" class and other special/unidentified categories.

---

## 5. Train/Val Cross-Analysis

### Split Quality

| Metric | Value |
|--------|-------|
| Train images | 200 (80.6%) |
| Val images | 48 (19.4%) |
| Image overlap | **0** (clean split) |
| Train annotations | 18,223 (80.2%) |
| Val annotations | 4,508 (19.8%) |

### Category Coverage

| Set | Categories |
|-----|-----------|
| Both train & val | 255 |
| Train only | **90** |
| Val only | **11** |
| Total | 356 |

**Critical finding:** 90 categories appear ONLY in training data. The model will never be validated on these during training. 11 categories appear only in validation -- the model has zero training examples for these.

### Train-Only Categories (top 10 by count)

| ID | Name | Train count |
|----|------|-------------|
| 175 | MELANGE MARGARIN 500G | 47 |
| 326 | SOFT FLORA ORIGINAL 540G | 45 |
| 312 | Toerrresvik Gaard Kvalitetsegg 10stk | 33 |
| 344 | EVERGOOD DARK ROAST KAFFEKAPSEL 16STK | 33 |
| 348 | ALI ORIGINAL HELE BOENNER 250G | 24 |
| 168 | BRELETT 540G | 21 |
| 253 | SOFT FLORA LETT 235G | 20 |
| 144 | FRIELE FROKOST KOKMALT 250G | 19 |
| 267 | EGGEHVITE 500G ELDORADO | 19 |
| 224 | SOFT FLORA LETT 540G | 18 |

### Val-Only Categories (all 11)

| ID | Name | Val count |
|----|------|-----------|
| 301 | Gaardsegg fra Fana 10stk | 6 |
| 346 | SANDWICH SOUR CREAM&ONION 33G WASA | 3 |
| 285 | Leka Egg 10stk | 2 |
| 256 | KAFFEFILTER PRESSKANNE 25STK EVERGOOD | 1 |
| 199 | GREEN CEYLON TE OEKOLOGISK 24POS CONFECTA | 1 |
| 167 | TROPISK AROMA FILTERMALT 200G JACOBS | 1 |
| 263 | GRANOLA RASPBERRY 500G START! | 1 |
| 335 | STORFE SHORT RIBS GREATER OMAHA LV | 1 |
| 81 | GROENN TE CHAI 25POS TWININGS | 1 |
| 154 | KRYDDERMIKS SHISH KEBAB 10G POS HINDU | 1 |
| 26 | OB PROCOMFORT NORMAL 16ST | 1 |

### Train Fraction Per Shared Category
- Mean: 0.784 (close to expected 0.80)
- Median: 0.800
- Range: 0.143 to 0.984

The split is reasonably balanced for categories that appear in both sets.

---

## 6. Key Implications for Training Strategy

### Critical Challenges

1. **Extreme class imbalance** -- 20% of classes have <5 examples, yet the top class has 422. Need class weighting or oversampling.

2. **Small objects** -- 86% of boxes are <1% of image area. **Use imgsz=1280 or higher.** Consider SAHI (Slicing Aided Hyper Inference).

3. **Variable image sizes** -- 110+ unique dimensions from 481x640 to 5712x4284. Letterboxing handles this but largest images lose massive detail when resized to 640.

4. **90 train-only categories** -- Val mAP won't measure these. Consider re-splitting or using k-fold CV.

5. **11 val-only categories** -- Zero-shot detection needed for these. Product reference images could help.

6. **"unknown_product" (ID 355)** -- Most common class (422). Need to decide: train on it or exclude it?

### Recommended Actions

1. **Resolution:** Train at imgsz=1280 minimum. Consider tiling large images.
2. **Class weighting:** Use class-balanced sampling or focal loss to help rare classes.
3. **Augmentation:** Heavy augmentation critical -- mosaic, mixup, and heavy scale variation.
4. **Re-split consideration:** Merge train+val and create a stratified split ensuring all classes in both.
5. **Product reference images:** Could be used for few-shot learning or augmentation for rare classes.
6. **SAHI for inference:** Slice large images into overlapping tiles, run detection, merge results.

---

*Analysis generated 2026-03-20*
