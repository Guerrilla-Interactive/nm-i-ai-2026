# NorgesGruppen Submission Status Report

**Date:** 2026-03-21
**Branch:** doey/team-3-0321-0838

## Checklist

| Check | Status | Details |
|-------|--------|---------|
| submission/ directory exists | PASS | Present |
| run.py in submission/ | PASS | 473 lines, 3-model ensemble with WBF |
| category_map.json in submission/ | PASS | 356 categories (correct) |
| best.onnx in submission/ | **FAIL** | **NOT FOUND** |
| best_x.onnx in submission/ | **FAIL** | **NOT FOUND** |
| best_s.onnx in submission/ | **FAIL** | **NOT FOUND** |
| No ONNX files anywhere in norgesgruppen/ | **FAIL** | **No .onnx files found in entire directory** |
| Blocked imports absent | PASS | No ultralytics/os/sys/subprocess/socket/pickle/yaml/requests |
| Allowed imports only | PASS | Uses: argparse, json, time, pathlib, cv2, numpy, onnxruntime (all OK) |
| ensemble_boxes import | WARN | Third-party `ensemble_boxes` imported but wrapped in try/except with NMS fallback — OK |
| COCO-format JSON output | PASS | Outputs `[{image_id, category_id, bbox:[x,y,w,h], score}]` |
| Input via --input/--output args | PASS | `argparse` with `--input` (image dir) and `--output` (JSON path) |
| Total model size < 420MB | **N/A** | No models present to measure |
| Time-budget awareness | PASS | 275s limit with progressive model dropping at 60%/80% thresholds |

## Critical Issues

1. **NO ONNX MODEL FILES** — The submission directory contains only `run.py` and `category_map.json`. All three expected model files (`best_x.onnx`, `best.onnx`, `best_s.onnx`) are missing. The run.py gracefully handles missing models (writes empty output), but the submission would produce zero detections and score 0.

## Minor Notes

- `ensemble_boxes` package may not be available in sandbox — but the fallback NMS merge path handles this correctly.
- The script uses `time.monotonic()` for time tracking — standard library, no issue.
- `package_submission.py` imports `validate_submission` which is a separate file (not checked here).

## Verdict

**NOT READY** — ONNX model weights must be added to `submission/` before packaging and uploading. The inference code itself looks correct and sandbox-compliant.
