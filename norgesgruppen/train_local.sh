#!/bin/bash
# train_local.sh — Setup venv + train YOLOv8 on Apple Silicon MPS
# Usage: bash train_local.sh [model] [epochs] [imgsz] [batch]
set -euo pipefail

cd /Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen

MODEL="${1:-yolov8x.pt}"
EPOCHS="${2:-200}"
IMGSZ="${3:-640}"
BATCH="${4:-4}"
VENV_DIR=".venv"

echo "=== NM i AI 2026 — Local Training Setup ==="
echo "Model: $MODEL | Epochs: $EPOCHS | ImgSz: $IMGSZ | Batch: $BATCH"

# Step 1: Create venv if needed
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating venv with homebrew Python 3.13..."
    /opt/homebrew/bin/python3.13 -m venv "$VENV_DIR"
fi

# Activate
source "$VENV_DIR/bin/activate"

# Step 2: Install dependencies
if ! python -c "import ultralytics" 2>/dev/null; then
    echo "Installing PyTorch + ultralytics..."
    pip install --upgrade pip
    pip install torch torchvision
    pip install ultralytics opencv-python-headless onnxruntime pycocotools
fi

# Step 3: Verify MPS
python -c "
import torch
if torch.backends.mps.is_available():
    print('MPS backend: AVAILABLE')
else:
    print('WARNING: MPS not available, will fall back to CPU')
print(f'PyTorch: {torch.__version__}')
"

# Step 4: Check dataset
if [ ! -f "dataset.yaml" ]; then
    echo "ERROR: dataset.yaml not found. Run convert_coco_to_yolo.py first."
    echo "  python convert_coco_to_yolo.py"
    exit 1
fi

# Step 5: Train
echo "Starting training..."
python -c "
from ultralytics import YOLO
import torch

device = 'mps' if torch.backends.mps.is_available() else 'cpu'
print(f'Training on: {device}')

model = YOLO('$MODEL')
results = model.train(
    data='dataset.yaml',
    epochs=$EPOCHS,
    imgsz=$IMGSZ,
    batch=$BATCH,
    device=device,
    patience=30,
    save=True,
    project='runs/train',
    name='norgesgruppen_local',
    exist_ok=True,
)

# Export to ONNX
print('Exporting to ONNX...')
best = YOLO('runs/train/norgesgruppen_local/weights/best.pt')
best.export(format='onnx', imgsz=$IMGSZ)
print('Done! Best model: runs/train/norgesgruppen_local/weights/best.pt')
print('ONNX export: runs/train/norgesgruppen_local/weights/best.onnx')
"
