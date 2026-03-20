"""
NM i AI 2026 — NorgesGruppen Object Detection
Ensemble inference: combines predictions from multiple ONNX models using
Weighted Box Fusion (WBF). Falls back to single-model NMS if ensemble_boxes
is not available.
"""
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
import time

import cv2
import numpy as np
import onnxruntime as ort

try:
    from ensemble_boxes import weighted_boxes_fusion
    HAS_WBF = True
except Exception:
    HAS_WBF = False

CONF_THRESH = 0.01
NMS_IOU_THRESH = 0.5
WBF_IOU_THRESH = 0.55
WBF_SKIP_BOX_THRESH = 0.01
PAD_COLOR = (114, 114, 114)
TIME_LIMIT_SECONDS = 300
TIME_RESERVE_SECONDS = 15


def letterbox(img: np.ndarray, target_size: int) -> tuple:
    """Resize image with letterbox padding, return padded image and scale info."""
    h, w = img.shape[:2]
    scale = min(target_size / h, target_size / w)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))

    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    pad_w = target_size - new_w
    pad_h = target_size - new_h
    top = pad_h // 2
    bottom = pad_h - top
    left = pad_w // 2
    right = pad_w - left

    padded = cv2.copyMakeBorder(
        resized, top, bottom, left, right,
        cv2.BORDER_CONSTANT, value=PAD_COLOR,
    )
    return padded, scale, left, top


def preprocess(img_bgr: np.ndarray, target_size: int) -> tuple:
    """BGR image -> ONNX input tensor (1, 3, H, W) float32 [0,1]."""
    padded, scale, pad_left, pad_top = letterbox(img_bgr, target_size)
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    blob = rgb.astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))  # HWC -> CHW
    blob = np.expand_dims(blob, axis=0)    # add batch dim
    return blob, scale, pad_left, pad_top


def decode_raw(
    output: np.ndarray,
    scale: float,
    pad_left: int,
    pad_top: int,
    orig_w: int,
    orig_h: int,
    category_map: Dict[int, int],
    conf_thresh: float = CONF_THRESH,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Decode YOLOv8 ONNX output into arrays.
    Returns (boxes_xyxy_normalized, scores, class_ids).
    boxes are in [x1, y1, x2, y2] format, normalized to [0,1] for WBF.
    """
    pred = output[0].T  # (8400, 4+num_classes)
    boxes_cxcywh = pred[:, :4]
    class_scores = pred[:, 4:]

    max_scores = np.max(class_scores, axis=1)
    class_ids = np.argmax(class_scores, axis=1)

    mask = max_scores > conf_thresh
    boxes_cxcywh = boxes_cxcywh[mask]
    max_scores = max_scores[mask]
    class_ids = class_ids[mask]

    if len(boxes_cxcywh) == 0:
        return np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.int32)

    # cx,cy,w,h -> x1,y1,x2,y2 in letterboxed coords
    x1 = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
    y1 = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
    x2 = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
    y2 = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2

    # Undo letterbox: remove padding, then undo scale -> original image coords
    x1 = (x1 - pad_left) / scale
    y1 = (y1 - pad_top) / scale
    x2 = (x2 - pad_left) / scale
    y2 = (y2 - pad_top) / scale

    # Clip to image boundaries
    x1 = np.clip(x1, 0, orig_w)
    y1 = np.clip(y1, 0, orig_h)
    x2 = np.clip(x2, 0, orig_w)
    y2 = np.clip(y2, 0, orig_h)

    # Filter out zero-area boxes
    valid = (x2 > x1) & (y2 > y1)
    x1, y1, x2, y2 = x1[valid], y1[valid], x2[valid], y2[valid]
    max_scores = max_scores[valid]
    class_ids = class_ids[valid]

    # Normalize to [0, 1] for WBF
    boxes_norm = np.stack([
        x1 / orig_w,
        y1 / orig_h,
        x2 / orig_w,
        y2 / orig_h,
    ], axis=1).astype(np.float32)

    # Map YOLO index -> COCO category_id
    mapped_ids = np.array([category_map.get(int(c), int(c)) for c in class_ids], dtype=np.int32)

    return boxes_norm, max_scores.astype(np.float32), mapped_ids


def nms_single_model(
    boxes_norm: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    orig_w: int,
    orig_h: int,
    iou_thresh: float = NMS_IOU_THRESH,
) -> List[Dict[str, Any]]:
    """NMS fallback for single model. boxes_norm in [x1,y1,x2,y2] normalized."""
    if len(boxes_norm) == 0:
        return []

    # Convert to xywh in original coords for cv2.dnn.NMSBoxes
    boxes_xywh = np.zeros_like(boxes_norm)
    boxes_xywh[:, 0] = boxes_norm[:, 0] * orig_w
    boxes_xywh[:, 1] = boxes_norm[:, 1] * orig_h
    boxes_xywh[:, 2] = (boxes_norm[:, 2] - boxes_norm[:, 0]) * orig_w
    boxes_xywh[:, 3] = (boxes_norm[:, 3] - boxes_norm[:, 1]) * orig_h

    indices = cv2.dnn.NMSBoxes(
        boxes_xywh.tolist(),
        scores.tolist(),
        CONF_THRESH,
        iou_thresh,
    )

    if len(indices) == 0:
        return []
    if isinstance(indices, np.ndarray):
        indices = indices.flatten()

    detections = []
    for idx in indices:
        x, y, w, h = boxes_xywh[idx]
        detections.append({
            "category_id": int(class_ids[idx]),
            "bbox": [round(float(x), 2), round(float(y), 2),
                     round(float(w), 2), round(float(h), 2)],
            "score": round(float(scores[idx]), 5),
        })
    return detections


def wbf_to_coco(
    boxes_list: List[np.ndarray],
    scores_list: List[np.ndarray],
    labels_list: List[np.ndarray],
    orig_w: int,
    orig_h: int,
    weights: List[float],
) -> List[Dict[str, Any]]:
    """Run WBF and convert to COCO-format detections."""
    # WBF needs list-of-lists format
    boxes_l = [b.tolist() if len(b) > 0 else [] for b in boxes_list]
    scores_l = [s.tolist() if len(s) > 0 else [] for s in scores_list]
    labels_l = [l.tolist() if len(l) > 0 else [] for l in labels_list]

    fused_boxes, fused_scores, fused_labels = weighted_boxes_fusion(
        boxes_l, scores_l, labels_l,
        weights=weights,
        iou_thr=WBF_IOU_THRESH,
        skip_box_thr=WBF_SKIP_BOX_THRESH,
    )

    detections = []
    for i in range(len(fused_scores)):
        x1, y1, x2, y2 = fused_boxes[i]
        # Convert normalized xyxy -> original coords xywh (COCO format)
        x = x1 * orig_w
        y = y1 * orig_h
        w = (x2 - x1) * orig_w
        h = (y2 - y1) * orig_h
        detections.append({
            "category_id": int(fused_labels[i]),
            "bbox": [round(float(x), 2), round(float(y), 2),
                     round(float(w), 2), round(float(h), 2)],
            "score": round(float(fused_scores[i]), 5),
        })
    return detections


def extract_image_id(filename: str) -> int:
    """Extract integer image_id from filename like img_00042.jpg -> 42."""
    stem = Path(filename).stem
    digits = "".join(c for c in stem if c.isdigit())
    if digits:
        return int(digits)
    return abs(hash(stem)) % (10**9)


def discover_models(script_dir: Path) -> List[Path]:
    """Find all .onnx files in the script directory."""
    models = sorted(script_dir.glob("*.onnx"))
    return models


def load_model(model_path: Path) -> Tuple[ort.InferenceSession, str, int]:
    """Load an ONNX model, return (session, input_name, input_size)."""
    session = ort.InferenceSession(
        str(model_path),
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape
    # Detect input size from model metadata
    input_size = 640  # default
    if input_shape and len(input_shape) == 4 and isinstance(input_shape[2], int):
        input_size = input_shape[2]
    return session, input_name, input_size


def main():
    parser = argparse.ArgumentParser(description="NM i AI 2026 ensemble inference")
    parser.add_argument("--input", type=str, required=True, help="Input image directory")
    parser.add_argument("--output", type=str, required=True, help="Output JSON path")
    args = parser.parse_args()

    start_time = time.monotonic()

    input_dir = Path(args.input)
    output_path = Path(args.output)
    script_dir = Path(__file__).parent

    # Load category mapping
    cat_map_path = script_dir / "category_map.json"
    category_map: Dict[int, int] = {}
    if cat_map_path.exists():
        with open(str(cat_map_path), "r") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            category_map = {i: int(v) for i, v in enumerate(raw)}
        else:
            category_map = {int(k): int(v) for k, v in raw.items()}

    # Discover and load models
    model_paths = discover_models(script_dir)
    if not model_paths:
        print("[ensemble] No .onnx models found, writing empty output")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_path), "w") as f:
            json.dump([], f)
        return

    models = []
    for mp in model_paths:
        try:
            session, input_name, input_size = load_model(mp)
            models.append((mp.name, session, input_name, input_size))
            print(f"[ensemble] Loaded {mp.name} (input_size={input_size})")
        except Exception as e:
            print(f"[ensemble] Failed to load {mp.name}: {e}")

    if not models:
        print("[ensemble] All models failed to load, writing empty output")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_path), "w") as f:
            json.dump([], f)
        return

    num_models = len(models)
    use_wbf = HAS_WBF and num_models > 1
    print(f"[ensemble] {num_models} model(s), WBF={'enabled' if use_wbf else 'disabled (fallback NMS)'}")

    # Equal weights for all models
    weights = [1.0] * num_models

    # Collect image paths
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    image_paths = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in image_extensions
    )

    all_detections: List[Dict[str, Any]] = []
    img_times: List[float] = []

    for i, img_path in enumerate(image_paths):
        img_start = time.monotonic()

        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            continue

        orig_h, orig_w = img_bgr.shape[:2]
        image_id = extract_image_id(img_path.name)

        # Run inference on all models
        boxes_list = []
        scores_list = []
        labels_list = []

        for model_name, session, input_name, input_size in models:
            blob, scale, pad_left, pad_top = preprocess(img_bgr, input_size)
            outputs = session.run(None, {input_name: blob})
            output = outputs[0]

            boxes_norm, scores, class_ids = decode_raw(
                output, scale, pad_left, pad_top, orig_w, orig_h, category_map,
            )

            boxes_list.append(boxes_norm)
            scores_list.append(scores)
            labels_list.append(class_ids)

        # Combine predictions
        if use_wbf:
            dets = wbf_to_coco(
                boxes_list, scores_list, labels_list,
                orig_w, orig_h, weights,
            )
        else:
            # Single model or no WBF: use NMS on first (or only) model
            merged_boxes = np.concatenate(boxes_list, axis=0) if boxes_list else np.zeros((0, 4))
            merged_scores = np.concatenate(scores_list, axis=0) if scores_list else np.zeros(0)
            merged_labels = np.concatenate(labels_list, axis=0) if labels_list else np.zeros(0, dtype=np.int32)
            dets = nms_single_model(
                merged_boxes, merged_scores, merged_labels,
                orig_w, orig_h,
            )

        for det in dets:
            det["image_id"] = image_id
        all_detections.extend(dets)

        img_elapsed = time.monotonic() - img_start
        img_times.append(img_elapsed)

        # Timing info
        total_elapsed = time.monotonic() - start_time
        remaining = TIME_LIMIT_SECONDS - total_elapsed
        images_left = len(image_paths) - (i + 1)
        avg_time = sum(img_times) / len(img_times)
        est_remaining = avg_time * images_left

        print(
            f"[ensemble] img {i+1}/{len(image_paths)} "
            f"({img_path.name}) {img_elapsed:.2f}s | "
            f"elapsed {total_elapsed:.1f}s | "
            f"est remaining {est_remaining:.1f}s / {remaining:.1f}s left"
        )

        # Safety: if we're going to exceed the time limit, warn
        if images_left > 0 and est_remaining > (remaining - TIME_RESERVE_SECONDS):
            print(f"[ensemble] WARNING: may exceed time limit! {est_remaining:.1f}s needed, {remaining:.1f}s left")

    total_time = time.monotonic() - start_time
    print(f"[ensemble] Done: {len(all_detections)} detections in {total_time:.1f}s")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w") as f:
        json.dump(all_detections, f)


if __name__ == "__main__":
    main()
