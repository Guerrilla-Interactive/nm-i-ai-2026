# NorgesGruppen Object Detection — Complete Documentation

> Source: https://app.ainm.no/docs/norgesgruppen-data/*
> Fetched: 2026-03-19

---

## Competition Overview

- **Sponsor:** NorgesGruppen Data
- **Task:** Detect and classify grocery products on store shelves
- **Submission format:** Code upload (ZIP file with `run.py`)
- **Timeline:** Thu Mar 19 18:00 CET → Sun Mar 22 15:00 CET (69 hours)
- **Prize pool:** 1,000,000 NOK (shared across all 3 tasks)
- **Teams:** 1–4 members, roster locks after first submission

---

## Training Data

### COCO Dataset (`NM_NGD_coco_dataset.zip`, ~864 MB)

- **248 shelf images** from Norwegian grocery stores
- **~22,700 COCO-format bounding box annotations**
- **356 product categories** (category_id 0–355)
- **4 store sections:** Egg, Frokost, Knekkebrod, Varmedrikker
- **Image dimensions:** 2000 × 1500 pixels

### Product Reference Images (`NM_NGD_product_images.zip`, ~60 MB)

- **327 individual products** with multi-angle photos
- Angles: main, front, back, left, right, top, bottom
- Organized by barcode: `{product_code}/main.jpg`
- Includes `metadata.json` with product names and annotation counts

---

## COCO Annotation Format (`annotations.json`)

```json
{
  "images": [
    {
      "id": <int>,
      "file_name": "img_XXXXX.jpg",
      "width": 2000,
      "height": 1500
    }
  ],
  "categories": [
    {
      "id": <int 0-355>,
      "name": "<product name>",
      "supercategory": "product"
    }
  ],
  "annotations": [
    {
      "id": <int>,
      "image_id": <int>,
      "category_id": <int 0-355>,
      "bbox": [x, y, width, height],
      "area": <float>,
      "iscrowd": <0|1>,
      "product_code": "<barcode>",
      "product_name": "<name>",
      "corrected": <bool>
    }
  ]
}
```

**Key:** `bbox` is `[x, y, width, height]` in pixels (standard COCO format, top-left origin).

Note: category IDs go 0–355 (356 categories total), but docs also mention "id (0-356)" in one place. The authoritative count is **356 categories (0–355)**.

---

## Scoring

### Formula

```
Score = 0.7 × detection_mAP + 0.3 × classification_mAP
```

Both use **mAP@0.5** (Mean Average Precision at IoU threshold 0.5).

### Detection mAP (70% weight)

- Evaluates product **localization** regardless of category
- True positive: IoU ≥ 0.5 between prediction and ground truth (category ignored)
- Each prediction matches to the closest ground truth box

### Classification mAP (30% weight)

- Evaluates correct product **identification**
- True positive requires IoU ≥ 0.5 **AND** matching `category_id`
- 356 product categories (IDs 0–355)

### Detection-Only Strategy

Submitting `category_id: 0` for all predictions → max score **0.70** (70%).
Adding correct classification unlocks the remaining 30%.

Score range: 0.0 (worst) to 1.0 (perfect).

---

## Submission Format

### ZIP Structure

```
submission.zip
├── run.py          # REQUIRED entry point (must be at ZIP root!)
├── model.onnx      # Optional model weights
└── utils.py        # Optional helper code
```

### File Limits

| Constraint | Limit |
|---|---|
| Max uncompressed size | 420 MB |
| Max total files | 1000 |
| Max Python files | 10 |
| Max weight files | 3 |
| Allowed extensions | `.py, .json, .yaml, .yml, .cfg, .pt, .pth, .onnx, .safetensors, .npy` |

### run.py Interface

**Execution command:**
```bash
python run.py --input /data/images --output /output/predictions.json
```

**Input:** Directory of JPEG shelf images named `img_XXXXX.jpg` (e.g., `img_00042.jpg`)

**Output:** JSON array:
```json
[
  {
    "image_id": 42,
    "category_id": 0,
    "bbox": [120.5, 45.0, 80.0, 110.0],
    "score": 0.923
  }
]
```

| Field | Type | Description |
|---|---|---|
| `image_id` | int | Extracted from filename (e.g., `img_00042.jpg` → `42`) |
| `category_id` | int | 0–355 from training annotations |
| `bbox` | [x, y, w, h] | COCO format, pixels |
| `score` | float | Confidence 0–1 |

### Creating the ZIP (critical — most common error!)

**Linux/macOS:**
```bash
cd my_submission/
zip -r ../submission.zip . -x ".*" "__MACOSX/*"
```

**Verify:**
```bash
unzip -l submission.zip | head -10
# Should show run.py directly, NOT my_submission/run.py
```

---

## Sandbox Environment

### Hardware

| Resource | Spec |
|---|---|
| GPU | NVIDIA L4, 24 GB VRAM |
| CPU | 4 vCPU |
| RAM | 8 GB |
| CUDA | 12.4 |
| Python | 3.11 |
| Timeout | 300 seconds |
| Network | **Fully offline** (no internet access) |

### Pre-installed Packages (exact versions)

| Package | Version |
|---|---|
| PyTorch | 2.6.0+cu124 |
| torchvision | 0.21.0+cu124 |
| ultralytics | 8.1.0 |
| onnxruntime-gpu | 1.20.0 |
| opencv-python-headless | 4.9.0.80 |
| albumentations | 1.3.1 |
| Pillow | 10.2.0 |
| numpy | 1.26.4 |
| scipy | 1.12.0 |
| scikit-learn | 1.4.0 |
| pycocotools | 2.0.7 |
| ensemble-boxes | 1.0.9 |
| timm | 0.9.12 |
| supervision | 0.18.0 |
| safetensors | 0.4.2 |

**No `pip install` allowed at runtime.**

### GPU Auto-Detection

- `torch.cuda.is_available()` returns `True`
- No opt-in required
- For ONNX: use `["CUDAExecutionProvider", "CPUExecutionProvider"]`

---

## Available Frameworks & Models

### Pre-installed (direct .pt submission)

| Framework | Models |
|---|---|
| ultralytics 8.1.0 | YOLOv8n/s/m/l/x, YOLOv5u, RT-DETR |
| torchvision 0.21.0 | Faster R-CNN, RetinaNet, SSD, FCOS, Mask R-CNN |
| timm 0.9.12 | ResNet, EfficientNet, ViT, Swin, ConvNeXt backbones |

### NOT Included

YOLOv9, YOLOv10, YOLO11, Detectron2, MMDetection, HuggingFace Transformers

### Using Unsupported Models

1. **Export to ONNX** (opset ≤ 20)
2. **Include model class + state_dict weights** using standard PyTorch ops

---

## Security Restrictions

### Blocked Imports

`os, sys, subprocess, socket, ctypes, builtins, importlib, pickle, marshal, shelve, shutil, yaml, requests, urllib, http.client, multiprocessing, threading, signal, gc, code, codeop, pty`

### Blocked Operations

`eval(), exec(), compile(), __import__(), dangerous getattr()`

### Also Blocked

- ELF/Mach-O/PE binaries
- Symlinks
- Path traversal

### Workarounds

- Use `pathlib` instead of `os` for file operations
- Use `json` instead of `yaml`

---

## Submission Rate Limits

| Constraint | Limit |
|---|---|
| Concurrent submissions | 2 per team |
| Daily submissions | 3 per team |
| Infrastructure failure freebies | 2 per day (don't count against limit) |
| Reset time | Midnight UTC |

### Final Evaluation

- By default: highest-scoring submission is used
- Override: "Select for final" button on any completed submission

---

## Common Errors & Fixes

| Error | Fix |
|---|---|
| `run.py not found at zip root` | Zip the **contents**, not the folder |
| `Disallowed file type: __MACOSX/` | Use `zip -r ../sub.zip . -x ".*" "__MACOSX/*"` |
| `.bin` files rejected | Rename to `.pt` or convert to `.safetensors` |
| Security violations | Remove `subprocess`, `socket`, `os` imports; use `pathlib` |
| 300-second timeout | Ensure GPU usage or reduce model size |
| Exit code 137 (OOM) | 8 GB RAM limit; reduce batch size or use FP16 |

---

## Tips & Strategy Notes

1. **Start simple** — verify setup with random baseline first
2. **GPU headroom** — L4 with 24GB VRAM allows larger models (YOLOv8m/l/x feasible)
3. **FP16 quantization** — smaller weights + faster inference
4. **Memory management** — process images one at a time; use `torch.no_grad()`
5. **Local testing** — always test before uploading
6. **Version pinning** — match sandbox package versions or export to ONNX
7. **YOLO pretrained caveat** — pretrained COCO model outputs class IDs 0–79, NOT product IDs 0–355. Must fine-tune with `nc=357` (or 356 — verify)
8. **Detection-only is viable** — gets you 70% max score, good starting point
9. **Product reference images** — 327 products with multi-angle photos can aid classification
10. **ensemble-boxes** is pre-installed — consider model ensembling

---

## Google Cloud Resources (for training)

- Selected teams get **@gcplab.me** account with dedicated GCP project
- **No credit limits** — no billing setup needed
- Cloud Shell: Linux VM, 5 GB persistent home, Python 3, Docker, gcloud CLI
- Compute Engine available for GPU training
- Vertex AI with Gemini models available
- Recommended region: `europe-north1`

---

## Rules Highlights

- **Permitted:** AI coding assistants, public models/datasets, research papers, OSS libraries
- **Prohibited:** Sharing solutions between teams, multiple accounts, circumventing rate limits, hardcoding test responses
- **Prize eligibility:** Vipps verification + public code repo (MIT license) + URL submitted before deadline
- **MCP integration:** `claude mcp add --transport http nmiai https://mcp-docs.ainm.no/mcp`

---

## Reference Images from Docs

- `/docs/shelf-annotations-full.png` — example of fully annotated shelf
- `/docs/shelf-annotations-partial.png` — example of partially annotated shelf
