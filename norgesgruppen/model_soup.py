"""
Model Soup — Average weights from multiple YOLO11x training runs.

Averages .pt state dicts and exports the result to ONNX.
Only works with models of the SAME architecture (e.g., all YOLO11x).

Usage:
    python model_soup.py best_v1.pt best_v2.pt
    python model_soup.py best_v1.pt best_v2.pt best_v3.pt --output /workspace/soup_best.onnx
    python model_soup.py best_v1.pt best_v2.pt --imgsz 960
"""
import argparse
import sys
from pathlib import Path

import torch


def main():
    parser = argparse.ArgumentParser(description="Model soup: average YOLO weights and export ONNX")
    parser.add_argument("weights", nargs="+", help="Paths to 2-3 best.pt files")
    parser.add_argument("--output", type=str, default="/workspace/soup_best.onnx",
                        help="Output ONNX path (default: /workspace/soup_best.onnx)")
    parser.add_argument("--imgsz", type=int, default=1280,
                        help="Export image size (default: 1280)")
    parser.add_argument("--base-model", type=str, default="yolo11x.pt",
                        help="Base model architecture for loading (default: yolo11x.pt)")
    args = parser.parse_args()

    if len(args.weights) < 2:
        print("ERROR: Need at least 2 weight files for model soup.")
        sys.exit(1)

    # Verify all files exist
    for p in args.weights:
        if not Path(p).exists():
            print(f"ERROR: Weight file not found: {p}")
            sys.exit(1)

    print(f"Model Soup: averaging {len(args.weights)} models")
    print(f"  Models: {args.weights}")
    print(f"  Output: {args.output}")
    print(f"  imgsz:  {args.imgsz}")
    print()

    # Load state dicts
    state_dicts = []
    for p in args.weights:
        print(f"  Loading {p}...")
        ckpt = torch.load(p, map_location="cpu")
        # ultralytics saves model in ckpt['model'].state_dict()
        sd = ckpt["model"].float().state_dict()
        state_dicts.append(sd)

    # Verify all state dicts have the same keys
    keys_0 = set(state_dicts[0].keys())
    for i, sd in enumerate(state_dicts[1:], 1):
        keys_i = set(sd.keys())
        if keys_0 != keys_i:
            missing = keys_0 - keys_i
            extra = keys_i - keys_0
            print(f"WARNING: Model {i} has different keys!")
            if missing:
                print(f"  Missing: {list(missing)[:5]}...")
            if extra:
                print(f"  Extra: {list(extra)[:5]}...")
            print("  Model soup only works with SAME architecture. Aborting.")
            sys.exit(1)

    # Average weights
    print(f"\n  Averaging {len(state_dicts)} state dicts ({len(keys_0)} parameters)...")
    avg_sd = {}
    for key in state_dicts[0]:
        avg_sd[key] = sum(sd[key] for sd in state_dicts) / len(state_dicts)

    # Load averaged weights into a fresh model and export
    from ultralytics import YOLO

    print(f"  Loading base model: {args.base_model}")
    model = YOLO(args.base_model)
    model.model.load_state_dict(avg_sd)

    print(f"  Exporting to ONNX at imgsz={args.imgsz}...")
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Export — ultralytics puts ONNX next to the .pt file by default,
    # so we save a temp .pt first, then export, then move.
    temp_pt = output_path.with_suffix(".pt")
    # Save the souped model as .pt
    ckpt["model"] = model.model
    torch.save(ckpt, str(temp_pt))

    # Re-load and export via ultralytics API
    soup_model = YOLO(str(temp_pt))
    export_path = soup_model.export(format="onnx", imgsz=args.imgsz, simplify=True)

    # Move ONNX to desired output path if needed
    export_path = Path(export_path)
    if export_path != output_path:
        import shutil
        shutil.move(str(export_path), str(output_path))

    # Clean up temp .pt
    temp_pt.unlink(missing_ok=True)

    # Report
    size_mb = output_path.stat().st_size / 1024 / 1024
    print()
    print("=" * 60)
    print("MODEL SOUP COMPLETE")
    print(f"  Output: {output_path}")
    print(f"  Size:   {size_mb:.1f} MB (limit: 420 MB)")
    print(f"  Models averaged: {len(args.weights)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
