# Research: Blocked Imports & run.py Architecture

## 1. Blocked Imports Analysis

The sandbox blocks: `os`, `sys`, `subprocess`, `socket`, `pickle`, `yaml`, `requests`, `multiprocessing`

### Ultralytics (YOLOv8) Internal Dependencies

**ALL 8 blocked modules are used by ultralytics.** Most are imported eagerly at module load time in `ultralytics/utils/__init__.py`:

| Module | Used? | Where |
|---|---|---|
| `os` | YES | utils/__init__.py, torch_utils.py, data/utils.py, engine/model.py |
| `sys` | YES | utils/__init__.py |
| `subprocess` | YES | utils/downloads.py, data/utils.py |
| `socket` | YES | utils/__init__.py |
| `pickle` | YES | Dataset caching |
| `yaml` | YES | utils/__init__.py (CSafeLoader/CSafeDumper) |
| `requests` | YES | utils/downloads.py |
| `multiprocessing` | YES | utils/downloads.py, data/utils.py |

**Verdict: `from ultralytics import YOLO` is impossible in the sandbox.**

### Workaround Analysis

- **Monkey-patching**: Not viable. `os`/`sys`/`socket`/`yaml` are imported at module load and actively used (`os.environ`, `socket.gethostname()`, `yaml.safe_load()`). Stubbing causes runtime crashes.
- **Custom import hook**: Theoretically possible but impractical — dozens of call sites to intercept.
- **ONNX Runtime inference**: **The correct approach.** Export model to ONNX outside sandbox, run with `onnxruntime` + `numpy` + `cv2` only.
- **Pure PyTorch**: Also viable if the model architecture is loaded without ultralytics (e.g., TorchScript export). But ONNX is simpler.

## 2. Recommended Architecture: ONNX Runtime Inference

### Export (done locally, not in sandbox)
```bash
yolo export model=best.pt format=onnx imgsz=640 simplify=True
```

### Preprocessing (letterbox + normalize)
1. BGR → RGB (`cv2.cvtColor`)
2. Letterbox resize: maintain aspect ratio, pad with `(114, 114, 114)` gray, centered
3. Normalize to `[0, 1]` float32
4. HWC → CHW transpose
5. Add batch dimension → `(1, 3, 640, 640)`

### Postprocessing (decode + NMS)
Raw ONNX output shape: `(1, num_features, num_detections)` where num_features = 4 + num_classes.
- For 356 categories: `(1, 360, 8400)` — 4 box coords (cx, cy, w, h) + 356 class scores
- Transpose to `(8400, 360)`
- Get max class score + class index per detection
- Filter by confidence threshold
- Subtract padding offset, scale back to original image coordinates
- Convert cx,cy,w,h → x,y,w,h (top-left)
- Apply NMS via `cv2.dnn.NMSBoxes`

### Category ID Mapping
This competition has **356 custom categories** (not standard COCO 80). The category mapping must come from the training data's COCO annotation file. YOLOv8 uses 0-indexed contiguous class IDs internally, so we need a mapping from `yolo_class_index → coco_category_id`.

This mapping should be saved as a JSON file alongside the model weights.

## 3. run.py Interface

### Arguments
Based on standard NM i AI / Kaggle competition patterns:
- `run.py` receives the input image directory and output file path as arguments
- Likely invoked as: `python run.py <input_dir> <output_file>`
- Or via argparse with named arguments

### Expected Output: COCO Detection Results Format
A flat JSON array:
```json
[
  {
    "image_id": 42,
    "category_id": 1,
    "bbox": [100.0, 200.0, 50.0, 80.0],
    "score": 0.95
  }
]
```

Fields:
- **image_id** (int): Derived from filename (e.g., `000042.jpg` → 42, or stem as int)
- **category_id** (int): COCO category ID from training annotations (1-indexed)
- **bbox** `[x_min, y_min, width, height]`: Absolute pixels, top-left corner
- **score** (float): Confidence 0.0–1.0

### How image_ids are determined
Most likely: the integer stem of the filename (e.g., `12.jpg` → `image_id: 12`). Need to verify from training data annotations.

## 4. Allowed Imports

Safe to use:
- `pathlib` (Path) — file system operations
- `json` — read/write JSON
- `numpy` — array operations
- `cv2` (OpenCV) — image I/O, resize, NMS
- `onnxruntime` — ONNX model inference
- `torch` — PyTorch (if using TorchScript path)
- `PIL` (Pillow) — alternative image I/O
- `argparse` — CLI argument parsing
- Standard library: `math`, `collections`, `typing`, `time`, `functools`, `itertools`

## 5. Skeleton run.py

See `run.py` in this directory for the complete implementation skeleton.

## 6. Key Decisions & Open Questions

1. **Input size**: Default 640x640. Check ONNX model's actual input shape at runtime.
2. **Confidence threshold**: Start with 0.25, tune based on leaderboard feedback.
3. **NMS IoU threshold**: Start with 0.45.
4. **Category mapping**: Must export from training COCO annotations → JSON file.
5. **image_id extraction**: Verify from test data (integer filename stem most likely).
6. **Model size**: Must fit under 420MB total zip. ONNX models are typically smaller than PyTorch.
7. **Inference time**: 300s timeout for all test images. L4 GPU + ONNX should be fast enough.
8. **GPU acceleration**: Use `onnxruntime-gpu` with CUDAExecutionProvider if available, fall back to CPU.
