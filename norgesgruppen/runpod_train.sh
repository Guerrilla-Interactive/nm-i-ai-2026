#!/bin/bash
set -euo pipefail

# =============================================================================
# RunPod Training Script — NorgesGruppen Object Detection (YOLO11x @ 1280)
# =============================================================================
# Self-contained script for training on a fresh RunPod GPU pod.
#
# Prerequisites:
#   - Upload this repo to /workspace/nm-i-ai-2026/
#   - Upload dataset to /workspace/data/ with:
#       /workspace/data/annotations.json   (COCO format)
#       /workspace/data/images/            (all images)
#
# Usage:
#   chmod +x runpod_train.sh && ./runpod_train.sh
# =============================================================================

WORKSPACE="/workspace"
REPO_DIR="${WORKSPACE}/nm-i-ai-2026/norgesgruppen"
DATA_SRC="${WORKSPACE}/data"
DATA_DST="${REPO_DIR}/data"
RUN_NAME="yolo11x_1280_v1"

echo "============================================================"
echo "  NorgesGruppen YOLO11x Training — RunPod"
echo "============================================================"
echo "  Repo:     ${REPO_DIR}"
echo "  Data src: ${DATA_SRC}"
echo "  Run name: ${RUN_NAME}"
echo "  GPU:      $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'unknown')"
echo "============================================================"
echo ""

# -----------------------------------------------------------------------
# Step 1: Install dependencies
# -----------------------------------------------------------------------
echo "[1/6] Installing dependencies..."
pip install --quiet ultralytics pycocotools opencv-python-headless onnxruntime onnxslim
echo "  Done."
echo ""

# -----------------------------------------------------------------------
# Step 2: Set up data directory structure
# -----------------------------------------------------------------------
echo "[2/6] Setting up data directory..."

# Verify source data exists
if [ ! -f "${DATA_SRC}/annotations.json" ]; then
    echo "ERROR: ${DATA_SRC}/annotations.json not found!"
    echo "Upload your dataset to ${DATA_SRC}/ first."
    echo "Expected structure:"
    echo "  ${DATA_SRC}/annotations.json"
    echo "  ${DATA_SRC}/images/*.jpg"
    exit 1
fi

if [ ! -d "${DATA_SRC}/images" ]; then
    echo "ERROR: ${DATA_SRC}/images/ directory not found!"
    exit 1
fi

IMG_COUNT=$(ls "${DATA_SRC}/images/"*.jpg 2>/dev/null | wc -l || echo 0)
echo "  Found ${IMG_COUNT} images in ${DATA_SRC}/images/"

# Create symlink so convert_coco_to_yolo.py finds the data
mkdir -p "${DATA_DST}"

# Link annotations.json
if [ ! -f "${DATA_DST}/annotations.json" ]; then
    ln -sf "${DATA_SRC}/annotations.json" "${DATA_DST}/annotations.json"
fi

# Link images directory
if [ ! -d "${DATA_DST}/images" ] || [ -L "${DATA_DST}/images" ]; then
    rm -f "${DATA_DST}/images" 2>/dev/null || true
    ln -sf "${DATA_SRC}/images" "${DATA_DST}/images"
fi

echo "  Data linked: ${DATA_DST}/ → ${DATA_SRC}/"
echo ""

# -----------------------------------------------------------------------
# Step 3: Convert COCO annotations to YOLO format
# -----------------------------------------------------------------------
echo "[3/6] Converting COCO → YOLO format..."
cd "${REPO_DIR}"

# Use --copy on RunPod since symlinks to symlinks can be fragile
python convert_coco_to_yolo.py \
    --annotations "${DATA_DST}/annotations.json" \
    --images-dir "${DATA_DST}/images" \
    --val-ratio 0.1 \
    --seed 42 \
    --copy

echo "  Conversion complete."
echo ""

# -----------------------------------------------------------------------
# Step 4: Train YOLO11x with optimized hyperparameters
# -----------------------------------------------------------------------
echo "[4/6] Starting training: YOLO11x @ 1280px..."
echo "  This will take a while. Monitor with: tail -f runs/${RUN_NAME}/results.csv"
echo ""

cd "${REPO_DIR}"
python -c "
from ultralytics import YOLO
from pathlib import Path
import time
import sys

BASE_DIR = Path('${REPO_DIR}')
DATA_YAML = BASE_DIR / 'norgesgruppen.yaml'
RUNS_DIR = BASE_DIR / 'runs'

print(f'Dataset config: {DATA_YAML}')
print(f'Output dir: {RUNS_DIR / \"${RUN_NAME}\"}')
print()

model = YOLO('yolo11x.pt')

start = time.time()

# Try imgsz=1280 first, fallback to 960 on OOM
imgsz = 1280
try:
    results = model.train(
        data=str(DATA_YAML),
        epochs=200,
        imgsz=imgsz,
        batch=-1,                # Auto batch — let YOLO maximize for GPU memory
        amp=True,                # Mixed precision (faster + less memory)
        patience=30,             # Early stopping patience (faster convergence check)
        # === Learning Rate ===
        lr0=0.001,
        lrf=0.01,                # Final LR = lr0 * 0.01
        warmup_epochs=5,         # Gentler warmup for 1280px
        warmup_momentum=0.8,
        # === Augmentation (aggressive for 248 images) ===
        mosaic=1.0,              # 4-image mosaic (critical for tiny dataset)
        close_mosaic=10,         # Disable mosaic for last 10 epochs
        mixup=0.15,              # Blend two images
        copy_paste=0.1,          # Copy-paste augmentation
        scale=0.9,               # Random scale +/-90%
        degrees=10.0,            # Random rotation +/-10 degrees
        translate=0.2,           # Random translation +/-20%
        shear=2.0,               # Random shear +/-2 degrees
        flipud=0.0,              # NO vertical flip (shelf images have orientation)
        fliplr=0.5,              # Horizontal flip
        hsv_h=0.015,             # Hue augmentation
        hsv_s=0.7,               # Saturation augmentation
        hsv_v=0.4,               # Brightness augmentation
        erasing=0.1,             # Random erasing
        # === Regularization ===
        label_smoothing=0.1,     # Helps with 356 similar-looking classes
        weight_decay=0.0005,
        dropout=0.0,             # YOLO default
        # === Output ===
        project=str(RUNS_DIR),
        name='${RUN_NAME}',
        exist_ok=True,
        save=True,
        save_period=25,          # Checkpoint every 25 epochs
        plots=True,
        verbose=True,
    )
except RuntimeError as e:
    if 'out of memory' in str(e).lower() or 'CUDA' in str(e):
        print()
        print('=' * 60)
        print('OOM at imgsz=1280 — retrying with imgsz=960')
        print('=' * 60)
        print()
        import torch
        torch.cuda.empty_cache()
        imgsz = 960
        model = YOLO('yolo11x.pt')
        results = model.train(
            data=str(DATA_YAML),
            epochs=200,
            imgsz=imgsz,
            batch=-1,
            amp=True,
            patience=30,
            lr0=0.001,
            lrf=0.01,
            warmup_epochs=5,
            warmup_momentum=0.8,
            mosaic=1.0,
            close_mosaic=10,
            mixup=0.15,
            copy_paste=0.1,
            scale=0.9,
            degrees=10.0,
            translate=0.2,
            shear=2.0,
            flipud=0.0,
            fliplr=0.5,
            hsv_h=0.015,
            hsv_s=0.7,
            hsv_v=0.4,
            erasing=0.1,
            label_smoothing=0.1,
            weight_decay=0.0005,
            dropout=0.0,
            project=str(RUNS_DIR),
            name='${RUN_NAME}',
            exist_ok=True,
            save=True,
            save_period=25,
            plots=True,
            verbose=True,
        )
    else:
        raise

elapsed = time.time() - start
print()
print('=' * 60)
print('TRAINING COMPLETE')
try:
    d = results.results_dict
    print(f'  mAP50:     {d.get(\"metrics/mAP50(B)\", \"N/A\")}')
    print(f'  mAP50-95:  {d.get(\"metrics/mAP50-95(B)\", \"N/A\")}')
    print(f'  Precision: {d.get(\"metrics/precision(B)\", \"N/A\")}')
    print(f'  Recall:    {d.get(\"metrics/recall(B)\", \"N/A\")}')
except Exception as e:
    print(f'  Metrics: {e}')
print(f'  Elapsed: {elapsed/3600:.1f}h ({elapsed/60:.0f}m)')
print(f'  Weights: {RUNS_DIR / \"${RUN_NAME}\" / \"weights\" / \"best.pt\"}')
print(f'  Trained at imgsz={imgsz}')
print('=' * 60)

# Save actual imgsz used for export step
with open(str(RUNS_DIR / '${RUN_NAME}' / 'imgsz_used.txt'), 'w') as f:
    f.write(str(imgsz))
"

echo ""

# -----------------------------------------------------------------------
# Step 5: Export best model to ONNX
# -----------------------------------------------------------------------
echo "[5/6] Exporting best.pt → ONNX..."

BEST_PT="${REPO_DIR}/runs/${RUN_NAME}/weights/best.pt"
IMGSZ_FILE="${REPO_DIR}/runs/${RUN_NAME}/imgsz_used.txt"

if [ ! -f "${BEST_PT}" ]; then
    echo "ERROR: best.pt not found at ${BEST_PT}"
    echo "Training may have failed. Check logs above."
    exit 1
fi

# Read actual imgsz used during training
EXPORT_IMGSZ=1280
if [ -f "${IMGSZ_FILE}" ]; then
    EXPORT_IMGSZ=$(cat "${IMGSZ_FILE}")
fi

echo "  Exporting with imgsz=${EXPORT_IMGSZ}..."

python -c "
from ultralytics import YOLO
model = YOLO('${BEST_PT}')
model.export(format='onnx', imgsz=${EXPORT_IMGSZ}, simplify=True)
"

BEST_ONNX="${REPO_DIR}/runs/${RUN_NAME}/weights/best.onnx"

echo ""
echo "============================================================"
echo "  TRAINING + EXPORT COMPLETE (v1)"
echo "============================================================"

if [ -f "${BEST_ONNX}" ]; then
    SIZE_MB=$(python -c "import os; print(f'{os.path.getsize(\"${BEST_ONNX}\") / 1024 / 1024:.1f}')")
    echo "  ONNX model: ${BEST_ONNX}"
    echo "  Size: ${SIZE_MB} MB (limit: 420 MB)"
else
    echo "  WARNING: ONNX export may have failed. Check for .onnx file in:"
    echo "    ${REPO_DIR}/runs/${RUN_NAME}/weights/"
    ls -la "${REPO_DIR}/runs/${RUN_NAME}/weights/" 2>/dev/null || true
fi

echo ""
echo "  Copy best model to workspace root:"
cp "${BEST_PT}" "${WORKSPACE}/best_v1.pt" 2>/dev/null || true
cp "${BEST_ONNX}" "${WORKSPACE}/best_v1.onnx" 2>/dev/null || true

# -----------------------------------------------------------------------
# Step 6: Second training run for model soup (different lr + seed)
# -----------------------------------------------------------------------
RUN_NAME_V2="yolo11x_1280_v2"
echo ""
echo "[6/6] Starting second training run for model soup: ${RUN_NAME_V2}"
echo "  lr0=0.0005, seed=123"
echo ""

cd "${REPO_DIR}"
python -c "
from ultralytics import YOLO
from pathlib import Path
import time

BASE_DIR = Path('${REPO_DIR}')
DATA_YAML = BASE_DIR / 'norgesgruppen.yaml'
RUNS_DIR = BASE_DIR / 'runs'

model = YOLO('yolo11x.pt')

start = time.time()

imgsz = ${EXPORT_IMGSZ}  # Use same imgsz as v1 (needed for model soup)

try:
    results = model.train(
        data=str(DATA_YAML),
        epochs=200,
        imgsz=imgsz,
        batch=-1,
        amp=True,
        patience=30,
        seed=123,
        # === Learning Rate (more conservative) ===
        lr0=0.0005,
        lrf=0.01,
        warmup_epochs=5,
        warmup_momentum=0.8,
        # === Same augmentation ===
        mosaic=1.0,
        close_mosaic=10,
        mixup=0.15,
        copy_paste=0.1,
        scale=0.9,
        degrees=10.0,
        translate=0.2,
        shear=2.0,
        flipud=0.0,
        fliplr=0.5,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        erasing=0.1,
        label_smoothing=0.1,
        weight_decay=0.0005,
        dropout=0.0,
        project=str(RUNS_DIR),
        name='${RUN_NAME_V2}',
        exist_ok=True,
        save=True,
        save_period=25,
        plots=True,
        verbose=True,
    )
except RuntimeError as e:
    if 'out of memory' in str(e).lower() or 'CUDA' in str(e):
        print('OOM — skipping v2 run. Use v1 only.')
        import sys; sys.exit(0)
    else:
        raise

elapsed = time.time() - start
print()
print('=' * 60)
print(f'TRAINING v2 COMPLETE ({elapsed/3600:.1f}h)')
try:
    d = results.results_dict
    print(f'  mAP50:     {d.get(\"metrics/mAP50(B)\", \"N/A\")}')
    print(f'  mAP50-95:  {d.get(\"metrics/mAP50-95(B)\", \"N/A\")}')
except Exception as e:
    print(f'  Metrics: {e}')
print('=' * 60)
"

# Copy v2 best weights
BEST_PT_V2="${REPO_DIR}/runs/${RUN_NAME_V2}/weights/best.pt"
cp "${BEST_PT_V2}" "${WORKSPACE}/best_v2.pt" 2>/dev/null || true

echo ""
echo "============================================================"
echo "  ALL TRAINING COMPLETE"
echo "============================================================"
echo ""
echo "  v1 weights: ${WORKSPACE}/best_v1.pt"
echo "  v2 weights: ${WORKSPACE}/best_v2.pt"
echo ""
echo "  Next: Run model soup to average weights:"
echo "    python model_soup.py ${WORKSPACE}/best_v1.pt ${WORKSPACE}/best_v2.pt"
echo ""
echo "  Or download best.onnx directly:"
echo "    scp root@<POD_IP>:${WORKSPACE}/best_v1.onnx ."
echo "============================================================"
