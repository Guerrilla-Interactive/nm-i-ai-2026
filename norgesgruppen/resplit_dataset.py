"""
Re-split the NorgesGruppen dataset so all 356 categories appear in both train and val.
Uses a greedy stratified approach: rare categories get val coverage first.
"""
import json
from pathlib import Path
from collections import defaultdict, Counter
import random

random.seed(42)

DATA = Path("/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen/data")
SRC_IMG_DIR = DATA / "train" / "images"
ANN_PATH = DATA / "annotations.json"

# Output paths
OUT_TRAIN_IMG = DATA / "images" / "train"
OUT_VAL_IMG = DATA / "images" / "val"
OUT_TRAIN_LBL = DATA / "labels" / "train"
OUT_VAL_LBL = DATA / "labels" / "val"

VAL_RATIO = 0.15  # Target 85/15 split


def main():
    with open(str(ANN_PATH)) as f:
        coco = json.load(f)

    images = {im["id"]: im for im in coco["images"]}
    categories = {c["id"]: c["name"] for c in coco["categories"]}
    num_cats = len(categories)

    # Build mappings
    img_to_anns = defaultdict(list)
    img_to_cats = defaultdict(set)
    cat_to_imgs = defaultdict(set)

    for ann in coco["annotations"]:
        img_id = ann["image_id"]
        cat_id = ann["category_id"]
        img_to_anns[img_id].append(ann)
        img_to_cats[img_id].add(cat_id)
        cat_to_imgs[cat_id].add(img_id)

    all_img_ids = sorted(images.keys())
    print(f"Total images: {len(all_img_ids)}")
    print(f"Total annotations: {len(coco['annotations'])}")
    print(f"Total categories: {num_cats}")

    # --- Greedy stratified split ---
    # Goal: every category appears in BOTH train and val.
    # Categories with only 1 image: that image goes in BOTH splits (duplicated).

    single_img_cats = {c for c, imgs in cat_to_imgs.items() if len(imgs) == 1}
    dual_imgs = set()  # Images that must appear in BOTH splits
    for cat_id in single_img_cats:
        dual_imgs.update(cat_to_imgs[cat_id])

    print(f"\nCategories with only 1 image: {len(single_img_cats)}")
    print(f"Images duplicated in both splits: {len(dual_imgs)}")

    # Splittable images get assigned to exactly one split
    splittable = set(all_img_ids) - dual_imgs

    # Phase 1: Greedily assign val images to cover all categories
    val_exclusive = set()
    cats_in_val = set()
    for img_id in dual_imgs:
        cats_in_val.update(img_to_cats[img_id])

    cats_by_rarity = sorted(cat_to_imgs.keys(), key=lambda c: len(cat_to_imgs[c]))
    for cat_id in cats_by_rarity:
        if cat_id in cats_in_val:
            continue
        candidates = cat_to_imgs[cat_id] & splittable - val_exclusive
        if not candidates:
            candidates = cat_to_imgs[cat_id] & splittable
        if not candidates:
            continue
        best = max(candidates, key=lambda i: len(img_to_cats[i] - cats_in_val))
        val_exclusive.add(best)
        cats_in_val.update(img_to_cats[best])

    # Phase 2: Ensure all categories also in train
    train_exclusive = splittable - val_exclusive
    cats_in_train = set()
    for img_id in dual_imgs | train_exclusive:
        cats_in_train.update(img_to_cats[img_id])

    # Iteratively fix: move val-exclusive images to train if needed
    for _ in range(10):  # max iterations
        missing_in_train = set(categories.keys()) - cats_in_train
        if not missing_in_train:
            break
        for cat_id in sorted(missing_in_train, key=lambda c: len(cat_to_imgs[c])):
            # Find an image in val_exclusive that has this cat
            candidates = cat_to_imgs[cat_id] & val_exclusive
            if not candidates:
                continue
            # Move the one that covers the least unique val cats
            move = min(candidates, key=lambda i: len(img_to_cats[i] - cats_in_train))
            val_exclusive.discard(move)
            train_exclusive.add(move)
            cats_in_train.update(img_to_cats[move])
            # Re-check if moved cat still covered in val
        # Recheck val coverage and re-add if needed
        cats_in_val = set()
        for img_id in dual_imgs | val_exclusive:
            cats_in_val.update(img_to_cats[img_id])
        missing_in_val = set(categories.keys()) - cats_in_val
        for cat_id in sorted(missing_in_val, key=lambda c: len(cat_to_imgs[c])):
            candidates = cat_to_imgs[cat_id] & train_exclusive
            if not candidates:
                continue
            best = max(candidates, key=lambda i: len(img_to_cats[i] - cats_in_val))
            train_exclusive.discard(best)
            val_exclusive.add(best)
            cats_in_val.update(img_to_cats[best])
        # Update train coverage
        cats_in_train = set()
        for img_id in dual_imgs | train_exclusive:
            cats_in_train.update(img_to_cats[img_id])

    # Phase 3: Adjust val size toward target ratio
    target_val_count = int(len(all_img_ids) * VAL_RATIO)
    current_val = len(dual_imgs) + len(val_exclusive)

    if current_val < target_val_count:
        # Move some train_exclusive to val
        movable = sorted(train_exclusive)
        random.shuffle(movable)
        for img_id in movable:
            if current_val >= target_val_count:
                break
            # Only move if it doesn't break train coverage
            test_train = (dual_imgs | train_exclusive) - {img_id}
            test_train_cats = set()
            for tid in test_train:
                test_train_cats.update(img_to_cats[tid])
            if len(test_train_cats) == len(categories):
                train_exclusive.discard(img_id)
                val_exclusive.add(img_id)
                current_val += 1

    # Build final sets
    train_ids = dual_imgs | train_exclusive
    val_ids = dual_imgs | val_exclusive

    # --- Verify coverage ---
    train_cats = set()
    val_cats = set()
    train_ann_count = 0
    val_ann_count = 0

    for img_id in train_ids:
        train_cats.update(img_to_cats[img_id])
        train_ann_count += len(img_to_anns[img_id])
    for img_id in val_ids:
        val_cats.update(img_to_cats[img_id])
        val_ann_count += len(img_to_anns[img_id])

    train_only = train_cats - val_cats
    val_only = val_cats - train_cats
    both = train_cats & val_cats

    print(f"\n=== SPLIT STATISTICS ===")
    print(f"Train: {len(train_ids)} images, {train_ann_count} annotations")
    print(f"Val:   {len(val_ids)} images, {val_ann_count} annotations")
    print(f"Split: {len(train_ids)/len(all_img_ids)*100:.1f}% / {len(val_ids)/len(all_img_ids)*100:.1f}%")
    print(f"\nCategories in train: {len(train_cats)}")
    print(f"Categories in val:   {len(val_cats)}")
    print(f"Categories in both:  {len(both)}")
    print(f"Train-only: {len(train_only)}")
    print(f"Val-only:   {len(val_only)}")

    if train_only:
        print(f"\nWARNING: Train-only categories: {sorted(train_only)[:20]}")
    if val_only:
        print(f"\nWARNING: Val-only categories: {sorted(val_only)[:20]}")

    # --- Create directories and clean old files ---
    for d in [OUT_TRAIN_IMG, OUT_VAL_IMG, OUT_TRAIN_LBL, OUT_VAL_LBL]:
        d.mkdir(parents=True, exist_ok=True)
        # Clean old files
        for old_file in d.iterdir():
            old_file.unlink()

    # Symlink images and create YOLO labels
    def write_split(img_ids, img_dir, lbl_dir):
        for img_id in sorted(img_ids):
            im = images[img_id]
            fname = im["file_name"]
            src = SRC_IMG_DIR / fname
            dst = img_dir / fname

            # Symlink image
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            if src.exists():
                dst.symlink_to(src.resolve())
            else:
                # Try jpeg extension
                src_jpeg = src.with_suffix(".jpeg")
                if src_jpeg.exists():
                    dst_symlink = img_dir / src_jpeg.name
                    if dst_symlink.exists() or dst_symlink.is_symlink():
                        dst_symlink.unlink()
                    dst_symlink.symlink_to(src_jpeg.resolve())

            # Write YOLO label
            w_img = im["width"]
            h_img = im["height"]
            label_name = Path(fname).stem + ".txt"
            label_path = lbl_dir / label_name

            lines = []
            for ann in img_to_anns[img_id]:
                cat_id = ann["category_id"]
                bx, by, bw, bh = ann["bbox"]  # COCO: x, y, w, h (top-left)
                # Convert to YOLO: x_center, y_center, w, h (normalized)
                x_center = (bx + bw / 2) / w_img
                y_center = (by + bh / 2) / h_img
                w_norm = bw / w_img
                h_norm = bh / h_img
                # Clip to [0, 1]
                x_center = max(0, min(1, x_center))
                y_center = max(0, min(1, y_center))
                w_norm = max(0, min(1, w_norm))
                h_norm = max(0, min(1, h_norm))
                lines.append(f"{cat_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")

            with open(str(label_path), "w") as f:
                f.write("\n".join(lines) + "\n" if lines else "")

    print(f"\nWriting train split...")
    write_split(train_ids, OUT_TRAIN_IMG, OUT_TRAIN_LBL)
    print(f"Writing val split...")
    write_split(val_ids, OUT_VAL_IMG, OUT_VAL_LBL)

    # --- Write updated annotation JSONs ---
    def make_coco_subset(img_ids):
        subset_images = [images[i] for i in sorted(img_ids)]
        subset_anns = []
        for img_id in sorted(img_ids):
            subset_anns.extend(img_to_anns[img_id])
        return {
            "images": subset_images,
            "annotations": subset_anns,
            "categories": coco["categories"],
        }

    train_coco = make_coco_subset(train_ids)
    val_coco = make_coco_subset(val_ids)

    with open(str(DATA / "annotations_train_stratified.json"), "w") as f:
        json.dump(train_coco, f)
    with open(str(DATA / "annotations_val_stratified.json"), "w") as f:
        json.dump(val_coco, f)

    print(f"\nSaved annotations_train_stratified.json ({len(train_coco['images'])} images)")
    print(f"Saved annotations_val_stratified.json ({len(val_coco['images'])} images)")

    # --- Write YOLO dataset YAML ---
    yaml_content = f"""# NorgesGruppen Object Detection - Stratified Split
path: {DATA.resolve()}
train: images/train
val: images/val

nc: {num_cats}
names:
"""
    for cat_id in sorted(categories.keys()):
        name = categories[cat_id].replace("'", "\\'")
        yaml_content += f"  {cat_id}: '{name}'\n"

    yaml_path = Path("/Users/pelle/Documents/github/nm-i-ai-2026/norgesgruppen") / "norgesgruppen.yaml"
    with open(str(yaml_path), "w") as f:
        f.write(yaml_content)
    print(f"Saved {yaml_path}")

    # --- Final verification ---
    print(f"\n=== VERIFICATION ===")
    train_imgs = list(OUT_TRAIN_IMG.glob("*.jpg")) + list(OUT_TRAIN_IMG.glob("*.jpeg"))
    val_imgs = list(OUT_VAL_IMG.glob("*.jpg")) + list(OUT_VAL_IMG.glob("*.jpeg"))
    train_lbls = list(OUT_TRAIN_LBL.glob("*.txt"))
    val_lbls = list(OUT_VAL_LBL.glob("*.txt"))
    print(f"Train images: {len(train_imgs)}, labels: {len(train_lbls)}")
    print(f"Val images:   {len(val_imgs)}, labels: {len(val_lbls)}")

    # Check a sample label
    sample_lbl = sorted(OUT_TRAIN_LBL.glob("*.txt"))[0]
    with open(str(sample_lbl)) as f:
        sample_lines = f.readlines()
    print(f"\nSample label ({sample_lbl.name}): {len(sample_lines)} objects")
    for line in sample_lines[:3]:
        print(f"  {line.strip()}")

    print("\nDone!")


if __name__ == "__main__":
    main()
