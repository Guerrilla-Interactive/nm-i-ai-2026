"""
Export a trained YOLOv8 model to ONNX format.

Usage:
    python export_onnx.py --weights runs/norgesgruppen_baseline/weights/best.pt --imgsz 640
    python export_onnx.py --weights best.pt --half --simplify --imgsz 1280

Requires: ultralytics, onnxruntime (runs locally, NOT in sandbox)
"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Export YOLOv8 to ONNX")
    parser.add_argument(
        "--weights", type=str, required=True,
        help="Path to trained YOLOv8 .pt weights",
    )
    parser.add_argument(
        "--imgsz", type=int, default=1280,
        help="Input image size (default: 1280 for small object detection)",
    )
    parser.add_argument(
        "--half", action="store_true",
        help="FP16 quantization (smaller model, faster GPU inference)",
    )
    parser.add_argument(
        "--simplify", action="store_true",
        help="Simplify ONNX graph (requires onnxslim)",
    )
    parser.add_argument(
        "--opset", type=int, default=12,
        help="ONNX opset version (default: 12 for broad compatibility)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output path for .onnx file (default: same directory as weights)",
    )
    args = parser.parse_args()

    weights_path = Path(args.weights).resolve()
    if not weights_path.exists():
        raise FileNotFoundError(f"Weights not found: {weights_path}")

    # Import ultralytics (local only — blocked in sandbox)
    from ultralytics import YOLO

    print(f"Loading model: {weights_path}")
    model = YOLO(str(weights_path))

    # Export to ONNX
    print(f"Exporting to ONNX (imgsz={args.imgsz}, half={args.half}, simplify={args.simplify}, opset={args.opset})")
    export_path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        half=args.half,
        simplify=args.simplify,
        opset=args.opset,
    )
    export_path = Path(export_path)
    print(f"Exported: {export_path}")

    # Move to custom output path if specified
    if args.output:
        import shutil
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(export_path), str(output_path))
        export_path = output_path
        print(f"Moved to: {export_path}")

    # Verify the ONNX model loads in onnxruntime
    print("\n--- Verification ---")
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(
            str(export_path),
            providers=["CPUExecutionProvider"],
        )

        print("ONNX Runtime loaded successfully!")
        print(f"\nInputs:")
        for inp in session.get_inputs():
            print(f"  {inp.name}: shape={inp.shape}, dtype={inp.type}")

        print(f"\nOutputs:")
        for out in session.get_outputs():
            print(f"  {out.name}: shape={out.shape}, dtype={out.type}")

    except ImportError:
        print("WARNING: onnxruntime not installed, skipping verification")
    except Exception as e:
        print(f"ERROR: Failed to load ONNX model: {e}")

    # Print file size
    size_mb = export_path.stat().st_size / (1024 * 1024)
    print(f"\nModel size: {size_mb:.1f} MB")
    if size_mb > 420:
        print("WARNING: Model exceeds 420MB submission limit!")
    elif size_mb > 350:
        print("NOTE: Model is large — leave room for run.py and category_map.json in ZIP")
    else:
        print(f"OK: {420 - size_mb:.1f} MB headroom within 420MB limit")


if __name__ == "__main__":
    main()
