"""
NM i AI 2026 — NorgesGruppen Object Detection with SAHI
Slicing Aided Hyper Inference: tiles the image into overlapping patches,
runs inference on each tile + full image, then merges with WBF (or NMS fallback).

Supports TTA (horizontal flip) and multi-scale tiling.
"""
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

import cv2
import numpy as np
import onnxruntime as ort

# Try to import WBF; fall back to NMS-only merging if unavailable
try:
    from ensemble_boxes import weighted_boxes_fusion
    HAS_WBF = True
except ImportError:
    HAS_WBF = False


# --- Configurable SAHI parameters ---
TILE_SIZE = 640              # Default tile size (auto-detected from ONNX model at runtime)
TILE_SIZES = [640, 1280]     # Multi-scale tile sizes (used when MULTI_SCALE_TILES=True)
MULTI_SCALE_TILES = False    # Enable multi-scale tiling
OVERLAP_RATIO = 0.25
CONF_THRESH = 0.001
NMS_IOU_THRESH = 0.65
MERGE_IOU_THRESH = 0.5       # IoU threshold for cross-tile WBF/NMS
WBF_SKIP_BOX_THRESH = 0.001  # WBF minimum score to keep a box

USE_SOFT_NMS = True           # Use Soft-NMS instead of hard NMS (better recall)
SOFT_NMS_SIGMA = 0.5          # Gaussian decay parameter for Soft-NMS
SOFT_NMS_SCORE_THRESH = 0.001 # Minimum score after decay to keep a box

ENABLE_TTA = True             # Enable test-time augmentation (horizontal flip)
MAX_TILES_PER_IMAGE = 50      # Safety limit to prevent OOM

INPUT_SIZE = 640
PAD_COLOR = (114, 114, 114)


# --- Reused functions from run.py (battle-tested) ---

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


def postprocess(
    output: np.ndarray,
    orig_w: int,
    orig_h: int,
    scale: float,
    pad_left: int,
    pad_top: int,
    category_map: Dict[int, int],
    conf_thresh: float = CONF_THRESH,
    iou_thresh: float = NMS_IOU_THRESH,
) -> List[Dict[str, Any]]:
    """
    Decode YOLOv8 ONNX output -> COCO-format detections.
    Returns detections with bbox in original image coordinates.
    """
    pred = output[0].T

    boxes_cxcywh = pred[:, :4]
    class_scores = pred[:, 4:]

    max_scores = np.max(class_scores, axis=1)
    class_ids = np.argmax(class_scores, axis=1)

    mask = max_scores > conf_thresh
    boxes_cxcywh = boxes_cxcywh[mask]
    max_scores = max_scores[mask]
    class_ids = class_ids[mask]

    if len(boxes_cxcywh) == 0:
        return []

    # cx,cy,w,h -> x1,y1,w,h
    boxes_xywh = np.copy(boxes_cxcywh)
    boxes_xywh[:, 0] = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
    boxes_xywh[:, 1] = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2

    indices = cv2.dnn.NMSBoxes(
        boxes_xywh.tolist(),
        max_scores.tolist(),
        conf_thresh,
        iou_thresh,
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

        # Undo letterbox: remove padding, then undo scale
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
            "bbox": [
                round(x_orig, 2),
                round(y_orig, 2),
                round(w_orig, 2),
                round(h_orig, 2),
            ],
            "score": round(score, 5),
        })

    return detections


def extract_image_id(filename: str) -> int:
    """Extract integer image_id from filename like img_00042.jpg -> 42."""
    stem = Path(filename).stem
    digits = "".join(c for c in stem if c.isdigit())
    if digits:
        return int(digits)
    return abs(hash(stem)) % (10**9)


# --- SAHI-specific functions ---

def generate_tiles(
    img_h: int, img_w: int, tile_size: int, overlap_ratio: float,
    max_tiles: int = MAX_TILES_PER_IMAGE,
) -> List[Tuple[int, int]]:
    """
    Generate tile coordinates (x_start, y_start) covering the full image.
    Tiles overlap by overlap_ratio. Last tiles are shifted to fit within bounds.
    If tile count exceeds max_tiles, increase stride to fit.
    """
    stride = int(tile_size * (1.0 - overlap_ratio))

    # Estimate tile count and increase stride if needed
    est_nx = max(1, (img_w - tile_size) // stride + 1) if img_w > tile_size else 1
    est_ny = max(1, (img_h - tile_size) // stride + 1) if img_h > tile_size else 1
    while est_nx * est_ny > max_tiles and stride < tile_size:
        stride = min(stride + tile_size // 10, tile_size)
        est_nx = max(1, (img_w - tile_size) // stride + 1) if img_w > tile_size else 1
        est_ny = max(1, (img_h - tile_size) // stride + 1) if img_h > tile_size else 1

    tiles = []

    y_starts = list(range(0, img_h - tile_size + 1, stride))
    if not y_starts or y_starts[-1] + tile_size < img_h:
        y_starts.append(max(0, img_h - tile_size))

    x_starts = list(range(0, img_w - tile_size + 1, stride))
    if not x_starts or x_starts[-1] + tile_size < img_w:
        x_starts.append(max(0, img_w - tile_size))

    # Deduplicate
    for y in sorted(set(y_starts)):
        for x in sorted(set(x_starts)):
            tiles.append((x, y))

    return tiles


def run_inference_on_crop(
    crop_bgr: np.ndarray,
    session: ort.InferenceSession,
    input_name: str,
    model_input_size: int,
    category_map: Dict[int, int],
) -> List[Dict[str, Any]]:
    """Run inference on a single crop and return detections in crop coordinates."""
    crop_h, crop_w = crop_bgr.shape[:2]
    blob, scale, pad_left, pad_top = preprocess(crop_bgr, model_input_size)
    outputs = session.run(None, {input_name: blob})
    output = outputs[0]
    return postprocess(
        output, crop_w, crop_h, scale, pad_left, pad_top, category_map,
    )


def run_inference_with_tta(
    crop_bgr: np.ndarray,
    session: ort.InferenceSession,
    input_name: str,
    model_input_size: int,
    category_map: Dict[int, int],
    base_source: int = 0,
) -> List[Dict[str, Any]]:
    """Run inference on a crop, optionally with TTA (horizontal flip).
    Tags each detection with '_source': base_source for normal, 2 for TTA-flipped."""
    dets = run_inference_on_crop(
        crop_bgr, session, input_name, model_input_size, category_map,
    )
    for d in dets:
        d["_source"] = base_source

    if not ENABLE_TTA:
        return dets

    # Horizontal flip augmentation
    crop_h, crop_w = crop_bgr.shape[:2]
    flipped = cv2.flip(crop_bgr, 1)
    flip_dets = run_inference_on_crop(
        flipped, session, input_name, model_input_size, category_map,
    )

    # Mirror x-coordinates back: x_new = crop_w - x - w
    for d in flip_dets:
        d["bbox"][0] = round(crop_w - d["bbox"][0] - d["bbox"][2], 2)
        d["_source"] = 2

    dets.extend(flip_dets)
    return dets


def offset_detections(detections: List[Dict[str, Any]], offset_x: float, offset_y: float):
    """Shift detection bboxes by (offset_x, offset_y)."""
    for det in detections:
        det["bbox"][0] = round(det["bbox"][0] + offset_x, 2)
        det["bbox"][1] = round(det["bbox"][1] + offset_y, 2)


def clip_detections(detections: List[Dict[str, Any]], img_w: int, img_h: int):
    """Clip detection bboxes to image boundaries. Remove invalid ones."""
    valid = []
    for det in detections:
        x, y, w, h = det["bbox"]
        x = max(0.0, x)
        y = max(0.0, y)
        w = min(w, img_w - x)
        h = min(h, img_h - y)
        if w > 0 and h > 0:
            det["bbox"] = [round(x, 2), round(y, 2), round(w, 2), round(h, 2)]
            valid.append(det)
    return valid


def merge_detections_wbf(
    all_dets: List[Dict[str, Any]],
    img_w: int,
    img_h: int,
    iou_thresh: float = MERGE_IOU_THRESH,
    sources: List[int] = None,
) -> List[Dict[str, Any]]:
    """
    Merge detections using Weighted Box Fusion (WBF) with multi-source fusion.
    Detections are grouped by source so WBF can properly average overlapping boxes
    from different sources (full-image=0, tiles=1, TTA-flipped=2).
    Falls back to NMS if ensemble_boxes is not available.
    """
    if not all_dets:
        return []

    if not HAS_WBF:
        return merge_detections_nms(all_dets, iou_thresh)

    if sources is None:
        sources = [0] * len(all_dets)

    # Group detections by source for multi-model WBF
    source_ids = sorted(set(sources))
    source_groups: Dict[int, List[int]] = {s: [] for s in source_ids}
    for i, src in enumerate(sources):
        source_groups[src].append(i)

    # Build per-source arrays for WBF (one "model" per source)
    boxes_list = []
    scores_list = []
    labels_list = []

    for src in source_ids:
        indices = source_groups[src]
        src_boxes = []
        src_scores = []
        src_labels = []
        for i in indices:
            det = all_dets[i]
            x, y, w, h = det["bbox"]
            x1 = max(0.0, min(1.0, x / img_w))
            y1 = max(0.0, min(1.0, y / img_h))
            x2 = max(0.0, min(1.0, (x + w) / img_w))
            y2 = max(0.0, min(1.0, (y + h) / img_h))
            src_boxes.append([x1, y1, x2, y2])
            src_scores.append(det["score"])
            src_labels.append(det["category_id"])

        if src_boxes:
            boxes_list.append(np.array(src_boxes, dtype=np.float32))
            scores_list.append(np.array(src_scores, dtype=np.float32))
            labels_list.append(np.array(src_labels, dtype=np.float32))
        else:
            boxes_list.append(np.zeros((0, 4), dtype=np.float32))
            scores_list.append(np.zeros(0, dtype=np.float32))
            labels_list.append(np.zeros(0, dtype=np.float32))

    fused_boxes, fused_scores, fused_labels = weighted_boxes_fusion(
        boxes_list, scores_list, labels_list,
        iou_thr=iou_thresh,
        skip_box_thr=WBF_SKIP_BOX_THRESH,
    )

    # Convert back to COCO [x, y, w, h] pixel coords
    merged = []
    for i in range(len(fused_boxes)):
        x1, y1, x2, y2 = fused_boxes[i]
        x = x1 * img_w
        y = y1 * img_h
        w = (x2 - x1) * img_w
        h = (y2 - y1) * img_h
        if w > 0 and h > 0:
            merged.append({
                "category_id": int(fused_labels[i]),
                "bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
                "score": round(float(fused_scores[i]), 5),
            })

    return merged


def soft_nms(boxes_xywh, scores, sigma=SOFT_NMS_SIGMA, score_thresh=SOFT_NMS_SCORE_THRESH):
    """
    Soft-NMS: instead of discarding overlapping boxes, decay their scores.
    boxes_xywh: numpy array (N, 4) in [x, y, w, h] format
    scores: numpy array (N,)
    Returns: indices of kept boxes, updated scores
    """
    if len(boxes_xywh) == 0:
        return np.array([], dtype=np.int32), np.array([], dtype=np.float32)

    # Convert xywh to x1y1x2y2
    b = np.array(boxes_xywh, dtype=np.float64)
    x1 = b[:, 0]
    y1 = b[:, 1]
    x2 = b[:, 0] + b[:, 2]
    y2 = b[:, 1] + b[:, 3]
    areas = b[:, 2] * b[:, 3]

    s = np.array(scores, dtype=np.float64)
    n = len(s)
    order = np.arange(n)

    for i in range(n):
        # Find the box with max score among remaining (i..n-1)
        max_pos = i + np.argmax(s[i:])

        # Swap current position with max
        for arr in [x1, y1, x2, y2, s, areas, order]:
            arr[i], arr[max_pos] = arr[max_pos], arr[i]

        # Compute IoU of box i with all subsequent boxes
        xx1 = np.maximum(x1[i], x1[i+1:])
        yy1 = np.maximum(y1[i], y1[i+1:])
        xx2 = np.minimum(x2[i], x2[i+1:])
        yy2 = np.minimum(y2[i], y2[i+1:])

        inter_w = np.maximum(0.0, xx2 - xx1)
        inter_h = np.maximum(0.0, yy2 - yy1)
        inter = inter_w * inter_h

        union = areas[i] + areas[i+1:] - inter
        iou = np.where(union > 0, inter / union, 0.0)

        # Gaussian decay
        s[i+1:] *= np.exp(-(iou ** 2) / sigma)

    # Filter by score threshold
    keep_mask = s >= score_thresh
    keep_indices = order[keep_mask].astype(np.int32)
    keep_scores = s[keep_mask].astype(np.float32)

    return keep_indices, keep_scores


def merge_detections_nms(
    all_dets: List[Dict[str, Any]],
    iou_thresh: float = MERGE_IOU_THRESH,
) -> List[Dict[str, Any]]:
    """
    Class-aware NMS across all merged detections to remove cross-tile duplicates.
    Uses Soft-NMS when USE_SOFT_NMS is True, otherwise hard NMS.
    """
    if not all_dets:
        return []

    # Group by class
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

        if USE_SOFT_NMS:
            kept, updated_scores = soft_nms(
                np.array(boxes, dtype=np.float64),
                np.array(scores, dtype=np.float64),
            )

            for k in range(len(kept)):
                det = all_dets[indices[kept[k]]].copy()
                det["score"] = round(float(updated_scores[k]), 5)
                results.append(det)
        else:
            nms_result = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESH, iou_thresh)

            if len(nms_result) == 0:
                continue

            if isinstance(nms_result, np.ndarray):
                nms_result = nms_result.flatten()

            for nms_idx in nms_result:
                results.append(all_dets[indices[nms_idx]])

    return results


def _run_tiles_for_size(
    img_bgr: np.ndarray,
    tile_size: int,
    session: ort.InferenceSession,
    input_name: str,
    model_input_size: int,
    category_map: Dict[int, int],
) -> List[Dict[str, Any]]:
    """Run tiled inference at a single tile size. Returns detections in image coords."""
    orig_h, orig_w = img_bgr.shape[:2]
    all_dets = []

    if orig_w > tile_size or orig_h > tile_size:
        tiles = generate_tiles(orig_h, orig_w, tile_size, OVERLAP_RATIO)

        for tx, ty in tiles:
            tile_x_end = min(tx + tile_size, orig_w)
            tile_y_end = min(ty + tile_size, orig_h)
            tile = img_bgr[ty:tile_y_end, tx:tile_x_end]

            tile_dets = run_inference_with_tta(
                tile, session, input_name, model_input_size, category_map,
                base_source=1,
            )

            offset_detections(tile_dets, float(tx), float(ty))
            all_dets.extend(tile_dets)

    return all_dets


def sahi_inference(
    img_bgr: np.ndarray,
    session: ort.InferenceSession,
    input_name: str,
    model_input_size: int,
    category_map: Dict[int, int],
) -> List[Dict[str, Any]]:
    """
    SAHI inference on a single image:
    1. Full-image pass (with optional TTA)
    2. Tiled passes at one or more scales (with optional TTA)
    3. Merge all detections with WBF (or NMS fallback)
    """
    orig_h, orig_w = img_bgr.shape[:2]
    all_dets = []

    # 1. Full-image pass (source=0, TTA flips get source=2)
    full_dets = run_inference_with_tta(
        img_bgr, session, input_name, model_input_size, category_map,
        base_source=0,
    )
    all_dets.extend(full_dets)

    # 2. Tiled passes (source=1, TTA flips get source=2)
    if MULTI_SCALE_TILES:
        for ts in TILE_SIZES:
            tile_dets = _run_tiles_for_size(
                img_bgr, ts, session, input_name, model_input_size, category_map,
            )
            all_dets.extend(tile_dets)
    else:
        tile_dets = _run_tiles_for_size(
            img_bgr, TILE_SIZE, session, input_name, model_input_size, category_map,
        )
        all_dets.extend(tile_dets)

    # Clip all detections to image bounds
    all_dets = clip_detections(all_dets, orig_w, orig_h)

    # Extract source tags for multi-source WBF
    sources = [det.pop("_source", 0) for det in all_dets]

    # 3. Merge with WBF (preferred) or NMS (fallback)
    merged = merge_detections_wbf(all_dets, orig_w, orig_h, MERGE_IOU_THRESH, sources=sources)

    return merged


def main():
    parser = argparse.ArgumentParser(description="NM i AI 2026 SAHI inference")
    parser.add_argument("--input", type=str, required=True, help="Input image directory")
    parser.add_argument("--output", type=str, required=True, help="Output JSON path")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)

    # Load model and category map from same directory as this script
    script_dir = Path(__file__).parent
    model_path = script_dir / "best.onnx"

    cat_map_path = script_dir / "category_map.json"
    category_map: Dict[int, int] = {}
    if cat_map_path.exists():
        with open(str(cat_map_path), "r") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            category_map = {i: int(v) for i, v in enumerate(raw)}
        else:
            category_map = {int(k): int(v) for k, v in raw.items()}

    if not model_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_path), "w") as f:
            json.dump([], f)
        return

    try:
        session = ort.InferenceSession(
            str(model_path),
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
    except Exception:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_path), "w") as f:
            json.dump([], f)
        return

    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape
    model_input_size = INPUT_SIZE
    if input_shape and len(input_shape) == 4 and isinstance(input_shape[2], int):
        model_input_size = input_shape[2]

    # Auto-detect TILE_SIZE from model input size
    global TILE_SIZE
    TILE_SIZE = model_input_size

    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    image_paths = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in image_extensions
    )

    all_detections: List[Dict[str, Any]] = []

    for img_path in image_paths:
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            continue

        image_id = extract_image_id(img_path.name)

        dets = sahi_inference(
            img_bgr, session, input_name, model_input_size, category_map,
        )

        for det in dets:
            det["image_id"] = image_id

        all_detections.extend(dets)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w") as f:
        json.dump(all_detections, f)


if __name__ == "__main__":
    main()
