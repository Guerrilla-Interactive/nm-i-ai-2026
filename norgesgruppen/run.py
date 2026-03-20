"""
NM i AI 2026 — NorgesGruppen Object Detection
Competition sandbox inference script using ONNX Runtime.

NOTE: This is the canonical copy. submission/run.py should be identical.
      train.py --prepare-submission copies this file into submission/.
"""
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

import cv2
import numpy as np
import onnxruntime as ort


CONF_THRESH = 0.01
NMS_IOU_THRESH = 0.5
INPUT_SIZE = 640
PAD_COLOR = (114, 114, 114)


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
    Decode YOLOv8 ONNX output → COCO-format detections.

    Output shape: (1, 4+num_classes, 8400)
    Transpose to: (8400, 4+num_classes)
    boxes[:, :4] = cx, cy, w, h  (in model input coords)
    scores[:, 4:] = class confidence scores
    """
    # (1, 360, 8400) → (8400, 360)
    pred = output[0].T

    boxes_cxcywh = pred[:, :4]
    class_scores = pred[:, 4:]

    num_classes = class_scores.shape[1]

    # Best class per detection
    max_scores = np.max(class_scores, axis=1)
    class_ids = np.argmax(class_scores, axis=1)

    # Confidence filter
    mask = max_scores > conf_thresh
    boxes_cxcywh = boxes_cxcywh[mask]
    max_scores = max_scores[mask]
    class_ids = class_ids[mask]

    if len(boxes_cxcywh) == 0:
        return []

    # cx,cy,w,h → x1,y1,w,h for NMS (cv2 expects x,y,w,h top-left)
    boxes_xywh = np.copy(boxes_cxcywh)
    boxes_xywh[:, 0] = boxes_cxcywh[:, 0] - boxes_cxcywh[:, 2] / 2  # x1
    boxes_xywh[:, 1] = boxes_cxcywh[:, 1] - boxes_cxcywh[:, 3] / 2  # y1

    # NMS per class
    indices = cv2.dnn.NMSBoxes(
        boxes_xywh.tolist(),
        max_scores.tolist(),
        conf_thresh,
        iou_thresh,
    )

    if len(indices) == 0:
        return []

    # Flatten indices (cv2 returns nested array in some versions)
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

        # Map YOLO index → COCO category_id
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
        # Handle both list format [cat0, cat1, ...] and dict format {"0": cat0, ...}
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

        orig_h, orig_w = img_bgr.shape[:2]
        image_id = extract_image_id(img_path.name)

        # Preprocess
        blob, scale, pad_left, pad_top = preprocess(img_bgr, model_input_size)

        # Inference
        outputs = session.run(None, {input_name: blob})
        output = outputs[0]  # (1, 4+num_classes, 8400)

        # Postprocess
        dets = postprocess(
            output, orig_w, orig_h, scale, pad_left, pad_top, category_map,
        )

        # Attach image_id
        for det in dets:
            det["image_id"] = image_id

        all_detections.extend(dets)

    # Write output (output directory is pre-created by the sandbox)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(output_path), "w") as f:
        json.dump(all_detections, f)


if __name__ == "__main__":
    main()
