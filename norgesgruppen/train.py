"""
YOLOv8 training script for NorgesGruppen grocery detection.

This runs on the TRAINING machine (local Mac / GCP VM), NOT in the sandbox.
ultralytics is fine to use here.

After training, the best model is exported to ONNX for sandbox inference.

Usage:
  python train.py                          # Defaults: yolov8x, 200 epochs, 640px
  python train.py --model yolov8l.pt       # Use large variant
  python train.py --epochs 100 --imgsz 1280 --batch 4
  python train.py --resume                 # Resume interrupted training
  python train.py --export-only            # Just export existing best.pt to ONNX
"""

import argparse
import json
import shutil
from pathlib import Path

from ultralytics import YOLO


BASE_DIR = Path(__file__).parent
DATA_YAML = BASE_DIR / "norgesgruppen.yaml"
RUNS_DIR = BASE_DIR / "runs"
SUBMISSION_DIR = BASE_DIR / "submission"


def train(args):
    """Run YOLOv8 training."""
    # Verify dataset config exists
    if not DATA_YAML.exists():
        print(f"ERROR: Dataset YAML not found at {DATA_YAML}")
        print("Run convert_coco_to_yolo.py first!")
        return None

    print(f"Model: {args.model}")
    print(f"Epochs: {args.epochs}")
    print(f"Image size: {args.imgsz}")
    print(f"Batch: {args.batch}")
    print(f"Run name: {args.name}")
    print()

    model = YOLO(args.model)

    results = model.train(
        data=str(DATA_YAML),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        amp=True,
        patience=args.patience,
        # Learning rate — lower for transfer learning from COCO
        lr0=args.lr,
        lrf=0.01,           # Final LR = lr0 * lrf
        warmup_epochs=3,
        warmup_momentum=0.8,
        # Augmentation — aggressive for small dataset (248 images)
        mosaic=1.0,          # Mosaic: combine 4 images (critical for small datasets)
        close_mosaic=10,     # Disable mosaic for last 10 epochs (fine-tune on clean images)
        mixup=0.15,          # Blend two images with alpha
        copy_paste=0.1,      # Copy-paste augmentation
        scale=0.9,           # Random scale ±90%
        degrees=10.0,        # Random rotation ±10°
        translate=0.2,       # Random translation ±20%
        shear=2.0,           # Random shear ±2°
        flipud=0.0,          # No vertical flip (shelf images have orientation)
        fliplr=0.5,          # Horizontal flip
        hsv_h=0.015,         # Hue augmentation
        hsv_s=0.7,           # Saturation augmentation
        hsv_v=0.4,           # Brightness augmentation
        erasing=0.1,         # Random erasing
        # Regularization
        label_smoothing=0.1, # Helps with 356 similar-looking classes
        weight_decay=0.0005,
        dropout=0.0,         # No dropout for detection (YOLO default)
        # Output
        project=str(RUNS_DIR),
        name=args.name,
        exist_ok=True,
        save=True,
        save_period=25,      # Checkpoint every 25 epochs
        plots=True,
        verbose=True,
    )

    return results


def export_onnx(args):
    """Export best.pt to ONNX format."""
    weights_path = RUNS_DIR / args.name / "weights" / "best.pt"

    if not weights_path.exists():
        print(f"ERROR: Best weights not found at {weights_path}")
        return None

    print(f"Exporting {weights_path} to ONNX (imgsz={args.imgsz})")
    model = YOLO(str(weights_path))

    export_path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        simplify=True,
        dynamic=False,
        half=False,  # Keep FP32 for accuracy; FP16 optional for size savings
    )

    print(f"ONNX model exported: {export_path}")
    return export_path


def prepare_submission(args):
    """Copy required files to submission/ directory."""
    SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)

    # Copy run.py
    run_py = BASE_DIR / "run.py"
    if run_py.exists():
        shutil.copy2(str(run_py), str(SUBMISSION_DIR / "run.py"))
        print(f"Copied run.py to submission/")

    # Copy category_map.json
    cat_map = BASE_DIR / "category_map.json"
    if cat_map.exists():
        shutil.copy2(str(cat_map), str(SUBMISSION_DIR / "category_map.json"))
        print(f"Copied category_map.json to submission/")

    # Copy ONNX model
    onnx_src = RUNS_DIR / args.name / "weights" / "best.onnx"
    if onnx_src.exists():
        shutil.copy2(str(onnx_src), str(SUBMISSION_DIR / "best.onnx"))
        size_mb = onnx_src.stat().st_size / (1024 * 1024)
        print(f"Copied best.onnx ({size_mb:.1f} MB) to submission/")

    # Report total size
    total = sum(f.stat().st_size for f in SUBMISSION_DIR.rglob("*") if f.is_file())
    total_mb = total / (1024 * 1024)
    print(f"\nSubmission total: {total_mb:.1f} MB (limit: 420 MB)")

    if total_mb > 420:
        print("WARNING: Submission exceeds 420 MB limit!")
    else:
        print("OK: Under size limit")

    # Count files
    py_files = list(SUBMISSION_DIR.glob("*.py"))
    weight_files = [f for f in SUBMISSION_DIR.iterdir() if f.suffix in {".onnx", ".pt", ".pth", ".safetensors"}]
    print(f"Python files: {len(py_files)}/10, Weight files: {len(weight_files)}/3")


def main():
    parser = argparse.ArgumentParser(description="Train YOLOv8 for NorgesGruppen")
    parser.add_argument("--model", type=str, default="yolov8x.pt", help="Base model (yolov8n/s/m/l/x.pt)")
    parser.add_argument("--epochs", type=int, default=200, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size")
    parser.add_argument("--batch", type=int, default=-1, help="Batch size (-1 = auto)")
    parser.add_argument("--lr", type=float, default=0.001, help="Initial learning rate")
    parser.add_argument("--patience", type=int, default=50, help="Early stopping patience")
    parser.add_argument("--name", type=str, default="norgesgruppen_baseline", help="Run name")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted training")
    parser.add_argument("--export-only", action="store_true", help="Only export to ONNX (skip training)")
    parser.add_argument("--no-export", action="store_true", help="Skip ONNX export after training")
    parser.add_argument("--prepare-submission", action="store_true", help="Copy files to submission/")
    args = parser.parse_args()

    # Resume interrupted training
    if args.resume:
        last_pt = RUNS_DIR / args.name / "weights" / "last.pt"
        if last_pt.exists():
            print(f"Resuming from {last_pt}")
            model = YOLO(str(last_pt))
            model.train(resume=True)
        else:
            print(f"ERROR: No checkpoint found at {last_pt}")
        return

    # Export only
    if args.export_only:
        export_onnx(args)
        if args.prepare_submission:
            prepare_submission(args)
        return

    # Full pipeline: train → export → prepare
    results = train(args)

    if results is not None and not args.no_export:
        export_onnx(args)

    if args.prepare_submission:
        prepare_submission(args)

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    print(f"Results: {RUNS_DIR / args.name}")
    print(f"Best weights: {RUNS_DIR / args.name / 'weights' / 'best.pt'}")
    print()
    print("Next steps:")
    print(f"  1. Export:  python train.py --export-only")
    print(f"  2. Bundle:  python train.py --export-only --prepare-submission")
    print(f"  3. Submit:  cd submission && zip -r ../submission.zip . -x '.*'")


if __name__ == "__main__":
    main()
