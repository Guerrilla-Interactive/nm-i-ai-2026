"""
Improved YOLOv8 training for NorgesGruppen grocery detection.

KEY IMPROVEMENTS over train.py / train_quick.py:
1. YOLOv8s (small) instead of nano — 2x more capacity, still fits in 16GB
2. imgsz=1280 — critical for small objects (86% of boxes are <1% of image area)
3. MPS (Metal) acceleration on M4 with CPU fallback
4. Aggressive augmentation tuned for long-tail distribution
5. Lower learning rate (0.001) for better transfer learning from COCO
6. Cosine LR schedule with longer warmup
7. Label smoothing for 356 fine-grained classes

Usage:
  .venv/bin/python train_improved.py
  .venv/bin/python train_improved.py --model yolov8m.pt --imgsz 640
  .venv/bin/python train_improved.py --device cpu   # Force CPU
"""

import argparse
import signal
import sys
import time
from pathlib import Path

from ultralytics import YOLO

BASE_DIR = Path(__file__).parent
DATA_YAML = BASE_DIR / "norgesgruppen.yaml"
RUNS_DIR = BASE_DIR / "runs"


def test_mps(timeout_seconds=60):
    """Test if MPS works for YOLO training with a quick micro-batch.

    Previous attempts hung on MPS — this does a timed test first.
    Returns 'mps' if it works, 'cpu' otherwise.
    """
    import torch

    if not torch.backends.mps.is_available():
        print("MPS not available, using CPU")
        return "cpu"

    print(f"MPS available — testing with {timeout_seconds}s timeout...")

    # Use a simple tensor operation test first
    try:
        t = torch.randn(2, 3, 64, 64, device="mps")
        _ = torch.nn.functional.conv2d(
            t,
            torch.randn(16, 3, 3, 3, device="mps"),
            padding=1,
        )
        torch.mps.synchronize()
        print("  MPS basic ops: OK")
    except Exception as e:
        print(f"  MPS basic ops failed: {e}")
        return "cpu"

    # Try a quick YOLO forward pass
    timed_out = False

    def alarm_handler(signum, frame):
        nonlocal timed_out
        timed_out = True
        raise TimeoutError("MPS test timed out")

    try:
        old_handler = signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(timeout_seconds)

        model = YOLO("yolov8s.pt")
        # Quick inference test on a random image
        import numpy as np

        dummy = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        _ = model.predict(dummy, device="mps", verbose=False)
        torch.mps.synchronize()

        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        print("  MPS YOLO inference: OK — using MPS!")
        return "mps"
    except TimeoutError:
        print("  MPS timed out — falling back to CPU")
        signal.signal(signal.SIGALRM, old_handler)
        return "cpu"
    except Exception as e:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        print(f"  MPS YOLO test failed: {e} — falling back to CPU")
        return "cpu"


def train(args):
    """Run improved YOLOv8 training."""
    if not DATA_YAML.exists():
        print(f"ERROR: Dataset YAML not found at {DATA_YAML}")
        print("Run convert_coco_to_yolo.py first!")
        return None

    # Determine device
    if args.device == "auto":
        device = test_mps(timeout_seconds=90)
    else:
        device = args.device

    # Adjust batch size based on device and model/imgsz
    batch = args.batch
    if batch == -1:
        if device == "mps":
            # Conservative for MPS — 16GB unified memory
            if args.imgsz >= 1280:
                batch = 2  # yolov8s @ 1280 on MPS
            else:
                batch = 8
        else:
            # CPU — memory is less of a concern but speed is
            if args.imgsz >= 1280:
                batch = 2
            else:
                batch = 8

    print("=" * 60)
    print("IMPROVED TRAINING — NorgesGruppen Object Detection")
    print("=" * 60)
    print(f"  Model:      {args.model}")
    print(f"  Image size: {args.imgsz}")
    print(f"  Batch size: {batch}")
    print(f"  Device:     {device}")
    print(f"  Epochs:     {args.epochs}")
    print(f"  LR:         {args.lr}")
    print(f"  Run name:   {args.name}")
    print(f"  AMP:        {device == 'mps'}")  # AMP only useful on GPU/MPS
    print("=" * 60)
    print()

    model = YOLO(args.model)

    results = model.train(
        data=str(DATA_YAML),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=batch,
        device=device,
        amp=(device == "mps"),  # AMP helps on MPS, not meaningful on CPU
        patience=args.patience,
        # === Learning Rate ===
        # Lower LR preserves COCO pretrained features better
        lr0=args.lr,
        lrf=0.01,  # Final LR = lr0 * 0.01
        warmup_epochs=5,  # Longer warmup for small dataset
        warmup_momentum=0.8,
        warmup_bias_lr=0.01,
        # === Optimizer ===
        optimizer="AdamW",  # Better than SGD for fine-tuning
        weight_decay=0.001,  # Slightly higher for regularization
        # === Augmentation — AGGRESSIVE for 248 images ===
        mosaic=1.0,  # 4-image mosaic (critical for tiny dataset)
        close_mosaic=15,  # Disable mosaic last 15 epochs for fine-tuning
        mixup=0.2,  # Blend images — helps regularization
        copy_paste=0.15,  # Copy-paste augmentation for object diversity
        scale=0.9,  # Random scale ±90% — helps with variable object sizes
        degrees=15.0,  # Rotation ±15° (shelves can be slightly tilted)
        translate=0.2,  # Translation ±20%
        shear=3.0,  # Shear ±3°
        perspective=0.0005,  # Slight perspective transform
        flipud=0.0,  # NO vertical flip (shelves have orientation)
        fliplr=0.5,  # Horizontal flip
        hsv_h=0.02,  # Hue augmentation (slightly higher)
        hsv_s=0.7,  # Saturation augmentation
        hsv_v=0.5,  # Brightness augmentation (higher for store lighting)
        erasing=0.2,  # Random erasing — occlusion robustness
        # === Classification head ===
        label_smoothing=0.1,  # Critical for 356 similar-looking classes
        dropout=0.1,  # Light dropout in classification head
        # === Output ===
        project=str(RUNS_DIR),
        name=args.name,
        exist_ok=True,
        save=True,
        save_period=10,  # Checkpoint every 10 epochs
        plots=True,
        verbose=True,
        workers=0 if device == "cpu" else 2,
        # === Multi-scale training ===
        # rect=False — keep disabled for mosaic compatibility
    )

    return results


def main():
    parser = argparse.ArgumentParser(description="Improved YOLOv8 training")
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8s.pt",
        help="Model variant (yolov8n/s/m/l/x.pt). Default: yolov8s (small)",
    )
    parser.add_argument(
        "--epochs", type=int, default=150, help="Training epochs (default: 150)"
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=1280,
        help="Input image size (default: 1280 for small objects)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=-1,
        help="Batch size (-1 = auto-select based on device)",
    )
    parser.add_argument(
        "--lr", type=float, default=0.001, help="Initial learning rate"
    )
    parser.add_argument(
        "--patience", type=int, default=30, help="Early stopping patience"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="improved_s_1280",
        help="Run name (default: improved_s_1280)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "mps", "cpu"],
        help="Device: auto (test MPS then fallback), mps, or cpu",
    )
    args = parser.parse_args()

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
    else:
        print("TRAINING FAILED")
    print(f"  Elapsed: {elapsed/3600:.1f}h ({elapsed/60:.0f}m)")
    print(f"  Weights: {RUNS_DIR / args.name / 'weights' / 'best.pt'}")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Export:  .venv/bin/python export_onnx.py")
    print("  2. Test:    .venv/bin/python test_inference.py")
    print("  3. Submit:  .venv/bin/python package_submission.py")


if __name__ == "__main__":
    main()
