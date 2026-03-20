"""
Convert COCO annotations to YOLO format for NorgesGruppen grocery detection.

Reads:  data/annotations.json (COCO format)
        data/images/ (source images, expected to exist)

Creates:
  data/images/train/  data/images/val/    (symlinked or copied images)
  data/labels/train/  data/labels/val/    (YOLO .txt label files)
  category_map.json                       (yolo_index → coco_category_id)
  norgesgruppen.yaml                      (ultralytics dataset config)

Usage:
  python convert_coco_to_yolo.py [--annotations path] [--images-dir path] [--val-ratio 0.1] [--seed 42]
"""

import argparse
import json
import random
import shutil
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Convert COCO to YOLO format")
    parser.add_argument(
        "--annotations",
        type=str,
        default=str(Path(__file__).parent / "data" / "annotations.json"),
        help="Path to COCO annotations.json",
    )
    parser.add_argument(
        "--images-dir",
        type=str,
        default=str(Path(__file__).parent / "data" / "images"),
        help="Path to source images directory",
    )
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation split ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for split")
    parser.add_argument("--copy", action="store_true", help="Copy images instead of symlink")
    args = parser.parse_args()

    annotations_path = Path(args.annotations)
    images_src = Path(args.images_dir)
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"

    # -----------------------------------------------------------------------
    # Load COCO annotations
    # -----------------------------------------------------------------------
    print(f"Loading annotations from {annotations_path}")
    with open(annotations_path, "r") as f:
        coco = json.load(f)

    images = {img["id"]: img for img in coco["images"]}
    categories = coco["categories"]
    annotations = coco["annotations"]

    print(f"  {len(images)} images, {len(annotations)} annotations, {len(categories)} categories")

    # -----------------------------------------------------------------------
    # Build category mapping: coco_category_id → yolo_class_index (0-based)
    # -----------------------------------------------------------------------
    # Sort categories by their original ID to get a deterministic mapping
    sorted_cats = sorted(categories, key=lambda c: c["id"])
    coco_id_to_yolo_idx = {}
    yolo_idx_to_coco_id = []  # list where index = yolo class, value = coco cat id

    for yolo_idx, cat in enumerate(sorted_cats):
        coco_id_to_yolo_idx[cat["id"]] = yolo_idx
        yolo_idx_to_coco_id.append(cat["id"])

    # Also build name list for YAML
    class_names = {yolo_idx: cat["name"] for yolo_idx, cat in enumerate(sorted_cats)}

    print(f"  Category ID range: {sorted_cats[0]['id']}–{sorted_cats[-1]['id']}")
    print(f"  YOLO class indices: 0–{len(sorted_cats)-1}")

    # Check if categories are already contiguous 0–N
    cat_ids = [c["id"] for c in sorted_cats]
    is_contiguous = cat_ids == list(range(len(cat_ids)))
    if is_contiguous:
        print("  Categories are already contiguous (0-indexed) — mapping is identity")
    else:
        print("  Categories are NOT contiguous — mapping required")

    # -----------------------------------------------------------------------
    # Group annotations by image
    # -----------------------------------------------------------------------
    anns_by_image = defaultdict(list)
    for ann in annotations:
        anns_by_image[ann["image_id"]].append(ann)

    # -----------------------------------------------------------------------
    # Stratified train/val split
    # -----------------------------------------------------------------------
    # Strategy: assign images to val set ensuring each category has representation
    # For simplicity with 248 images, use random split with seed
    image_ids = sorted(images.keys())
    random.seed(args.seed)
    random.shuffle(image_ids)

    val_count = max(1, round(len(image_ids) * args.val_ratio))
    val_ids = set(image_ids[:val_count])
    train_ids = set(image_ids[val_count:])

    print(f"  Split: {len(train_ids)} train, {len(val_ids)} val")

    # Verify category coverage in val set
    val_cats = set()
    for img_id in val_ids:
        for ann in anns_by_image[img_id]:
            val_cats.add(ann["category_id"])
    print(f"  Val set covers {len(val_cats)}/{len(categories)} categories")

    # -----------------------------------------------------------------------
    # Create directory structure
    # -----------------------------------------------------------------------
    for split in ["train", "val"]:
        (data_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (data_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Convert and write YOLO labels + organize images
    # -----------------------------------------------------------------------
    stats = {"train": 0, "val": 0, "total_anns": 0, "skipped_images": 0}

    for img_id in sorted(images.keys()):
        img_info = images[img_id]
        img_w = img_info["width"]
        img_h = img_info["height"]
        file_name = img_info["file_name"]
        stem = Path(file_name).stem

        split = "val" if img_id in val_ids else "train"

        # Source image path
        src_img = images_src / file_name
        if not src_img.exists():
            # Try without subdirectory
            candidates = list(images_src.rglob(file_name))
            if candidates:
                src_img = candidates[0]
            else:
                print(f"  WARNING: Image not found: {file_name}")
                stats["skipped_images"] += 1
                continue

        # Copy/symlink image to split directory
        dst_img = data_dir / "images" / split / file_name
        if not dst_img.exists():
            if args.copy:
                shutil.copy2(str(src_img), str(dst_img))
            else:
                dst_img.symlink_to(src_img.resolve())

        # Write YOLO label file
        label_lines = []
        for ann in anns_by_image.get(img_id, []):
            coco_cat_id = ann["category_id"]
            yolo_cls = coco_id_to_yolo_idx[coco_cat_id]

            # COCO bbox: [x_min, y_min, width, height] in pixels
            bx, by, bw, bh = ann["bbox"]

            # Convert to YOLO: [x_center, y_center, width, height] normalized 0-1
            x_center = (bx + bw / 2) / img_w
            y_center = (by + bh / 2) / img_h
            w_norm = bw / img_w
            h_norm = bh / img_h

            # Clamp to [0, 1]
            x_center = max(0.0, min(1.0, x_center))
            y_center = max(0.0, min(1.0, y_center))
            w_norm = max(0.0, min(1.0, w_norm))
            h_norm = max(0.0, min(1.0, h_norm))

            # Skip degenerate boxes
            if w_norm < 1e-6 or h_norm < 1e-6:
                continue

            label_lines.append(f"{yolo_cls} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")
            stats["total_anns"] += 1

        label_path = data_dir / "labels" / split / f"{stem}.txt"
        with open(label_path, "w") as f:
            f.write("\n".join(label_lines))
            if label_lines:
                f.write("\n")

        stats[split] += 1

    print(f"\nConversion complete:")
    print(f"  Train images: {stats['train']}")
    print(f"  Val images:   {stats['val']}")
    print(f"  Total annotations converted: {stats['total_anns']}")
    if stats["skipped_images"]:
        print(f"  Skipped (missing): {stats['skipped_images']}")

    # -----------------------------------------------------------------------
    # Save category_map.json (yolo_index → coco_category_id)
    # -----------------------------------------------------------------------
    cat_map_path = base_dir / "category_map.json"
    with open(cat_map_path, "w") as f:
        json.dump(yolo_idx_to_coco_id, f)
    print(f"\nSaved category map: {cat_map_path}")
    print(f"  {len(yolo_idx_to_coco_id)} classes: YOLO[0] → COCO[{yolo_idx_to_coco_id[0]}], ... YOLO[{len(yolo_idx_to_coco_id)-1}] → COCO[{yolo_idx_to_coco_id[-1]}]")

    # -----------------------------------------------------------------------
    # Generate norgesgruppen.yaml dataset config
    # -----------------------------------------------------------------------
    yaml_path = base_dir / "norgesgruppen.yaml"

    # Build YAML manually (no yaml import needed)
    yaml_lines = [
        f"# NorgesGruppen Grocery Detection — YOLOv8 dataset config",
        f"# Auto-generated by convert_coco_to_yolo.py",
        f"",
        f"path: {data_dir.resolve()}",
        f"train: images/train",
        f"val: images/val",
        f"",
        f"# {len(class_names)} product categories",
        f"nc: {len(class_names)}",
        f"names:",
    ]
    for idx in range(len(class_names)):
        # Escape quotes in category names
        name = class_names[idx].replace("'", "\\'").replace('"', '\\"')
        yaml_lines.append(f"  {idx}: '{name}'")

    with open(yaml_path, "w") as f:
        f.write("\n".join(yaml_lines) + "\n")
    print(f"Saved dataset YAML: {yaml_path}")

    print("\nDone! Next steps:")
    print("  1. Verify images are in data/images/ (or download the dataset first)")
    print("  2. Run: python train.py")


if __name__ == "__main__":
    main()
