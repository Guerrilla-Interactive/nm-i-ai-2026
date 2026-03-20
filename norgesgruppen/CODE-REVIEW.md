# Code Review — NorgesGruppen Pipeline

Reviewed: 2026-03-19

## submission/run.py (CRITICAL — sandbox inference)

### Bugs Fixed
1. **Removed unused `math` import** — dead code cleanup
2. **Fixed category_map.json loading crash** — `convert_coco_to_yolo.py` saves a JSON **list** `[0, 1, 2, ..., 355]`, but `run.py` called `.items()` which only works on dicts. Now handles both list and dict formats.

### Verified Correct
- Uses `--input` / `--output` argparse flags (matches sandbox invocation)
- Zero blocked imports (no os, sys, subprocess, socket, pickle, yaml, requests, multiprocessing, threading)
- ONNX Runtime with CUDAExecutionProvider + CPUExecutionProvider fallback
- Letterbox: BGR→RGB, aspect-ratio resize, centered gray (114,114,114) padding
- YOLOv8 output decoding: shape `(1, 4+nc, 8400)` → transpose → boxes + scores
- NMS via `cv2.dnn.NMSBoxes` with `cv2` version-safe index flattening
- Coordinate undo: subtract pad → divide by scale → cx,cy,w,h → x,y,w,h (COCO top-left)
- Box clipping to image boundaries with degenerate box rejection
- image_id extraction: `img_00042.jpg` → `42` via digit extraction
- Low confidence threshold (0.01) to maximize recall
- Correct COCO JSON output format

## norgesgruppen/run.py (canonical copy)

### Changes
- **Replaced entirely** with the submission/run.py version. Old version had positional args (wrong), CONF_THRESHOLD=0.25 (too high), TorchScript fallback (unnecessary complexity), and `time` import.

## test_inference.py

### Bugs Fixed
1. **Fixed run_submission() argument passing** — was passing positional args but run.py uses `--input`/`--output` flags. Inference test would crash immediately.
2. **Fixed detection evaluation** — now uses class-agnostic mAP@0.5 (all categories collapsed to single "product" class), matching the competition's 70% detection component.
3. **Added proper classification mAP** — added `evaluate_classification_map()` using pycocotools per-category mAP@0.5 (the real 30% metric), replacing simple accuracy.
4. **Removed unused `tempfile` import**

## export_onnx.py

### Bugs Fixed
1. **Fixed cross-filesystem move** — `Path.rename()` fails across filesystems. Changed to `shutil.move()`.

### Verified Correct
- FP16 `--half` flag works
- ONNX verification loads model and prints input/output tensor shapes
- Size check against 420MB limit

## train.py

### Verified Correct (no changes needed)
- All hyperparameters match RESEARCH-MASTER.md recommendations
- Command-line flags for --epochs, --imgsz, --model, --batch, --lr, --patience, --name
- ONNX export after training via `export_onnx()`
- `--resume` flag for interrupted training
- `--prepare-submission` copies run.py + category_map.json + best.onnx to submission/
- `prepare_submission` correctly references `BASE_DIR / "run.py"` (now the canonical copy)

## convert_coco_to_yolo.py

### Verified Correct (no changes needed)
- COCO bbox `[x, y, w, h]` pixels → YOLO `[cx, cy, w, h]` normalized 0-1: correct formula
- Category mapping: sorts by ID, builds contiguous 0-indexed mapping
- Saves `category_map.json` as list (run.py now handles this)
- 90/10 train/val split with seed
- Creates data/images/{train,val}/ and data/labels/{train,val}/
- Generates norgesgruppen.yaml (manual YAML, no yaml import needed)
- Handles symlink vs copy for images
- Clamps normalized coords to [0,1], skips degenerate boxes

## package_submission.py

### Verified Correct (no changes needed)
- Validates all constraints: 420MB, 1000 files, 10 .py, 3 weight files
- Checks allowed extensions
- Rejects hidden files and __MACOSX artifacts
- run.py at ZIP root verification
- Prints size breakdown

## Summary of All Changes

| File | Changes |
|---|---|
| submission/run.py | Removed unused `math` import; fixed category_map list/dict loading |
| norgesgruppen/run.py | Replaced with canonical copy of submission/run.py |
| test_inference.py | Fixed `--input`/`--output` flags; added class-agnostic detection mAP; added per-category classification mAP; removed unused `tempfile` |
| export_onnx.py | Fixed `rename()` → `shutil.move()` for cross-filesystem safety |
| train.py | No changes needed |
| convert_coco_to_yolo.py | No changes needed |
| package_submission.py | No changes needed |
