"""
NM i AI 2026 — NorgesGruppen Object Detection: 3-Model Ensemble
Runs YOLO11x (1280px), YOLOv8m (640px), YOLOv8s (640px) and merges
detections with Weighted Box Fusion (WBF). Time-budget aware: drops
slower models as deadline approaches.
"""
import argparse
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

import cv2
import numpy as np
import onnxruntime as ort

# Try to import WBF; fall back to per-class NMS if unavailable
try:
    from ensemble_boxes import weighted_boxes_fusion
    HAS_WBF = True
except ImportError:
    HAS_WBF = False

# --- Constants ---
CONF_THRESH = 0.005
NMS_IOU_THRESH = 0.55
WBF_IOU_THRESH = 0.55
WBF_SKIP_BOX_THRESH = 0.001
PAD_COLOR = (114, 114, 114)
TIME_LIMIT = 275.0  # 300s sandbox minus 25s safety margin

# Model configs: (filename, WBF weight)
MODEL_CONFIGS = [
    ("best_x.onnx", 1.0),   # YOLO11x @ 1280px — primary
    ("best.onnx",   0.7),   # YOLOv8m @ 640px  — secondary
    ("best_s.onnx", 0.5),   # YOLOv8s @ 640px  — tertiary
]


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def letterbox(img: np.ndarray, target_size: int) -> Tuple[np.ndarray, float, int, int]:
    """Resize with letterbox padding. Returns (padded, scale, pad_left, pad_top)."""
    h, w = img.shape[:2]
    scale = min(target_size / h, target_size / w)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))

    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_w = target_size - new_w
    pad_h = target_size - new_h
    top = pad_h // 2
    left = pad_w // 2

    padded = cv2.copyMakeBorder(
        resized, top, pad_h - top, left, pad_w - left,
        cv2.BORDER_CONSTANT, value=PAD_COLOR,
    )
    return padded, scale, left, top


def preprocess(img_bgr: np.ndarray, target_size: int) -> Tuple[np.ndarray, float, int, int]:
    """BGR image -> ONNX input tensor (1,3,H,W) float32 [0,1]."""
    padded, scale, pad_left, pad_top = letterbox(img_bgr, target_size)
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    blob = rgb.astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))   # HWC -> CHW
    blob = np.expand_dims(blob, axis=0)     # add batch dim
    return blob, scale, pad_left, pad_top


# ---------------------------------------------------------------------------
# Postprocessing
# ---------------------------------------------------------------------------

def postprocess(
    output: np.ndarray,
    orig_w: int,
    orig_h: int,
    scale: float,
    pad_left: int,
    pad_top: int,
    category_map: Dict[int, int],
    conf_thresh: float = CONF_THRESH,
) -> List[Dict[str, Any]]:
    """
    Decode YOLO ONNX output -> list of {category_id, bbox:[x,y,w,h], score}.
    Output shape: [1, 360, num_anchors] -> transpose to [num_anchors, 360].
    First 4 values: cx, cy, w, h. Remaining 356: class scores.
    """
    # [1, 360, N] -> [N, 360]
    pred = output[0].T

    boxes_cxcywh = pred[:, :4]
    class_scores = pred[:, 4:]

    max_scores = np.max(class_scores, axis=1)
    class_ids = np.argmax(class_scores, axis=1)

    # Filter by confidence
    mask = max_scores > conf_thresh
    boxes_cxcywh = boxes_cxcywh[mask]
    max_scores = max_scores[mask]
    class_ids = class_ids[mask]

    if len(boxes_cxcywh) == 0:
        return []

    # cx,cy,w,h -> x,y,w,h (top-left)
    boxes_xywh = np.copy(boxes_cxcywh)
    boxes_xywh[:, 0] = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
    boxes_xywh[:, 1] = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2

    # Per-class NMS: offset boxes by class so different classes don't suppress
    max_coord = max(
        boxes_xywh[:, 0].max() + boxes_xywh[:, 2].max(),
        boxes_xywh[:, 1].max() + boxes_xywh[:, 3].max(),
    ) + 1.0
    boxes_for_nms = boxes_xywh.copy()
    boxes_for_nms[:, 0] += class_ids.astype(np.float32) * max_coord
    boxes_for_nms[:, 1] += class_ids.astype(np.float32) * max_coord

    indices = cv2.dnn.NMSBoxes(
        boxes_for_nms.tolist(),
        max_scores.tolist(),
        conf_thresh,
        NMS_IOU_THRESH,
    )

    if len(indices) == 0:
        return []
    if isinstance(indices, np.ndarray):
        indices = indices.flatten()

    detections = []
    for idx in indices:
        x, y, w, h = boxes_xywh[idx]
        score = float(max_scores[idx])
        yolo_class_id = int(class_ids[idx])

        # Undo letterbox: remove padding then undo scale
        x_orig = (float(x) - pad_left) / scale
        y_orig = (float(y) - pad_top) / scale
        w_orig = float(w) / scale
        h_orig = float(h) / scale

        # Clip to image boundaries
        x_orig = max(0.0, x_orig)
        y_orig = max(0.0, y_orig)
        w_orig = min(w_orig, orig_w - x_orig)
        h_orig = min(h_orig, orig_h - y_orig)

        if w_orig <= 0 or h_orig <= 0:
            continue

        coco_cat_id = category_map.get(yolo_class_id, yolo_class_id)

        detections.append({
            "category_id": int(coco_cat_id),
            "bbox": [round(x_orig, 2), round(y_orig, 2),
                     round(w_orig, 2), round(h_orig, 2)],
            "score": round(score, 5),
        })

    return detections


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_model(model_path: Path):
    """Load ONNX model. Returns (session, input_name, input_size) or None."""
    if not model_path.exists():
        return None
    try:
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session = ort.InferenceSession(
            str(model_path), opts,
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        input_name = session.get_inputs()[0].name
        input_shape = session.get_inputs()[0].shape
        # Auto-detect input size from ONNX metadata
        input_size = 640
        if input_shape and len(input_shape) == 4 and isinstance(input_shape[2], int):
            input_size = input_shape[2]
        return session, input_name, input_size
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Single-model inference
# ---------------------------------------------------------------------------

def run_single_model(
    img_bgr: np.ndarray,
    session: ort.InferenceSession,
    input_name: str,
    input_size: int,
    category_map: Dict[int, int],
) -> List[Dict[str, Any]]:
    """Run one model on a full image, return COCO detections."""
    orig_h, orig_w = img_bgr.shape[:2]
    blob, scale, pad_left, pad_top = preprocess(img_bgr, input_size)
    outputs = session.run(None, {input_name: blob})
    return postprocess(
        outputs[0], orig_w, orig_h, scale, pad_left, pad_top, category_map,
    )


# ---------------------------------------------------------------------------
# Ensemble merging
# ---------------------------------------------------------------------------

def merge_ensemble_wbf(
    model_dets_list: List[List[Dict[str, Any]]],
    model_weights: List[float],
    img_w: int,
    img_h: int,
) -> List[Dict[str, Any]]:
    """Merge detections from multiple models using WBF."""
    if not model_dets_list:
        return []
    if len(model_dets_list) == 1:
        return model_dets_list[0]

    if not HAS_WBF:
        # Fallback: concat all detections, run per-class NMS
        return _fallback_nms_merge(model_dets_list, img_w, img_h)

    boxes_list = []
    scores_list = []
    labels_list = []

    for dets in model_dets_list:
        if not dets:
            boxes_list.append(np.zeros((0, 4), dtype=np.float32))
            scores_list.append(np.zeros(0, dtype=np.float32))
            labels_list.append(np.zeros(0, dtype=np.float32))
            continue

        m_boxes, m_scores, m_labels = [], [], []
        for d in dets:
            x, y, w, h = d["bbox"]
            # Normalize to [0,1] for WBF
            x1 = max(0.0, min(1.0, x / img_w))
            y1 = max(0.0, min(1.0, y / img_h))
            x2 = max(0.0, min(1.0, (x + w) / img_w))
            y2 = max(0.0, min(1.0, (y + h) / img_h))
            m_boxes.append([x1, y1, x2, y2])
            m_scores.append(d["score"])
            m_labels.append(d["category_id"])

        boxes_list.append(np.array(m_boxes, dtype=np.float32))
        scores_list.append(np.array(m_scores, dtype=np.float32))
        labels_list.append(np.array(m_labels, dtype=np.float32))

    fused_boxes, fused_scores, fused_labels = weighted_boxes_fusion(
        boxes_list, scores_list, labels_list,
        weights=model_weights[:len(boxes_list)],
        iou_thr=WBF_IOU_THRESH,
        skip_box_thr=WBF_SKIP_BOX_THRESH,
    )

    # Convert back to COCO [x,y,w,h] pixel coords
    merged = []
    for i in range(len(fused_boxes)):
        bx1, by1, bx2, by2 = fused_boxes[i]
        x = bx1 * img_w
        y = by1 * img_h
        w = (bx2 - bx1) * img_w
        h = (by2 - by1) * img_h
        if w > 0 and h > 0:
            merged.append({
                "category_id": int(fused_labels[i]),
                "bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
                "score": round(float(fused_scores[i]), 5),
            })

    return merged


def _fallback_nms_merge(
    model_dets_list: List[List[Dict[str, Any]]],
    img_w: int,
    img_h: int,
) -> List[Dict[str, Any]]:
    """Fallback: concat all model detections, per-class NMS."""
    all_dets = []
    for dets in model_dets_list:
        all_dets.extend(dets)

    if not all_dets:
        return []

    # Group by class for per-class NMS
    class_groups: Dict[int, List[int]] = {}
    for i, det in enumerate(all_dets):
        cat = det["category_id"]
        if cat not in class_groups:
            class_groups[cat] = []
        class_groups[cat].append(i)

    results = []
    for cat_id, indices in class_groups.items():
        boxes = [all_dets[i]["bbox"] for i in indices]
        scores = [all_dets[i]["score"] for i in indices]

        nms_result = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESH, NMS_IOU_THRESH)
        if len(nms_result) == 0:
            continue
        if isinstance(nms_result, np.ndarray):
            nms_result = nms_result.flatten()

        for nms_idx in nms_result:
            results.append(all_dets[indices[nms_idx]])

    return results


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def extract_image_id(filename: str) -> int:
    """Extract integer image_id from filename like img_00042.jpg -> 42."""
    stem = Path(filename).stem
    digits = "".join(c for c in stem if c.isdigit())
    if digits:
        return int(digits)
    return abs(hash(stem)) % (10**9)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="NM i AI 2026 — 3-model ensemble object detection",
    )
    parser.add_argument("--input", type=str, required=True, help="Input image directory")
    parser.add_argument("--output", type=str, required=True, help="Output JSON path")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)

    # Load category map
    script_dir = Path(__file__).parent
    cat_map_path = script_dir / "category_map.json"
    category_map: Dict[int, int] = {}
    if cat_map_path.exists():
        with open(str(cat_map_path), "r") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            category_map = {i: int(v) for i, v in enumerate(raw)}
        else:
            category_map = {int(k): int(v) for k, v in raw.items()}

    # Load all available models
    models = []
    for model_name, weight in MODEL_CONFIGS:
        loaded = load_model(script_dir / model_name)
        if loaded:
            session, input_name, input_size = loaded
            models.append({
                "session": session,
                "input_name": input_name,
                "input_size": input_size,
                "weight": weight,
                "name": model_name,
            })
        else:
            print("[run] Model %s not found, skipping" % model_name)

    if not models:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_path), "w") as f:
            json.dump([], f)
        print("[run] No models found — wrote empty output")
        return

    print("[run] Loaded %d model(s):" % len(models))
    for m in models:
        print("  %s @ %dpx (weight=%.1f)" % (m["name"], m["input_size"], m["weight"]))

    # Collect images
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    image_paths = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in image_extensions
    )
    n_images = len(image_paths)
    print("[run] %d images to process" % n_images)

    all_detections: List[Dict[str, Any]] = []
    total_start = time.monotonic()

    for img_idx, img_path in enumerate(image_paths):
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            continue

        image_id = extract_image_id(img_path.name)
        orig_h, orig_w = img_bgr.shape[:2]
        elapsed_total = time.monotonic() - total_start
        time_fraction = elapsed_total / TIME_LIMIT

        # Decide which models to run based on time budget
        # >80% time used: only primary model (best_x)
        # >60% time used: skip best_s (tertiary)
        # otherwise: run all models
        if time_fraction > 0.80:
            active_models = models[:1]   # primary only
        elif time_fraction > 0.60:
            active_models = [m for m in models if m["name"] != "best_s.onnx"]
        else:
            active_models = models

        # Run each active model
        model_dets_list = []
        model_weights = []
        for m in active_models:
            dets = run_single_model(
                img_bgr, m["session"], m["input_name"],
                m["input_size"], category_map,
            )
            model_dets_list.append(dets)
            model_weights.append(m["weight"])

        # Merge with WBF (or NMS fallback)
        merged = merge_ensemble_wbf(
            model_dets_list, model_weights, orig_w, orig_h,
        )

        # Tag with image_id
        for det in merged:
            det["image_id"] = image_id
        all_detections.extend(merged)

        # Progress
        img_elapsed = time.monotonic() - (total_start + elapsed_total)
        total_elapsed = time.monotonic() - total_start
        active_names = "+".join(m["name"].replace(".onnx", "") for m in active_models)
        print("[run] %d/%d (%s) %d dets | elapsed %.1fs | %.1fs left [%s]" % (
            img_idx + 1, n_images, img_path.name, len(merged),
            total_elapsed, TIME_LIMIT - total_elapsed, active_names))

        # Emergency stop
        if total_elapsed > TIME_LIMIT:
            print("[run] TIME LIMIT — writing %d detections from %d/%d images" % (
                len(all_detections), img_idx + 1, n_images))
            break

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w") as f:
        json.dump(all_detections, f)

    total_time = time.monotonic() - total_start
    print("[run] Done: %d detections, %.1fs total" % (len(all_detections), total_time))


if __name__ == "__main__":
    main()
