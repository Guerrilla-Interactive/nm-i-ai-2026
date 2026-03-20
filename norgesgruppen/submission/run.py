"""
NM i AI 2026 — NorgesGruppen Object Detection
Multi-scale ensemble inference with manual Weighted Box Fusion (WBF).
Runs each ONNX model at 640px (full image) and 1280px (4 tiles) for
higher recall on small objects, then fuses all detections with WBF.
"""
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
import time

import cv2
import numpy as np
import onnxruntime as ort

# --- Configuration ---
CONF_THRESH = 0.005        # Very low: false positives are free, missed detections are costly
NMS_IOU_THRESH = 0.7       # Generous per-pass NMS (keep more candidates for WBF)
WBF_IOU_THRESH = 0.55      # WBF clustering threshold
WBF_SKIP_BOX_THRESH = 0.001
MAX_DETS_PER_CLASS = 50    # Per pass, before WBF
PAD_COLOR = (114, 114, 114)
TIME_LIMIT_SECONDS = 300
TIME_RESERVE_SECONDS = 15
INPUT_SIZE = 640           # Fixed model input size
TILE_SIZE = 1280           # Virtual high-res size for tiling

# Weight scheme: (model_name, scale_label) -> weight
# best.onnx = YOLOv8m (larger/better), best_s.onnx = YOLOv8s (smaller/faster)
MODEL_WEIGHTS = {
    ("best.onnx", "1280"): 1.0,
    ("best.onnx", "640"): 0.7,
    ("best_s.onnx", "1280"): 0.7,
    ("best_s.onnx", "640"): 0.5,
}
DEFAULT_WEIGHT = 0.6


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
    left = pad_w // 2
    padded = cv2.copyMakeBorder(
        resized, top, pad_h - top, left, pad_w - left,
        cv2.BORDER_CONSTANT, value=PAD_COLOR,
    )
    return padded, scale, left, top


def preprocess(img_bgr: np.ndarray, target_size: int) -> tuple:
    """BGR image -> ONNX input tensor (1, 3, H, W) float32 [0,1]."""
    padded, scale, pad_left, pad_top = letterbox(img_bgr, target_size)
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    blob = rgb.astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))
    blob = np.expand_dims(blob, axis=0)
    return blob, scale, pad_left, pad_top


def decode_yolo_output(
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
    Returns (boxes_xyxy in original image coords, scores, class_ids).
    """
    pred = output[0].T  # (8400, 4+num_classes)
    boxes_cxcywh = pred[:, :4]
    class_scores = pred[:, 4:]

    max_scores = np.max(class_scores, axis=1)
    mask = max_scores > conf_thresh
    boxes_cxcywh = boxes_cxcywh[mask]
    max_scores = max_scores[mask]
    class_ids = np.argmax(class_scores[mask], axis=1)

    if len(boxes_cxcywh) == 0:
        return np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.int32)

    # cx,cy,w,h -> x1,y1,x2,y2 in letterboxed coords
    x1 = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
    y1 = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
    x2 = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
    y2 = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2

    # Undo letterbox -> original image coords
    x1 = (x1 - pad_left) / scale
    y1 = (y1 - pad_top) / scale
    x2 = (x2 - pad_left) / scale
    y2 = (y2 - pad_top) / scale

    # Clip to image boundaries
    x1 = np.clip(x1, 0, orig_w)
    y1 = np.clip(y1, 0, orig_h)
    x2 = np.clip(x2, 0, orig_w)
    y2 = np.clip(y2, 0, orig_h)

    # Filter zero-area
    valid = (x2 > x1 + 1) & (y2 > y1 + 1)
    x1, y1, x2, y2 = x1[valid], y1[valid], x2[valid], y2[valid]
    max_scores = max_scores[valid]
    class_ids = class_ids[valid]

    boxes = np.stack([x1, y1, x2, y2], axis=1).astype(np.float32)
    mapped_ids = np.array([category_map.get(int(c), int(c)) for c in class_ids], dtype=np.int32)

    return boxes, max_scores.astype(np.float32), mapped_ids


def nms_per_class(
    boxes: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    iou_thresh: float = NMS_IOU_THRESH,
    max_per_class: int = MAX_DETS_PER_CLASS,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-class NMS. boxes in xyxy original coords. Returns filtered arrays."""
    if len(boxes) == 0:
        return boxes, scores, class_ids

    keep_boxes, keep_scores, keep_ids = [], [], []

    for cls_id in np.unique(class_ids):
        mask = class_ids == cls_id
        cls_boxes = boxes[mask]
        cls_scores = scores[mask]

        # Convert xyxy -> xywh for cv2.dnn.NMSBoxes
        xywh = np.zeros_like(cls_boxes)
        xywh[:, 0] = cls_boxes[:, 0]
        xywh[:, 1] = cls_boxes[:, 1]
        xywh[:, 2] = cls_boxes[:, 2] - cls_boxes[:, 0]
        xywh[:, 3] = cls_boxes[:, 3] - cls_boxes[:, 1]

        indices = cv2.dnn.NMSBoxes(
            xywh.tolist(), cls_scores.tolist(), CONF_THRESH, iou_thresh,
        )
        if len(indices) == 0:
            continue
        if isinstance(indices, np.ndarray):
            indices = indices.flatten()

        if len(indices) > max_per_class:
            top_k = np.argsort(cls_scores[indices])[::-1][:max_per_class]
            indices = indices[top_k]

        keep_boxes.append(cls_boxes[indices])
        keep_scores.append(cls_scores[indices])
        keep_ids.append(np.full(len(indices), cls_id, dtype=np.int32))

    if not keep_boxes:
        return np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.int32)

    return np.concatenate(keep_boxes), np.concatenate(keep_scores), np.concatenate(keep_ids)


def run_inference_fullimage(
    session: ort.InferenceSession,
    input_name: str,
    img_bgr: np.ndarray,
    orig_w: int,
    orig_h: int,
    category_map: Dict[int, int],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run single 640px full-image inference. Returns (boxes_xyxy, scores, class_ids)."""
    blob, scale, pad_left, pad_top = preprocess(img_bgr, INPUT_SIZE)
    outputs = session.run(None, {input_name: blob})
    boxes, scores, class_ids = decode_yolo_output(
        outputs[0], scale, pad_left, pad_top, orig_w, orig_h, category_map,
    )
    return nms_per_class(boxes, scores, class_ids)


def run_inference_tiled(
    session: ort.InferenceSession,
    input_name: str,
    img_bgr: np.ndarray,
    orig_w: int,
    orig_h: int,
    category_map: Dict[int, int],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Run tiled inference at 2x resolution (1280px virtual).
    Letterbox to 1280x1280, split into 4 non-overlapping 640x640 tiles,
    run each tile, map detections back to original image coordinates.
    """
    padded_1280, scale_1280, pad_left_1280, pad_top_1280 = letterbox(img_bgr, TILE_SIZE)

    # 4 tiles: 640*2 = 1280, no overlap
    tile_positions = [(0, 0), (INPUT_SIZE, 0), (0, INPUT_SIZE), (INPUT_SIZE, INPUT_SIZE)]

    all_boxes, all_scores, all_ids = [], [], []

    for tx, ty in tile_positions:
        tile = padded_1280[ty:ty + INPUT_SIZE, tx:tx + INPUT_SIZE]

        # Tile is already 640x640, just normalize
        rgb = cv2.cvtColor(tile, cv2.COLOR_BGR2RGB)
        blob = rgb.astype(np.float32) / 255.0
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)

        outputs = session.run(None, {input_name: blob})
        pred = outputs[0]

        # Decode: detections are in tile pixel coords [0, INPUT_SIZE]
        raw = pred[0].T
        boxes_cxcywh = raw[:, :4]
        class_scores = raw[:, 4:]

        max_scores = np.max(class_scores, axis=1)
        mask = max_scores > CONF_THRESH
        if not np.any(mask):
            continue

        boxes_cxcywh = boxes_cxcywh[mask]
        max_scores = max_scores[mask]
        class_ids = np.argmax(class_scores[mask], axis=1)

        # cx,cy,w,h -> x1,y1,x2,y2 in tile coords
        x1 = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2
        y1 = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2
        x2 = boxes_cxcywh[:, 0] + boxes_cxcywh[:, 2] / 2
        y2 = boxes_cxcywh[:, 1] + boxes_cxcywh[:, 3] / 2

        # Tile coords -> 1280 letterbox coords
        x1 += tx
        y1 += ty
        x2 += tx
        y2 += ty

        # 1280 letterbox coords -> original image coords
        x1 = (x1 - pad_left_1280) / scale_1280
        y1 = (y1 - pad_top_1280) / scale_1280
        x2 = (x2 - pad_left_1280) / scale_1280
        y2 = (y2 - pad_top_1280) / scale_1280

        # Clip
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        valid = (x2 > x1 + 1) & (y2 > y1 + 1)
        if not np.any(valid):
            continue

        boxes = np.stack([x1[valid], y1[valid], x2[valid], y2[valid]], axis=1).astype(np.float32)
        mapped_ids = np.array([category_map.get(int(c), int(c)) for c in class_ids[valid]], dtype=np.int32)

        all_boxes.append(boxes)
        all_scores.append(max_scores[valid].astype(np.float32))
        all_ids.append(mapped_ids)

    if not all_boxes:
        return np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.int32)

    merged_boxes = np.concatenate(all_boxes)
    merged_scores = np.concatenate(all_scores)
    merged_ids = np.concatenate(all_ids)

    # NMS within this tiled pass to reduce candidates
    return nms_per_class(merged_boxes, merged_scores, merged_ids)


def weighted_box_fusion(
    boxes_list: List[np.ndarray],
    scores_list: List[np.ndarray],
    labels_list: List[np.ndarray],
    weights: List[float],
    iou_thr: float = WBF_IOU_THRESH,
    skip_box_thr: float = WBF_SKIP_BOX_THRESH,
    num_models: int = 4,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Manual Weighted Box Fusion.
    For each class:
      1. Pool all boxes sorted by weighted score descending
      2. Greedily cluster: each box joins highest-scoring cluster it overlaps (IoU > thr)
      3. Fused box = weighted average of coords, fused score rewards agreement
    """
    all_boxes = []
    all_scores = []
    all_labels = []
    all_pass_weights = []

    for i, (boxes, scores, labels) in enumerate(zip(boxes_list, scores_list, labels_list)):
        if len(boxes) == 0:
            continue
        all_boxes.append(boxes)
        all_scores.append(scores)
        all_labels.append(labels)
        all_pass_weights.append(np.full(len(boxes), weights[i], dtype=np.float32))

    if not all_boxes:
        return np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.int32)

    all_boxes = np.concatenate(all_boxes)
    all_scores = np.concatenate(all_scores)
    all_labels = np.concatenate(all_labels)
    all_pass_weights = np.concatenate(all_pass_weights)

    fused_boxes = []
    fused_scores = []
    fused_labels = []
    weight_sum = sum(weights)

    for cls_id in np.unique(all_labels):
        mask = all_labels == cls_id
        cls_boxes = all_boxes[mask]
        cls_scores = all_scores[mask]
        cls_weights = all_pass_weights[mask]

        # Sort by weighted score descending
        weighted_scores = cls_scores * cls_weights
        order = np.argsort(weighted_scores)[::-1]
        cls_boxes = cls_boxes[order]
        cls_scores = cls_scores[order]
        cls_weights = cls_weights[order]

        # Greedy clustering
        # Each cluster stores: sum of weighted coords, total weight, member count, fused box
        cluster_boxes = []       # current fused box (xyxy)
        cluster_total_sw = []    # sum of score*weight
        cluster_coord_sum = []   # weighted sum of coords
        cluster_n = []           # number of members

        for i in range(len(cls_boxes)):
            box = cls_boxes[i]
            score = cls_scores[i]
            weight = cls_weights[i]
            sw = score * weight

            best_cluster = -1
            best_iou = iou_thr

            # Find best matching cluster
            for ci in range(len(cluster_boxes)):
                c_box = cluster_boxes[ci]
                ix1 = max(box[0], c_box[0])
                iy1 = max(box[1], c_box[1])
                ix2 = min(box[2], c_box[2])
                iy2 = min(box[3], c_box[3])
                inter = max(ix2 - ix1, 0) * max(iy2 - iy1, 0)
                area_a = (box[2] - box[0]) * (box[3] - box[1])
                area_b = (c_box[2] - c_box[0]) * (c_box[3] - c_box[1])
                union = area_a + area_b - inter
                iou = inter / max(union, 1e-6)

                if iou > best_iou:
                    best_iou = iou
                    best_cluster = ci

            if best_cluster >= 0:
                cluster_total_sw[best_cluster] += sw
                cluster_coord_sum[best_cluster] += box * sw
                cluster_n[best_cluster] += 1
                # Update fused box
                cluster_boxes[best_cluster] = cluster_coord_sum[best_cluster] / cluster_total_sw[best_cluster]
            else:
                cluster_boxes.append(box.copy())
                cluster_total_sw.append(sw)
                cluster_coord_sum.append(box * sw)
                cluster_n.append(1)

        # Extract fused results
        for ci in range(len(cluster_boxes)):
            avg_score = cluster_total_sw[ci] / weight_sum
            # Reward multi-source agreement
            agreement = min(cluster_n[ci] / num_models, 1.0)
            final_score = min(avg_score * (0.7 + 0.3 * agreement), 1.0)

            if final_score < skip_box_thr:
                continue

            fused_boxes.append(cluster_boxes[ci])
            fused_scores.append(final_score)
            fused_labels.append(cls_id)

    if not fused_boxes:
        return np.zeros((0, 4), dtype=np.float32), np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.int32)

    return np.array(fused_boxes), np.array(fused_scores, dtype=np.float32), np.array(fused_labels, dtype=np.int32)


def to_coco_detections(
    boxes: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    image_id: int,
) -> List[Dict[str, Any]]:
    """Convert xyxy boxes to COCO format detections."""
    detections = []
    for i in range(len(scores)):
        x1, y1, x2, y2 = boxes[i]
        detections.append({
            "image_id": image_id,
            "category_id": int(class_ids[i]),
            "bbox": [
                round(float(x1), 2),
                round(float(y1), 2),
                round(float(x2 - x1), 2),
                round(float(y2 - y1), 2),
            ],
            "score": round(float(scores[i]), 5),
        })
    return detections


def extract_image_id(filename: str) -> int:
    """Extract integer image_id from filename like img_00042.jpg -> 42."""
    stem = Path(filename).stem
    digits = "".join(c for c in stem if c.isdigit())
    if digits:
        return int(digits)
    return abs(hash(stem)) % (10**9)


def main():
    parser = argparse.ArgumentParser(description="NM i AI 2026 multi-scale ensemble")
    parser.add_argument("--input", type=str, required=True, help="Input image directory")
    parser.add_argument("--output", type=str, required=True, help="Output JSON path")
    args = parser.parse_args()

    start_time = time.monotonic()
    script_dir = Path(__file__).parent
    input_dir = Path(args.input)
    output_path = Path(args.output)

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
    model_paths = sorted(script_dir.glob("*.onnx"))
    if not model_paths:
        print("[run] No .onnx models found, writing empty output")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_path), "w") as f:
            json.dump([], f)
        return

    models = []
    for mp in model_paths:
        try:
            session = ort.InferenceSession(
                str(mp),
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            input_name = session.get_inputs()[0].name
            models.append((mp.name, session, input_name))
            print(f"[run] Loaded {mp.name}")
        except Exception as e:
            print(f"[run] Failed to load {mp.name}: {e}")

    if not models:
        print("[run] All models failed to load, writing empty output")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_path), "w") as f:
            json.dump([], f)
        return

    # Build pass definitions: each model runs at 640px and 1280px (tiled)
    passes = []
    pass_weights = []
    for model_name, session, input_name in models:
        passes.append((model_name, session, input_name, "640"))
        pass_weights.append(MODEL_WEIGHTS.get((model_name, "640"), DEFAULT_WEIGHT))
        passes.append((model_name, session, input_name, "1280"))
        pass_weights.append(MODEL_WEIGHTS.get((model_name, "1280"), DEFAULT_WEIGHT))

    num_passes = len(passes)
    print(f"[run] {len(models)} model(s), {num_passes} passes/image (640px + 1280px tiled)")
    for p, w in zip(passes, pass_weights):
        print(f"  {p[0]}@{p[3]}: weight={w}")

    # Collect image paths
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    image_paths = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in image_extensions
    )
    print(f"[run] {len(image_paths)} images to process")

    all_detections: List[Dict[str, Any]] = []
    img_times: List[float] = []
    skip_tiling = False

    for i, img_path in enumerate(image_paths):
        img_start = time.monotonic()

        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            continue

        orig_h, orig_w = img_bgr.shape[:2]
        image_id = extract_image_id(img_path.name)

        # Run all passes
        boxes_list = []
        scores_list = []
        labels_list = []
        active_weights = []

        for j, (model_name, session, input_name, scale_label) in enumerate(passes):
            if scale_label == "1280" and skip_tiling:
                continue

            if scale_label == "640":
                boxes, scores, labels = run_inference_fullimage(
                    session, input_name, img_bgr, orig_w, orig_h, category_map,
                )
            else:
                boxes, scores, labels = run_inference_tiled(
                    session, input_name, img_bgr, orig_w, orig_h, category_map,
                )

            boxes_list.append(boxes)
            scores_list.append(scores)
            labels_list.append(labels)
            active_weights.append(pass_weights[j])

        # Fuse with WBF
        if len(boxes_list) > 1:
            fused_boxes, fused_scores, fused_labels = weighted_box_fusion(
                boxes_list, scores_list, labels_list,
                weights=active_weights,
                num_models=len(active_weights),
            )
        elif len(boxes_list) == 1:
            fused_boxes, fused_scores, fused_labels = boxes_list[0], scores_list[0], labels_list[0]
        else:
            fused_boxes = np.zeros((0, 4), dtype=np.float32)
            fused_scores = np.zeros(0, dtype=np.float32)
            fused_labels = np.zeros(0, dtype=np.int32)

        dets = to_coco_detections(fused_boxes, fused_scores, fused_labels, image_id)
        all_detections.extend(dets)

        img_elapsed = time.monotonic() - img_start
        img_times.append(img_elapsed)

        total_elapsed = time.monotonic() - start_time
        remaining = TIME_LIMIT_SECONDS - total_elapsed
        images_left = len(image_paths) - (i + 1)
        avg_time = sum(img_times) / len(img_times)
        est_remaining = avg_time * images_left

        print(
            f"[run] {i+1}/{len(image_paths)} "
            f"({img_path.name}) {len(dets)} dets {img_elapsed:.2f}s | "
            f"elapsed {total_elapsed:.1f}s | "
            f"est {est_remaining:.1f}s / {remaining:.1f}s left"
        )

        # Graceful degradation: skip tiling if time is tight
        if not skip_tiling and images_left > 0 and est_remaining > (remaining - TIME_RESERVE_SECONDS):
            print(f"[run] TIME PRESSURE: disabling 1280px tiling for remaining {images_left} images")
            skip_tiling = True
            img_times.clear()

    total_time = time.monotonic() - start_time
    print(f"[run] Done: {len(all_detections)} detections from {len(image_paths)} images in {total_time:.1f}s")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w") as f:
        json.dump(all_detections, f)


if __name__ == "__main__":
    main()
