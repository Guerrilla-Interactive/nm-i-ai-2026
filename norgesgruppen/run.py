"""
NM i AI 2026 — NorgesGruppen Object Detection
Competition sandbox inference script using ONNX Runtime.

Optimizations over baseline:
- Per-class NMS (avoids suppressing valid overlapping detections of different classes)
- Higher NMS IoU threshold (0.65) for densely packed shelves
- Horizontal flip TTA (2x inference, merges flipped + original detections)
- Multi-scale inference (640 + dynamic larger scale if model supports it)
- Tiling fallback for fixed-input models to improve small object detection

NOTE: This is the canonical copy. submission/run.py should be identical.
      train.py --prepare-submission copies this file into submission/.
"""
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

import cv2
import numpy as np
import onnxruntime as ort


CONF_THRESH = 0.01
NMS_IOU_THRESH = 0.65  # was 0.5 — higher keeps more overlapping detections on packed shelves
MAX_DET = 600  # was 300 — allow more detections with TTA/multi-scale
INPUT_SIZE = 640
PAD_COLOR = (114, 114, 114)
# Multi-scale: extra scales to try (only used if model supports dynamic input)
EXTRA_SCALES = [1280]
# Tiling: used if model has fixed input and image is large enough
TILE_OVERLAP = 0.2  # 20% overlap between tiles
MIN_TILE_RATIO = 1.5  # only tile if image is at least 1.5x the model input size
# TTA
ENABLE_FLIP_TTA = True


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
    """BGR image → ONNX input tensor (1, 3, H, W) float32 [0,1]."""
    padded, scale, pad_left, pad_top = letterbox(img_bgr, target_size)
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    blob = rgb.astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))  # HWC → CHW
    blob = np.expand_dims(blob, axis=0)    # add batch dim
    return blob, scale, pad_left, pad_top


def decode_raw_output(
    output: np.ndarray,
    scale: float,
    pad_left: int,
    pad_top: int,
    conf_thresh: float = CONF_THRESH,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Decode YOLOv8 raw output to boxes in original image coords, scores, class_ids.
    Returns (boxes_xywh_orig, max_scores, class_ids) — all filtered by conf_thresh.
    boxes_xywh_orig are in original image pixel coordinates (x, y, w, h top-left).
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
        return np.zeros((0, 4)), np.zeros(0), np.zeros(0, dtype=np.int32)

    # cx,cy,w,h → x1,y1,w,h (top-left) in model input coords
    boxes_xywh = np.copy(boxes_cxcywh)
    boxes_xywh[:, 0] = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
    boxes_xywh[:, 1] = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2

    # Undo letterbox: remove padding, then undo scale → original image coords
    boxes_xywh[:, 0] = (boxes_xywh[:, 0] - pad_left) / scale
    boxes_xywh[:, 1] = (boxes_xywh[:, 1] - pad_top) / scale
    boxes_xywh[:, 2] = boxes_xywh[:, 2] / scale
    boxes_xywh[:, 3] = boxes_xywh[:, 3] / scale

    return boxes_xywh, max_scores, class_ids


def nms_per_class(
    boxes_xywh: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    orig_w: int,
    orig_h: int,
    category_map: Dict[int, int],
    iou_thresh: float = NMS_IOU_THRESH,
    max_det: int = MAX_DET,
) -> List[Dict[str, Any]]:
    """Run NMS independently per class to avoid cross-class suppression."""
    if len(boxes_xywh) == 0:
        return []

    all_dets = []
    unique_classes = np.unique(class_ids)

    for cls_id in unique_classes:
        cls_mask = class_ids == cls_id
        cls_boxes = boxes_xywh[cls_mask]
        cls_scores = scores[cls_mask]

        indices = cv2.dnn.NMSBoxes(
            cls_boxes.tolist(),
            cls_scores.tolist(),
            CONF_THRESH,
            iou_thresh,
        )
        if len(indices) == 0:
            continue
        if isinstance(indices, np.ndarray):
            indices = indices.flatten()

        for idx in indices:
            x, y, w, h = cls_boxes[idx]
            x, y, w, h = float(x), float(y), float(w), float(h)

            # Clip to image boundaries
            x = max(0.0, x)
            y = max(0.0, y)
            w = min(w, orig_w - x)
            h = min(h, orig_h - y)

            if w <= 0 or h <= 0:
                continue

            coco_cat_id = category_map.get(int(cls_id), int(cls_id))
            all_dets.append({
                "category_id": int(coco_cat_id),
                "bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
                "score": round(float(cls_scores[idx]), 5),
            })

    # Limit to top max_det by confidence
    if len(all_dets) > max_det:
        all_dets.sort(key=lambda d: d["score"], reverse=True)
        all_dets = all_dets[:max_det]

    return all_dets


def run_inference(
    session: ort.InferenceSession,
    input_name: str,
    img_bgr: np.ndarray,
    target_size: int,
) -> Tuple[np.ndarray, float, int, int]:
    """Run single inference pass, return (raw_output, scale, pad_left, pad_top)."""
    blob, scale, pad_left, pad_top = preprocess(img_bgr, target_size)
    outputs = session.run(None, {input_name: blob})
    return outputs[0], scale, pad_left, pad_top


def flip_boxes_horizontal(boxes_xywh: np.ndarray, img_w: int) -> np.ndarray:
    """Flip x-coordinates of boxes (x,y,w,h top-left format) horizontally."""
    flipped = boxes_xywh.copy()
    # new x = img_w - (x + w)
    flipped[:, 0] = img_w - (boxes_xywh[:, 0] + boxes_xywh[:, 2])
    return flipped


def get_tile_coords(
    img_h: int, img_w: int, tile_size: int, overlap: float
) -> List[Tuple[int, int, int, int]]:
    """Generate overlapping tile coordinates (x, y, w, h) covering the image."""
    stride = int(tile_size * (1.0 - overlap))
    tiles = []
    for y in range(0, img_h, stride):
        for x in range(0, img_w, stride):
            tx = min(x, max(0, img_w - tile_size))
            ty = min(y, max(0, img_h - tile_size))
            tw = min(tile_size, img_w - tx)
            th = min(tile_size, img_h - ty)
            tile = (tx, ty, tw, th)
            if tile not in tiles:
                tiles.append(tile)
    return tiles


def infer_image(
    session: ort.InferenceSession,
    input_name: str,
    img_bgr: np.ndarray,
    model_input_size: int,
    supports_dynamic: bool,
    category_map: Dict[int, int],
) -> List[Dict[str, Any]]:
    """Run full inference pipeline on one image with TTA and multi-scale/tiling."""
    orig_h, orig_w = img_bgr.shape[:2]

    all_boxes = []
    all_scores = []
    all_class_ids = []

    # --- Pass 1: Standard inference at model input size ---
    output, scale, pl, pt = run_inference(session, input_name, img_bgr, model_input_size)
    boxes, scores, cids = decode_raw_output(output, scale, pl, pt)
    all_boxes.append(boxes)
    all_scores.append(scores)
    all_class_ids.append(cids)

    # --- Pass 2: Horizontal flip TTA ---
    if ENABLE_FLIP_TTA:
        flipped = cv2.flip(img_bgr, 1)  # horizontal flip
        output_f, scale_f, pl_f, pt_f = run_inference(
            session, input_name, flipped, model_input_size
        )
        boxes_f, scores_f, cids_f = decode_raw_output(output_f, scale_f, pl_f, pt_f)
        if len(boxes_f) > 0:
            boxes_f = flip_boxes_horizontal(boxes_f, orig_w)
            all_boxes.append(boxes_f)
            all_scores.append(scores_f)
            all_class_ids.append(cids_f)

    # --- Pass 3: Multi-scale (if model supports dynamic input) ---
    if supports_dynamic:
        for extra_size in EXTRA_SCALES:
            if extra_size == model_input_size:
                continue
            output_ms, scale_ms, pl_ms, pt_ms = run_inference(
                session, input_name, img_bgr, extra_size
            )
            boxes_ms, scores_ms, cids_ms = decode_raw_output(
                output_ms, scale_ms, pl_ms, pt_ms
            )
            all_boxes.append(boxes_ms)
            all_scores.append(scores_ms)
            all_class_ids.append(cids_ms)

            # Flip TTA at extra scale too
            if ENABLE_FLIP_TTA:
                flipped = cv2.flip(img_bgr, 1)
                out_mf, sc_mf, pl_mf, pt_mf = run_inference(
                    session, input_name, flipped, extra_size
                )
                bx_mf, sc_mf2, ci_mf = decode_raw_output(out_mf, sc_mf, pl_mf, pt_mf)
                if len(bx_mf) > 0:
                    bx_mf = flip_boxes_horizontal(bx_mf, orig_w)
                    all_boxes.append(bx_mf)
                    all_scores.append(sc_mf2)
                    all_class_ids.append(ci_mf)
    else:
        # --- Pass 3 alt: Tiling for fixed-input models on large images ---
        max_dim = max(orig_h, orig_w)
        # Tile size in original image pixels that maps to model_input_size
        # We want tiles that, when letterboxed to model_input_size, give ~1:1 pixel mapping
        tile_native = model_input_size  # tile at native model resolution in orig coords
        # Only tile if image is significantly larger than model input
        if max_dim > model_input_size * MIN_TILE_RATIO:
            # Use tiles of size proportional to model input, at original resolution
            # This means each tile gets full model_input_size resolution for a smaller region
            tile_pixel_size = int(max_dim / 2)  # 2x2 grid roughly
            tiles = get_tile_coords(orig_h, orig_w, tile_pixel_size, TILE_OVERLAP)
            for tx, ty, tw, th in tiles:
                if tw < 32 or th < 32:
                    continue
                tile_img = img_bgr[ty:ty + th, tx:tx + tw]
                output_t, scale_t, pl_t, pt_t = run_inference(
                    session, input_name, tile_img, model_input_size
                )
                boxes_t, scores_t, cids_t = decode_raw_output(
                    output_t, scale_t, pl_t, pt_t
                )
                if len(boxes_t) > 0:
                    # Offset tile boxes to full image coordinates
                    boxes_t[:, 0] += tx
                    boxes_t[:, 1] += ty
                    all_boxes.append(boxes_t)
                    all_scores.append(scores_t)
                    all_class_ids.append(cids_t)

    # Merge all detections
    if not all_boxes:
        return []

    merged_boxes = np.concatenate(all_boxes, axis=0)
    merged_scores = np.concatenate(all_scores, axis=0)
    merged_cids = np.concatenate(all_class_ids, axis=0)

    if len(merged_boxes) == 0:
        return []

    # Per-class NMS on merged detections
    return nms_per_class(
        merged_boxes, merged_scores, merged_cids,
        orig_w, orig_h, category_map,
    )


def extract_image_id(filename: str) -> int:
    """Extract integer image_id from filename like img_00042.jpg → 42."""
    stem = Path(filename).stem
    digits = "".join(c for c in stem if c.isdigit())
    if digits:
        return int(digits)
    # Fallback: hash the filename
    return abs(hash(stem)) % (10**9)


def main():
    parser = argparse.ArgumentParser(description="NM i AI 2026 inference")
    parser.add_argument("--input", type=str, required=True, help="Input image directory")
    parser.add_argument("--output", type=str, required=True, help="Output JSON path")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)

    # Load model from same directory as this script
    script_dir = Path(__file__).parent
    model_path = script_dir / "best.onnx"

    # Load category mapping (YOLO class index → COCO category_id)
    cat_map_path = script_dir / "category_map.json"
    category_map: Dict[int, int] = {}
    if cat_map_path.exists():
        with open(str(cat_map_path), "r") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            category_map = {i: int(v) for i, v in enumerate(raw)}
        else:
            category_map = {int(k): int(v) for k, v in raw.items()}

    # Graceful handling: if model is missing, output empty predictions
    if not model_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_path), "w") as f:
            json.dump([], f)
        return

    # Create ONNX session
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
    # Determine model input size from ONNX metadata if available
    model_input_size = INPUT_SIZE
    if input_shape and len(input_shape) == 4 and isinstance(input_shape[2], int):
        model_input_size = input_shape[2]

    # Check if model supports dynamic input (non-fixed dimensions)
    supports_dynamic = False
    if input_shape and len(input_shape) == 4:
        # Dynamic if height/width are strings or None (not fixed ints)
        h_dim = input_shape[2]
        w_dim = input_shape[3]
        supports_dynamic = not (isinstance(h_dim, int) and isinstance(w_dim, int))

    # Collect image paths
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

        dets = infer_image(
            session, input_name, img_bgr, model_input_size,
            supports_dynamic, category_map,
        )

        for det in dets:
            det["image_id"] = image_id

        all_detections.extend(dets)

    # Write output (output directory is pre-created by the sandbox)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w") as f:
        json.dump(all_detections, f)


if __name__ == "__main__":
    main()
