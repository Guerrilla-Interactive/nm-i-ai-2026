# NorgesGruppen — Object Detection

## Overview
Detect and classify grocery products on store shelves using computer vision.

## Setup
- Training data: 248 images, ~22,700 COCO-format annotations, 356 categories
- Sandbox GPU: NVIDIA L4 (24GB VRAM)
- Pre-installed: PyTorch 2.6.0, YOLOv8, ONNX Runtime, OpenCV
- Max weights: 420MB, timeout: 300s

## Submission
- Submit `.zip` with `run.py` at root + model weights
- **run.py must be at zip root (not in subfolder)**

## Scoring
- 70% detection (bounding box at IoU ≥ 0.5)
- 30% classification (correct product ID)

## Blocked imports
`os`, `sys`, `subprocess`, `socket`, `pickle`, `yaml`, `requests`, `multiprocessing`
Use `pathlib` instead of `os`, `json` instead of `yaml`.
