#!/usr/bin/env python3
"""
Split NorgesGruppen COCO dataset into train/val and convert to YOLO format.

Creates:
  data/images/train/  data/images/val/   (symlinks to originals)
  data/labels/train/  data/labels/val/   (YOLO .txt files)
  norgesgruppen.yaml                     (ultralytics dataset config)

YOLO format: class_id x_center y_center width height (all normalized 0-1)
"""

import json
import random
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/data")
PROJECT_DIR = Path("/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen")
SPLIT_RATIO = 0.9  # 90% train, 10% val
SEED = 42


def coco_to_yolo_bbox(bbox, img_w, img_h):
    """Convert COCO [x, y, w, h] to YOLO [x_center, y_center, w, h] normalized."""
    x, y, w, h = bbox
    x_center = (x + w / 2) / img_w
    y_center = (y + h / 2) / img_h
    w_norm = w / img_w
    h_norm = h / img_h
    # Clamp to [0, 1]
    x_center = max(0, min(1, x_center))
    y_center = max(0, min(1, y_center))
    w_norm = max(0, min(1, w_norm))
    h_norm = max(0, min(1, h_norm))
    return x_center, y_center, w_norm, h_norm


def main():
    ann_path = DATA_DIR / "annotations.json"
    if not ann_path.exists():
        print(f"ERROR: {ann_path} not found. Download and extract the dataset first.")
        return

    with open(ann_path) as f:
        coco = json.load(f)

    images = {img["id"]: img for img in coco["images"]}
    categories = {c["id"]: c["name"] for c in coco["categories"]}
    n_categories = len(categories)

    # Group annotations by image
    img_annotations = defaultdict(list)
    for ann in coco["annotations"]:
        img_annotations[ann["image_id"]].append(ann)

    # Find source images directory
    # Dataset extracts to data/train/images/
    img_dir = DATA_DIR / "train" / "images"
    if not img_dir.exists() or not any(img_dir.glob("*.jpg")):
        # Fallback: check other locations
        for candidate in [DATA_DIR / "images", DATA_DIR]:
            jpgs = list(candidate.glob("img_*.jpg"))
            if jpgs:
                img_dir = candidate
                break

    # Build image path lookup (only shelf images, not product reference images)
    all_jpgs = {}
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for p in img_dir.glob(f"img_{ext}"):
            all_jpgs[p.name] = p

    # Stratified split: assign images to train/val
    # Group images by their dominant category for stratification
    img_ids = list(images.keys())
    img_dominant_cat = {}
    for img_id in img_ids:
        anns = img_annotations.get(img_id, [])
        if anns:
            cats = [a["category_id"] for a in anns]
            # Use most common category as stratification key
            from collections import Counter
            img_dominant_cat[img_id] = Counter(cats).most_common(1)[0][0]
        else:
            img_dominant_cat[img_id] = -1

    # Group by dominant category
    cat_images = defaultdict(list)
    for img_id, cat_id in img_dominant_cat.items():
        cat_images[cat_id].append(img_id)

    random.seed(SEED)
    train_ids = set()
    val_ids = set()

    for cat_id, cat_img_ids in cat_images.items():
        random.shuffle(cat_img_ids)
        split_idx = max(1, int(len(cat_img_ids) * SPLIT_RATIO))
        # Ensure at least 1 in val if possible
        if len(cat_img_ids) > 1:
            train_ids.update(cat_img_ids[:split_idx])
            val_ids.update(cat_img_ids[split_idx:])
        else:
            train_ids.update(cat_img_ids)  # Single image goes to train

    print(f"Split: {len(train_ids)} train, {len(val_ids)} val")

    # Create directories
    for split in ["train", "val"]:
        (DATA_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATA_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Process each image
    train_count = 0
    val_count = 0
    missing = 0

    for img_id, img_info in images.items():
        fname = img_info["file_name"]
        # Resolve actual file path
        basename = Path(fname).name
        src_path = all_jpgs.get(basename)
        if src_path is None:
            missing += 1
            continue

        split = "train" if img_id in train_ids else "val"
        img_w = img_info["width"]
        img_h = img_info["height"]

        # Symlink image
        dst_img = DATA_DIR / "images" / split / basename
        if not dst_img.exists():
            dst_img.symlink_to(src_path.resolve())

        # Write YOLO label file
        label_name = basename.replace(".jpg", ".txt").replace(".jpeg", ".txt").replace(".png", ".txt")
        dst_label = DATA_DIR / "labels" / split / label_name
        anns = img_annotations.get(img_id, [])

        with open(dst_label, "w") as f:
            for ann in anns:
                cat_id = ann["category_id"]
                xc, yc, wn, hn = coco_to_yolo_bbox(ann["bbox"], img_w, img_h)
                f.write(f"{cat_id} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}\n")

        if split == "train":
            train_count += 1
        else:
            val_count += 1

    print(f"Created: {train_count} train, {val_count} val images/labels")
    if missing:
        print(f"WARNING: {missing} images not found in {img_dir}")

    # Generate ultralytics YAML
    cat_names = [categories.get(i, f"class_{i}") for i in range(n_categories)]
    yaml_path = PROJECT_DIR / "norgesgruppen.yaml"

    yaml_lines = [
        f"path: {DATA_DIR}",
        "train: images/train",
        "val: images/val",
        f"nc: {n_categories}",
        "names:",
    ]
    for i, name in enumerate(cat_names):
        # Escape quotes in names
        safe_name = name.replace("'", "''").replace('"', '\\"')
        yaml_lines.append(f"  {i}: '{safe_name}'")

    yaml_path.write_text("\n".join(yaml_lines) + "\n")
    print(f"YAML config saved to {yaml_path}")

    # Also save COCO split annotations for pycocotools evaluation
    for split, split_ids in [("train", train_ids), ("val", val_ids)]:
        split_coco = {
            "images": [img for img in coco["images"] if img["id"] in split_ids],
            "annotations": [ann for ann in coco["annotations"] if ann["image_id"] in split_ids],
            "categories": coco["categories"],
        }
        split_path = DATA_DIR / f"annotations_{split}.json"
        with open(split_path, "w") as f:
            json.dump(split_coco, f)
        print(f"COCO {split} annotations: {len(split_coco['images'])} images, {len(split_coco['annotations'])} annotations -> {split_path}")


if __name__ == "__main__":
    main()
