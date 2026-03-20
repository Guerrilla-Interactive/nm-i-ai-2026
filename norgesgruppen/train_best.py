"""
Best-effort YOLO11x training at 1280px for NorgesGruppen grocery detection.

Aggressive augmentation, label smoothing, cosine LR schedule.
Designed for GPU with >= 16GB VRAM (auto batch sizing).

Usage:
  python train_best.py                                  # Defaults: yolo11x, 1280px, 200 epochs
  python train_best.py --data-yaml norgesgruppen_with_synthetic.yaml
  python train_best.py --model yolo11l.pt --imgsz 640   # Smaller model/resolution
  python train_best.py --export-only                     # Just export best.pt to ONNX
  python train_best.py --resume                          # Resume interrupted training

ONNX output: ~260MB for yolo11x (well under 420MB limit)
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

from ultralytics import YOLO

BASE_DIR = Path(__file__).parent
DEFAULT_DATA_YAML = BASE_DIR / "norgesgruppen.yaml"
SYNTHETIC_DATA_YAML = BASE_DIR / "norgesgruppen_with_synthetic.yaml"
RUNS_DIR = BASE_DIR / "runs"
SUBMISSION_DIR = BASE_DIR / "submission"
RUN_NAME = "best_x_1280"
MAX_ONNX_SIZE_MB = 420


def pick_data_yaml(args):
    """Select dataset YAML: explicit arg > synthetic (if exists) > default."""
    if args.data_yaml:
        p = Path(args.data_yaml)
        if not p.is_absolute():
            p = BASE_DIR / p
        if p.exists():
            return str(p)
        print(f"WARNING: --data-yaml {args.data_yaml} not found, falling back")

    # Auto-detect synthetic data
    if SYNTHETIC_DATA_YAML.exists():
        synth_dir = BASE_DIR / "data" / "images" / "synthetic"
        if synth_dir.exists() and any(synth_dir.iterdir()):
            print(f"Auto-detected synthetic data: {SYNTHETIC_DATA_YAML}")
            return str(SYNTHETIC_DATA_YAML)

    if not DEFAULT_DATA_YAML.exists():
        print(f"ERROR: Dataset YAML not found at {DEFAULT_DATA_YAML}")
        sys.exit(1)

    return str(DEFAULT_DATA_YAML)


def train(args):
    """Run YOLO11x training with aggressive augmentation."""
    data_yaml = pick_data_yaml(args)

    print("=" * 60)
    print("BEST MODEL TRAINING — NorgesGruppen Object Detection")
    print("=" * 60)
    print(f"  Model:      {args.model}")
    print(f"  Image size: {args.imgsz}")
    print(f"  Batch size: {args.batch} ({'auto' if args.batch == -1 else 'fixed'})")
    print(f"  Epochs:     {args.epochs}")
    print(f"  Patience:   {args.patience}")
    print(f"  LR:         {args.lr} -> {args.lr * 0.01}")
    print(f"  Data:       {data_yaml}")
    print(f"  Run name:   {RUN_NAME}")
    print("=" * 60)

    model = YOLO(args.model)

    results = model.train(
        data=data_yaml,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        amp=True,
        patience=args.patience,

        # === Learning Rate ===
        lr0=args.lr,
        lrf=0.01,
        warmup_epochs=5,
        warmup_momentum=0.8,
        warmup_bias_lr=0.01,

        # === Optimizer ===
        optimizer="AdamW",
        weight_decay=0.0005,
        cos_lr=True,

        # === Augmentation — AGGRESSIVE for 248 images, 356 classes ===
        mosaic=1.0,
        close_mosaic=15,
        mixup=0.3,
        copy_paste=0.2,
        scale=0.5,
        degrees=15.0,
        translate=0.2,
        shear=3.0,
        perspective=0.0005,
        flipud=0.0,
        fliplr=0.5,
        hsv_h=0.02,
        hsv_s=0.7,
        hsv_v=0.5,
        erasing=0.2,

        # === Classification head ===
        label_smoothing=0.1,
        dropout=0.1,

        # === Output ===
        project=str(RUNS_DIR),
        name=RUN_NAME,
        exist_ok=True,
        save=True,
        save_period=25,
        plots=True,
        verbose=True,
    )

    return results


def export_onnx(args):
    """Export best.pt to ONNX and verify size."""
    weights_path = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    if not weights_path.exists():
        print(f"ERROR: Best weights not found at {weights_path}")
        return None

    print(f"\nExporting {weights_path} to ONNX (imgsz={args.imgsz})")
    model = YOLO(str(weights_path))

    export_path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        simplify=True,
        dynamic=False,
        half=False,
    )

    onnx_path = Path(export_path)
    size_mb = onnx_path.stat().st_size / (1024 * 1024)
    print(f"ONNX model exported: {export_path} ({size_mb:.1f} MB)")

    if size_mb > MAX_ONNX_SIZE_MB:
        print(f"WARNING: ONNX exceeds {MAX_ONNX_SIZE_MB} MB limit!")
        print("Trying FP16 export to reduce size...")
        export_path_fp16 = model.export(
            format="onnx",
            imgsz=args.imgsz,
            simplify=True,
            dynamic=False,
            half=True,
        )
        fp16_path = Path(export_path_fp16)
        fp16_size = fp16_path.stat().st_size / (1024 * 1024)
        print(f"FP16 ONNX: {fp16_path} ({fp16_size:.1f} MB)")
        if fp16_size <= MAX_ONNX_SIZE_MB:
            print("FP16 model fits! Using FP16 version.")
            return str(fp16_path)
        else:
            print("CRITICAL: Even FP16 exceeds limit. Consider a smaller model.")
    else:
        print(f"OK: {size_mb:.1f} MB is under {MAX_ONNX_SIZE_MB} MB limit")

    return str(export_path)


def prepare_submission():
    """Copy ONNX + run.py + category_map to submission/."""
    SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)

    for name in ["run.py", "category_map.json"]:
        src = BASE_DIR / name
        if src.exists():
            shutil.copy2(str(src), str(SUBMISSION_DIR / name))
            print(f"Copied {name} to submission/")

    onnx_src = RUNS_DIR / RUN_NAME / "weights" / "best.onnx"
    if onnx_src.exists():
        dest = SUBMISSION_DIR / "best.onnx"
        shutil.copy2(str(onnx_src), str(dest))
        size_mb = onnx_src.stat().st_size / (1024 * 1024)
        print(f"Copied best.onnx ({size_mb:.1f} MB) to submission/")

    total = sum(f.stat().st_size for f in SUBMISSION_DIR.rglob("*") if f.is_file())
    total_mb = total / (1024 * 1024)
    print(f"\nSubmission total: {total_mb:.1f} MB (limit: {MAX_ONNX_SIZE_MB} MB)")
    if total_mb > MAX_ONNX_SIZE_MB:
        print("WARNING: Submission exceeds size limit!")
    else:
        print("OK: Under size limit")


def main():
    parser = argparse.ArgumentParser(description="Train best YOLO11 model for NorgesGruppen")
    parser.add_argument("--model", type=str, default="yolo11x.pt", help="Base model (yolo11n/s/m/l/x.pt)")
    parser.add_argument("--epochs", type=int, default=200, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=1280, help="Input image size")
    parser.add_argument("--batch", type=int, default=-1, help="Batch size (-1 = auto)")
    parser.add_argument("--lr", type=float, default=0.001, help="Initial learning rate")
    parser.add_argument("--patience", type=int, default=50, help="Early stopping patience")
    parser.add_argument("--data-yaml", type=str, default="", help="Path to dataset YAML config")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted training")
    parser.add_argument("--export-only", action="store_true", help="Only export to ONNX")
    parser.add_argument("--no-export", action="store_true", help="Skip ONNX export")
    parser.add_argument("--prepare-submission", action="store_true", help="Also prepare submission/")
    args = parser.parse_args()

    if args.resume:
        last_pt = RUNS_DIR / RUN_NAME / "weights" / "last.pt"
        if last_pt.exists():
            print(f"Resuming from {last_pt}")
            model = YOLO(str(last_pt))
            model.train(resume=True)
        else:
            print(f"ERROR: No checkpoint found at {last_pt}")
        return

    if args.export_only:
        export_onnx(args)
        if args.prepare_submission:
            prepare_submission()
        return

    start = time.time()
    results = train(args)
    elapsed = time.time() - start

    print()
    print("=" * 60)
    if results is not None:
        print("TRAINING COMPLETE")
        try:
            d = results.results_dict
            print(f"  mAP50:     {d.get('metrics/mAP50(B)', 'N/A')}")
            print(f"  mAP50-95:  {d.get('metrics/mAP50-95(B)', 'N/A')}")
            print(f"  Precision: {d.get('metrics/precision(B)', 'N/A')}")
            print(f"  Recall:    {d.get('metrics/recall(B)', 'N/A')}")
        except Exception as e:
            print(f"  Metrics error: {e}")

        if not args.no_export:
            export_onnx(args)

        if args.prepare_submission:
            prepare_submission()
    else:
        print("TRAINING FAILED")

    print(f"  Elapsed: {elapsed/3600:.1f}h ({elapsed/60:.0f}m)")
    print(f"  Weights: {RUNS_DIR / RUN_NAME / 'weights' / 'best.pt'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
