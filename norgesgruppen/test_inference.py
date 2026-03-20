"""
Local test harness for NorgesGruppen object detection submission.

Simulates sandbox execution of submission/run.py, then evaluates predictions
against ground truth using pycocotools.

Usage:
    python test_inference.py --images data/images/val/ --gt data/annotations/val.json
    python test_inference.py --images data/images/val/ --gt data/annotations/val.json --submission-dir submission/

Reports: mAP@0.5 (detection), classification accuracy, combined score (0.7*det + 0.3*cls)
"""
import argparse
import json
import subprocess
from pathlib import Path


PROJECT_DIR = Path(__file__).parent


def check_blocked_imports(run_py: Path) -> list:
    """Quick scan for blocked imports in run.py (string-based, fast check)."""
    blocked_modules = [
        "os", "sys", "subprocess", "socket", "ctypes", "builtins",
        "importlib", "pickle", "marshal", "shelve", "shutil", "yaml",
        "requests", "urllib", "http.client", "multiprocessing",
        "threading", "signal", "gc", "code", "codeop", "pty",
    ]
    blocked_calls = ["eval(", "exec(", "compile(", "__import__("]

    warnings = []
    text = run_py.read_text()
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue

        for mod in blocked_modules:
            if f"import {mod}" in stripped or f"from {mod}" in stripped:
                warnings.append(f"  Line {i}: blocked import '{mod}' — {stripped}")

        for call in blocked_calls:
            if call in stripped:
                warnings.append(f"  Line {i}: blocked call '{call}' — {stripped}")

    return warnings


def run_submission(submission_dir: Path, images_dir: Path, output_path: Path) -> bool:
    """Run submission/run.py via subprocess, simulating sandbox execution."""
    run_py = submission_dir / "run.py"
    if not run_py.exists():
        print(f"ERROR: {run_py} not found")
        return False

    cmd = [
        "python", str(run_py),
        "--input", str(images_dir),
        "--output", str(output_path),
    ]

    print(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(submission_dir),
        )
    except subprocess.TimeoutExpired:
        print("ERROR: Inference timed out (300s limit)")
        return False

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    if result.returncode != 0:
        print(f"ERROR: run.py exited with code {result.returncode}")
        return False

    return True


def evaluate_detection(gt_path: Path, pred_path: Path) -> dict:
    """
    Evaluate detection predictions using pycocotools.

    For the detection component (70% of score), all predictions are treated
    as a single "product" class — only localization matters.
    """
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    import copy

    # Load ground truth
    coco_gt = COCO(str(gt_path))

    # Load predictions
    with open(pred_path, "r") as f:
        predictions = json.load(f)

    if not predictions:
        print("WARNING: No predictions generated!")
        return {"mAP_50": 0.0, "mAP_50_95": 0.0, "recall_100": 0.0}

    # --- Class-agnostic detection mAP ---
    # Set all category_ids to 0 (single class) for detection-only evaluation
    gt_agnostic = copy.deepcopy(coco_gt.dataset)
    gt_agnostic["categories"] = [{"id": 0, "name": "product", "supercategory": ""}]
    for ann in gt_agnostic["annotations"]:
        ann["category_id"] = 0

    coco_gt_det = COCO()
    coco_gt_det.dataset = gt_agnostic
    coco_gt_det.createIndex()

    preds_agnostic = copy.deepcopy(predictions)
    for p in preds_agnostic:
        p["category_id"] = 0

    coco_dt_det = coco_gt_det.loadRes(preds_agnostic)

    coco_eval = COCOeval(coco_gt_det, coco_dt_det, "bbox")
    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()

    stats = coco_eval.stats
    return {
        "mAP_50_95": float(stats[0]),
        "mAP_50": float(stats[1]),
        "mAP_75": float(stats[2]),
        "recall_100": float(stats[8]),
    }


def evaluate_classification_map(gt_path: Path, pred_path: Path) -> dict:
    """
    Evaluate classification using per-category mAP@0.5 (30% of score).

    This is the real metric: mAP@0.5 where category_id must match.
    """
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    coco_gt = COCO(str(gt_path))

    with open(pred_path, "r") as f:
        predictions = json.load(f)

    if not predictions:
        return {"cls_mAP_50": 0.0, "cls_mAP_50_95": 0.0}

    coco_dt = coco_gt.loadRes(predictions)

    coco_eval = COCOeval(coco_gt, coco_dt, "bbox")
    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()

    stats = coco_eval.stats
    return {
        "cls_mAP_50_95": float(stats[0]),
        "cls_mAP_50": float(stats[1]),
    }


def evaluate_classification(gt_path: Path, pred_path: Path, iou_thresh: float = 0.5) -> dict:
    """
    Evaluate classification accuracy for matched detections.

    For each ground truth box, find the best matching prediction (IoU >= threshold),
    then check if the category_id matches.
    """
    with open(gt_path, "r") as f:
        gt_data = json.load(f)
    with open(pred_path, "r") as f:
        predictions = json.load(f)

    if not predictions:
        return {"classification_accuracy": 0.0, "matched": 0, "correct": 0, "total_gt": 0}

    # Index predictions by image_id
    pred_by_image = {}
    for p in predictions:
        img_id = p["image_id"]
        if img_id not in pred_by_image:
            pred_by_image[img_id] = []
        pred_by_image[img_id].append(p)

    total_gt = 0
    matched = 0
    correct = 0

    for ann in gt_data.get("annotations", []):
        total_gt += 1
        img_id = ann["image_id"]
        gt_box = ann["bbox"]  # [x, y, w, h]
        gt_cat = ann["category_id"]

        preds = pred_by_image.get(img_id, [])
        best_iou = 0.0
        best_pred = None

        for p in preds:
            iou = compute_iou(gt_box, p["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_pred = p

        if best_iou >= iou_thresh and best_pred is not None:
            matched += 1
            if best_pred["category_id"] == gt_cat:
                correct += 1

    cls_accuracy = correct / total_gt if total_gt > 0 else 0.0

    return {
        "classification_accuracy": cls_accuracy,
        "matched": matched,
        "correct": correct,
        "total_gt": total_gt,
    }


def compute_iou(box_a: list, box_b: list) -> float:
    """Compute IoU between two [x, y, w, h] boxes."""
    ax1, ay1, aw, ah = box_a
    bx1, by1, bw, bh = box_b

    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)

    area_a = aw * ah
    area_b = bw * bh
    union_area = area_a + area_b - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def main():
    parser = argparse.ArgumentParser(description="Test NorgesGruppen submission locally")
    parser.add_argument(
        "--images", type=str, required=True,
        help="Directory containing test/val images",
    )
    parser.add_argument(
        "--gt", type=str, required=True,
        help="Ground truth COCO annotations JSON",
    )
    parser.add_argument(
        "--submission-dir", type=str,
        default=str(PROJECT_DIR / "submission"),
        help="Submission directory containing run.py (default: submission/)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output predictions JSON path (default: temp file)",
    )
    parser.add_argument(
        "--skip-inference", action="store_true",
        help="Skip inference, evaluate existing --output file",
    )
    args = parser.parse_args()

    images_dir = Path(args.images).resolve()
    gt_path = Path(args.gt).resolve()
    submission_dir = Path(args.submission_dir).resolve()
    run_py = submission_dir / "run.py"

    # Determine output path
    if args.output:
        pred_path = Path(args.output).resolve()
    else:
        pred_path = PROJECT_DIR / "test_predictions.json"

    # Check for blocked imports
    print("=== Import Check ===")
    if run_py.exists():
        warnings = check_blocked_imports(run_py)
        if warnings:
            print("WARNING: Potentially blocked imports detected:")
            for w in warnings:
                print(w)
            print()
        else:
            print("OK: No blocked imports detected (quick scan)")
    else:
        print(f"WARNING: {run_py} not found")
    print()

    # Run inference
    if not args.skip_inference:
        print("=== Running Inference ===")
        success = run_submission(submission_dir, images_dir, pred_path)
        if not success:
            print("\nInference failed. Cannot evaluate.")
            raise SystemExit(1)
        print()

    # Check predictions exist
    if not pred_path.exists():
        print(f"ERROR: Predictions file not found: {pred_path}")
        raise SystemExit(1)

    with open(pred_path, "r") as f:
        predictions = json.load(f)
    print(f"Predictions: {len(predictions)} detections")
    print()

    # Evaluate detection (class-agnostic mAP — 70% of score)
    print("=== Detection Evaluation (class-agnostic mAP@0.5) ===")
    det_metrics = evaluate_detection(gt_path, pred_path)
    print()

    # Evaluate classification (per-category mAP — 30% of score)
    print("=== Classification Evaluation (per-category mAP@0.5) ===")
    cls_metrics = evaluate_classification_map(gt_path, pred_path)
    print()

    # Simple match stats for quick reference
    print("=== Quick Match Stats ===")
    simple_cls = evaluate_classification(gt_path, pred_path)
    print(f"  Ground truth annotations: {simple_cls['total_gt']}")
    print(f"  Matched detections (IoU >= 0.5): {simple_cls['matched']}")
    print(f"  Correct category: {simple_cls['correct']}")
    print(f"  Simple accuracy: {simple_cls['classification_accuracy']:.4f}")
    print()

    # Combined score (competition formula)
    detection_score = det_metrics["mAP_50"]
    classification_score = cls_metrics["cls_mAP_50"]
    combined = 0.7 * detection_score + 0.3 * classification_score

    print("=" * 50)
    print("  COMPETITION SCORE ESTIMATE")
    print("=" * 50)
    print(f"  Detection mAP@0.5:        {detection_score:.4f}  × 0.7 = {0.7 * detection_score:.4f}")
    print(f"  Classification mAP@0.5:   {classification_score:.4f}  × 0.3 = {0.3 * classification_score:.4f}")
    print(f"  Combined score:            {combined:.4f}")
    print()
    print(f"  Detection mAP@0.5:0.95:   {det_metrics['mAP_50_95']:.4f}")
    print(f"  Detection recall@100:      {det_metrics['recall_100']:.4f}")


if __name__ == "__main__":
    main()
