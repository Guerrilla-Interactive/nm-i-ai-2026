"""
Generate synthetic training images from product reference images for rare classes.

Pastes product images onto crops from real training images to create
realistic-looking shelf scenes with YOLO labels.

Improvements over v1:
- Class-balanced: more images for rarer classes (inverse-count weighting)
- Shelf-like grid placement instead of random scatter
- Per-paste color jitter (hue, saturation, brightness, contrast)
- Multiple target instances per image for very rare classes
- CLI with --dry-run, --threshold, --max-images flags
"""

import argparse
import json
import math
import os
import random
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PRODUCT_IMAGES_DIR = DATA_DIR / "product_images"
TRAIN_IMAGES_DIR = DATA_DIR / "images" / "train"
ANNOTATIONS_FILE = DATA_DIR / "annotations.json"
METADATA_FILE = PRODUCT_IMAGES_DIR / "metadata.json"

OUTPUT_IMAGES_DIR = DATA_DIR / "images" / "synthetic"
OUTPUT_LABELS_DIR = DATA_DIR / "labels" / "synthetic"

# Canvas
CANVAS_SIZE = (1280, 1280)
SEED = 42

# Shelf layout constants
SHELF_ROWS = (2, 5)       # number of shelf rows per image
SHELF_Y_JITTER = 10       # pixels of vertical jitter within a row
SHELF_X_GAP = (2, 15)     # horizontal gap between products on a shelf
PRODUCT_H_RANGE = (90, 220)  # product height range in pixels


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate synthetic shelf images for rare classes"
    )
    parser.add_argument(
        "--threshold", type=int, default=10,
        help="Classes with fewer than this many annotations are considered rare (default: 10)"
    )
    parser.add_argument(
        "--max-images", type=int, default=15,
        help="Max synthetic images per class (rarest classes get this many) (default: 15)"
    )
    parser.add_argument(
        "--min-images", type=int, default=4,
        help="Min synthetic images per class (default: 4)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print plan without generating images"
    )
    parser.add_argument(
        "--seed", type=int, default=SEED,
        help="Random seed (default: 42)"
    )
    return parser.parse_args()


def load_data():
    """Load annotations, metadata, and build mappings."""
    with open(ANNOTATIONS_FILE) as f:
        annotations = json.load(f)

    with open(METADATA_FILE) as f:
        metadata = json.load(f)

    cat_name_to_id = {c["name"]: c["id"] for c in annotations["categories"]}
    ann_counts = Counter(a["category_id"] for a in annotations["annotations"])

    # Build product_code -> category_id mapping via name matching
    product_to_catid = {}
    for product in metadata["products"]:
        name = product["product_name"]
        if name in cat_name_to_id and product["has_images"]:
            product_to_catid[product["product_code"]] = cat_name_to_id[name]

    # category_id -> product_code (keep first match)
    catid_to_product = {}
    for pcode, cid in product_to_catid.items():
        if cid not in catid_to_product:
            catid_to_product[cid] = pcode

    return annotations, ann_counts, catid_to_product, cat_name_to_id


def get_rare_classes(ann_counts, catid_to_product, threshold, num_classes=356):
    """Find rare classes that have product images available."""
    rare = []
    for cid in range(num_classes):
        count = ann_counts.get(cid, 0)
        if count < threshold and cid in catid_to_product:
            rare.append((cid, count))
    rare.sort(key=lambda x: x[1])
    return rare


def images_for_class(ann_count, threshold, max_images, min_images):
    """Inverse-count weighting: fewer annotations -> more synthetic images."""
    if ann_count == 0:
        return max_images
    # Linear interpolation: 0 anns -> max_images, threshold anns -> min_images
    frac = ann_count / threshold
    n = max_images - frac * (max_images - min_images)
    return max(min_images, int(round(n)))


def load_product_image(product_code, angle=None):
    """Load a product reference image."""
    product_dir = PRODUCT_IMAGES_DIR / product_code
    if not product_dir.exists():
        return None

    available = [f.stem for f in product_dir.iterdir() if f.suffix in (".jpg", ".png", ".jpeg")]
    if not available:
        return None

    if angle and angle in available:
        chosen = angle
    else:
        preferred = ["front", "main"]
        chosen = None
        for p in preferred:
            if p in available:
                chosen = p
                break
        if chosen is None:
            chosen = random.choice(available)

    for ext in (".jpg", ".png", ".jpeg"):
        img_path = product_dir / f"{chosen}{ext}"
        if img_path.exists():
            try:
                return Image.open(img_path).convert("RGBA")
            except Exception:
                pass

    return None


def get_background_crop(train_images):
    """Get a random crop from a training image to use as background."""
    img_path = random.choice(train_images)
    try:
        bg = Image.open(img_path).convert("RGB")
    except Exception:
        bg = Image.new("RGB", CANVAS_SIZE, color=(200, 195, 185))
        return bg

    w, h = bg.size
    scale = max(CANVAS_SIZE[0] / w, CANVAS_SIZE[1] / h) * 1.1
    bg = bg.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    w, h = bg.size
    x = random.randint(0, max(0, w - CANVAS_SIZE[0]))
    y = random.randint(0, max(0, h - CANVAS_SIZE[1]))
    bg = bg.crop((x, y, x + CANVAS_SIZE[0], y + CANVAS_SIZE[1]))

    return bg


def color_jitter(img):
    """Apply per-paste color jitter: hue, saturation, brightness, contrast."""
    alpha = img.split()[3]
    rgb = img.convert("RGB")

    # Hue shift via HSV
    hsv = np.array(rgb.convert("HSV"))
    hue_shift = random.randint(-15, 15)
    hsv[:, :, 0] = (hsv[:, :, 0].astype(int) + hue_shift) % 256
    rgb = Image.fromarray(hsv, "HSV").convert("RGB")

    # Saturation
    rgb = ImageEnhance.Color(rgb).enhance(random.uniform(0.7, 1.4))

    # Brightness
    rgb = ImageEnhance.Brightness(rgb).enhance(random.uniform(0.65, 1.35))

    # Contrast
    rgb = ImageEnhance.Contrast(rgb).enhance(random.uniform(0.75, 1.25))

    # Optional blur (shelf distance effect)
    if random.random() < 0.25:
        rgb = rgb.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 1.5)))

    result = rgb.convert("RGBA")
    result.putalpha(alpha)
    return result


def augment_product(img):
    """Apply geometric augmentations + per-paste color jitter."""
    # Small rotation (shelf products are mostly upright)
    angle = random.uniform(-5, 5)
    img = img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))

    # Per-paste color jitter
    img = color_jitter(img)

    return img


def compute_shelf_layout(canvas_w, canvas_h):
    """Generate a shelf-like grid: rows of products at consistent y-positions.

    Returns list of (row_y, row_h) for each shelf row.
    """
    num_rows = random.randint(*SHELF_ROWS)
    # Divide canvas into rows with small gaps
    row_gap = random.randint(5, 20)
    usable_h = canvas_h - row_gap * (num_rows + 1)
    row_h = usable_h // num_rows

    rows = []
    y = row_gap
    for _ in range(num_rows):
        rows.append((y, min(row_h, random.randint(*PRODUCT_H_RANGE))))
        y += row_h + row_gap

    return rows


def place_product_on_canvas(canvas, product_img, x, y):
    """Paste product image onto canvas at (x, y), return bounding box."""
    pw, ph = product_img.size

    # Clamp to canvas bounds
    if x + pw > canvas.width:
        pw = canvas.width - x
    if y + ph > canvas.height:
        ph = canvas.height - y
    if pw <= 0 or ph <= 0:
        return None

    cropped = product_img.crop((0, 0, pw, ph))
    canvas.paste(cropped, (x, y), cropped)

    return (x, y, pw, ph)


def bbox_to_yolo(bbox, img_w, img_h):
    """Convert (x, y, w, h) bbox to YOLO format (cx, cy, w, h) normalized."""
    x, y, w, h = bbox
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    nw = w / img_w
    nh = h / img_h
    # Clamp to [0, 1]
    cx = max(0.0, min(1.0, cx))
    cy = max(0.0, min(1.0, cy))
    nw = max(0.0, min(1.0, nw))
    nh = max(0.0, min(1.0, nh))
    return cx, cy, nw, nh


def resize_product_to_height(img, target_h):
    """Resize product image to target height, preserving aspect ratio."""
    aspect = img.width / max(1, img.height)
    target_w = max(20, int(target_h * aspect))
    return img.resize((target_w, target_h), Image.LANCZOS)


def generate_synthetic_image(
    target_class_id,
    target_product_code,
    catid_to_product,
    train_images,
    img_index,
    target_instances=1,
):
    """Generate one synthetic image with shelf-like layout.

    Places target_instances copies of the target class, fills remaining
    shelf slots with random other products.
    """
    bg = get_background_crop(train_images)
    canvas = bg.copy()
    labels = []

    # Generate shelf layout
    shelf_rows = compute_shelf_layout(CANVAS_SIZE[0], CANVAS_SIZE[1])
    available_products = list(catid_to_product.items())

    # Build a pool of (class_id, product_code) to place, ensuring target class appears
    product_pool = []
    for _ in range(target_instances):
        product_pool.append((target_class_id, target_product_code))

    # Fill remaining slots with random products (estimate ~4-7 per row)
    total_slots = sum(random.randint(4, 7) for _ in shelf_rows)
    fill_count = max(0, total_slots - target_instances)
    for _ in range(fill_count):
        cid, pcode = random.choice(available_products)
        product_pool.append((cid, pcode))

    random.shuffle(product_pool)

    # Place products row by row
    pool_idx = 0
    for row_y, row_h in shelf_rows:
        x_cursor = random.randint(5, 30)  # left margin

        while x_cursor < CANVAS_SIZE[0] - 40 and pool_idx < len(product_pool):
            cid, pcode = product_pool[pool_idx]
            pool_idx += 1

            # Load and augment
            angle_choice = random.choice(["front", "main", "front", "front"])
            prod_img = load_product_image(pcode, angle=angle_choice)
            if prod_img is None:
                continue

            prod_img = augment_product(prod_img)

            # Size to fit the shelf row
            product_h = min(row_h, random.randint(*PRODUCT_H_RANGE))
            prod_img = resize_product_to_height(prod_img, product_h)

            # Place at current cursor with small vertical jitter
            y_jitter = random.randint(-SHELF_Y_JITTER, SHELF_Y_JITTER)
            place_y = max(0, row_y + (row_h - product_h) // 2 + y_jitter)

            bbox = place_product_on_canvas(canvas, prod_img, x_cursor, place_y)
            if bbox:
                yolo_bbox = bbox_to_yolo(bbox, CANVAS_SIZE[0], CANVAS_SIZE[1])
                labels.append((cid, *yolo_bbox))

            # Advance cursor
            x_cursor += prod_img.width + random.randint(*SHELF_X_GAP)

    if not labels:
        return False

    # Verify target class is in labels (it should be unless image loading failed)
    has_target = any(l[0] == target_class_id for l in labels)
    if not has_target:
        return False

    # Save image and label
    img_name = f"synth_{target_class_id:03d}_{img_index:03d}.jpg"
    label_name = f"synth_{target_class_id:03d}_{img_index:03d}.txt"

    canvas.save(OUTPUT_IMAGES_DIR / img_name, quality=92)

    with open(OUTPUT_LABELS_DIR / label_name, "w") as f:
        for class_id, cx, cy, w, h in labels:
            f.write(f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

    return True


def main():
    args = parse_args()
    random.seed(args.seed)
    np.random.seed(args.seed)

    print("Loading data...")
    annotations, ann_counts, catid_to_product, cat_name_to_id = load_data()

    print(f"Total categories: {len(annotations['categories'])}")
    print(f"Categories with product images: {len(catid_to_product)}")

    rare_classes = get_rare_classes(ann_counts, catid_to_product, args.threshold)
    print(f"Rare classes (<{args.threshold} annotations) with product images: {len(rare_classes)}")

    if not rare_classes:
        print("No rare classes with product images found!")
        return

    id_to_name = {c["id"]: c["name"] for c in annotations["categories"]}

    # Compute per-class image counts
    plan = []
    total_planned = 0
    for class_id, ann_count in rare_classes:
        n_images = images_for_class(ann_count, args.threshold, args.max_images, args.min_images)
        # Very rare classes get multiple target instances per image
        target_instances = 2 if ann_count <= 2 else 1
        plan.append((class_id, ann_count, n_images, target_instances))
        total_planned += n_images

    # Print plan
    print(f"\nGeneration plan ({total_planned} images total):")
    print(f"  {'CID':>4s}  {'Ann':>4s}  {'Synth':>5s}  {'Inst/img':>8s}  Name")
    print("-" * 80)
    for class_id, ann_count, n_images, t_inst in plan:
        name = id_to_name.get(class_id, f"class_{class_id}")[:50]
        print(f"  {class_id:4d}  {ann_count:4d}  {n_images:5d}  {t_inst:8d}  {name}")
    print("-" * 80)
    print(f"  Total: {total_planned} images for {len(plan)} classes")

    if args.dry_run:
        print("\n[DRY RUN] No images generated.")
        return

    # Collect training images for backgrounds
    train_images = [
        str(TRAIN_IMAGES_DIR / f)
        for f in os.listdir(TRAIN_IMAGES_DIR)
        if f.endswith((".jpg", ".jpeg", ".png"))
    ]
    print(f"\nTraining images for backgrounds: {len(train_images)}")

    OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_LABELS_DIR.mkdir(parents=True, exist_ok=True)

    total_generated = 0
    classes_augmented = 0

    print(f"\nGenerating images...")
    for class_id, ann_count, n_images, target_instances in plan:
        product_code = catid_to_product[class_id]
        class_name = id_to_name.get(class_id, f"class_{class_id}")

        generated = 0
        for i in range(n_images):
            success = generate_synthetic_image(
                class_id,
                product_code,
                catid_to_product,
                train_images,
                i,
                target_instances=target_instances,
            )
            if success:
                generated += 1

        if generated > 0:
            classes_augmented += 1
            total_generated += generated
            print(f"  Class {class_id:3d} ({ann_count:2d} ann): {class_name[:50]:50s} -> {generated} images")

    print("-" * 70)
    print(f"\nSummary:")
    print(f"  Classes augmented: {classes_augmented}")
    print(f"  Total synthetic images: {total_generated}")
    print(f"  Output images: {OUTPUT_IMAGES_DIR}")
    print(f"  Output labels: {OUTPUT_LABELS_DIR}")


if __name__ == "__main__":
    main()
