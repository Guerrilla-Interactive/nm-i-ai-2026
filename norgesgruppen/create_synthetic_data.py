"""
Generate synthetic training images from product reference images for rare classes.

Pastes product images onto crops from real training images to create
realistic-looking shelf scenes with YOLO labels.
"""

import json
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
CATEGORY_NAMES_FILE = DATA_DIR / "category_names.json"

OUTPUT_IMAGES_DIR = DATA_DIR / "images" / "synthetic"
OUTPUT_LABELS_DIR = DATA_DIR / "labels" / "synthetic"

# Config
RARE_THRESHOLD = 10  # classes with fewer than this many annotations
IMAGES_PER_RARE_CLASS = 8  # synthetic images to generate per rare class
CANVAS_SIZE = (1280, 1280)  # output image size
PRODUCTS_PER_IMAGE = (3, 8)  # range of products to place per synthetic image
SEED = 42


def load_data():
    """Load annotations, metadata, and build mappings."""
    with open(ANNOTATIONS_FILE) as f:
        annotations = json.load(f)

    with open(METADATA_FILE) as f:
        metadata = json.load(f)

    # category name -> id
    cat_name_to_id = {c["name"]: c["id"] for c in annotations["categories"]}

    # Count annotations per category
    ann_counts = Counter(a["category_id"] for a in annotations["annotations"])

    # Build product_code -> category_id mapping via name matching
    product_to_catid = {}
    for product in metadata["products"]:
        name = product["product_name"]
        if name in cat_name_to_id and product["has_images"]:
            product_to_catid[product["product_code"]] = cat_name_to_id[name]

    # Build category_id -> product_code reverse mapping
    catid_to_product = {}
    for pcode, cid in product_to_catid.items():
        catid_to_product[cid] = pcode

    return annotations, ann_counts, catid_to_product, cat_name_to_id


def get_rare_classes(ann_counts, catid_to_product, num_classes=356):
    """Find rare classes that have product images available."""
    rare = []
    for cid in range(num_classes):
        count = ann_counts.get(cid, 0)
        if count < RARE_THRESHOLD and cid in catid_to_product:
            rare.append((cid, count))
    rare.sort(key=lambda x: x[1])
    return rare


def load_product_image(product_code, angle=None):
    """Load a product reference image."""
    product_dir = PRODUCT_IMAGES_DIR / product_code
    if not product_dir.exists():
        return None

    available = [f.stem for f in product_dir.iterdir() if f.suffix in (".jpg", ".png", ".jpeg")]
    if not available:
        return None

    # Prefer front/main for best visibility
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

    # Resize to at least canvas size, then crop
    w, h = bg.size
    scale = max(CANVAS_SIZE[0] / w, CANVAS_SIZE[1] / h) * 1.1
    bg = bg.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Random crop
    w, h = bg.size
    x = random.randint(0, max(0, w - CANVAS_SIZE[0]))
    y = random.randint(0, max(0, h - CANVAS_SIZE[1]))
    bg = bg.crop((x, y, x + CANVAS_SIZE[0], y + CANVAS_SIZE[1]))

    return bg


def augment_product(img):
    """Apply random augmentations to a product image."""
    # Random rotation (-15 to 15 degrees)
    angle = random.uniform(-15, 15)
    img = img.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))

    # Random scale (0.5x to 1.5x)
    scale = random.uniform(0.5, 1.5)
    new_w = max(20, int(img.width * scale))
    new_h = max(20, int(img.height * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Random brightness (0.7 to 1.3)
    rgb = img.convert("RGB")
    enhancer = ImageEnhance.Brightness(rgb)
    rgb = enhancer.enhance(random.uniform(0.7, 1.3))

    # Random contrast (0.8 to 1.2)
    enhancer = ImageEnhance.Contrast(rgb)
    rgb = enhancer.enhance(random.uniform(0.8, 1.2))

    # Random slight blur (simulates shelf distance)
    if random.random() < 0.3:
        rgb = rgb.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 1.5)))

    # Recombine with alpha
    result = rgb.convert("RGBA")
    result.putalpha(img.split()[3])  # preserve original alpha

    return result


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
    canvas.paste(cropped, (x, y), cropped)  # use alpha as mask

    return (x, y, pw, ph)


def bbox_to_yolo(bbox, img_w, img_h):
    """Convert (x, y, w, h) bbox to YOLO format (cx, cy, w, h) normalized."""
    x, y, w, h = bbox
    cx = (x + w / 2) / img_w
    cy = (y + h / 2) / img_h
    nw = w / img_w
    nh = h / img_h
    return cx, cy, nw, nh


def generate_synthetic_image(
    target_class_id,
    target_product_code,
    catid_to_product,
    train_images,
    img_index,
):
    """Generate one synthetic image with the target class + random other products."""
    bg = get_background_crop(train_images)
    canvas = bg.copy()

    labels = []
    placed = []

    # Target product sizes typical for shelf products (relative to 1280px canvas)
    target_size_range = (80, 250)

    # Place the target product (guaranteed)
    product_img = load_product_image(target_product_code, angle=random.choice(["front", "main"]))
    if product_img is None:
        return False

    product_img = augment_product(product_img)

    # Scale to reasonable shelf-product size
    target_h = random.randint(*target_size_range)
    aspect = product_img.width / max(1, product_img.height)
    target_w = max(20, int(target_h * aspect))
    product_img = product_img.resize((target_w, target_h), Image.LANCZOS)

    # Random position
    x = random.randint(0, max(0, CANVAS_SIZE[0] - target_w))
    y = random.randint(0, max(0, CANVAS_SIZE[1] - target_h))

    bbox = place_product_on_canvas(canvas, product_img, x, y)
    if bbox:
        yolo_bbox = bbox_to_yolo(bbox, CANVAS_SIZE[0], CANVAS_SIZE[1])
        labels.append((target_class_id, *yolo_bbox))
        placed.append(bbox)

    # Add random other products to fill the scene
    num_others = random.randint(*PRODUCTS_PER_IMAGE)
    available_products = list(catid_to_product.items())

    for _ in range(num_others):
        other_cid, other_pcode = random.choice(available_products)
        other_img = load_product_image(other_pcode, angle=random.choice(["front", "main", "left", "right"]))
        if other_img is None:
            continue

        other_img = augment_product(other_img)

        other_h = random.randint(*target_size_range)
        aspect = other_img.width / max(1, other_img.height)
        other_w = max(20, int(other_h * aspect))
        other_img = other_img.resize((other_w, other_h), Image.LANCZOS)

        # Try to find non-overlapping position (up to 5 attempts)
        for _ in range(5):
            ox = random.randint(0, max(0, CANVAS_SIZE[0] - other_w))
            oy = random.randint(0, max(0, CANVAS_SIZE[1] - other_h))

            overlap_ok = True
            for px, py, pw, ph in placed:
                ix1 = max(ox, px)
                iy1 = max(oy, py)
                ix2 = min(ox + other_w, px + pw)
                iy2 = min(oy + other_h, py + ph)
                if ix2 > ix1 and iy2 > iy1:
                    inter = (ix2 - ix1) * (iy2 - iy1)
                    area = other_w * other_h
                    if inter / area > 0.3:
                        overlap_ok = False
                        break

            if overlap_ok:
                bbox = place_product_on_canvas(canvas, other_img, ox, oy)
                if bbox:
                    yolo_bbox = bbox_to_yolo(bbox, CANVAS_SIZE[0], CANVAS_SIZE[1])
                    labels.append((other_cid, *yolo_bbox))
                    placed.append(bbox)
                break

    # Save image and label
    img_name = f"synth_{target_class_id:03d}_{img_index:03d}.jpg"
    label_name = f"synth_{target_class_id:03d}_{img_index:03d}.txt"

    canvas.save(OUTPUT_IMAGES_DIR / img_name, quality=92)

    with open(OUTPUT_LABELS_DIR / label_name, "w") as f:
        for class_id, cx, cy, w, h in labels:
            f.write(f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

    return True


def main():
    random.seed(SEED)
    np.random.seed(SEED)

    print("Loading data...")
    annotations, ann_counts, catid_to_product, cat_name_to_id = load_data()

    print(f"Total categories: {len(annotations['categories'])}")
    print(f"Categories with product images: {len(catid_to_product)}")

    rare_classes = get_rare_classes(ann_counts, catid_to_product)
    print(f"Rare classes (<{RARE_THRESHOLD} annotations) with product images: {len(rare_classes)}")

    if not rare_classes:
        print("No rare classes with product images found!")
        return

    # Collect training images for backgrounds
    train_images = [
        str(TRAIN_IMAGES_DIR / f)
        for f in os.listdir(TRAIN_IMAGES_DIR)
        if f.endswith((".jpg", ".jpeg", ".png"))
    ]
    print(f"Training images for backgrounds: {len(train_images)}")

    # Create output directories
    OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_LABELS_DIR.mkdir(parents=True, exist_ok=True)

    # Build reverse mapping for category names
    id_to_name = {c["id"]: c["name"] for c in annotations["categories"]}

    total_generated = 0
    classes_augmented = 0

    print(f"\nGenerating {IMAGES_PER_RARE_CLASS} synthetic images per rare class...")
    print("-" * 70)

    for class_id, ann_count in rare_classes:
        product_code = catid_to_product[class_id]
        class_name = id_to_name.get(class_id, f"class_{class_id}")

        generated = 0
        for i in range(IMAGES_PER_RARE_CLASS):
            success = generate_synthetic_image(
                class_id,
                product_code,
                catid_to_product,
                train_images,
                i,
            )
            if success:
                generated += 1

        if generated > 0:
            classes_augmented += 1
            total_generated += generated
            print(f"  Class {class_id:3d} ({ann_count} ann): {class_name[:50]:50s} -> {generated} images")

    print("-" * 70)
    print(f"\nSummary:")
    print(f"  Classes augmented: {classes_augmented}")
    print(f"  Total synthetic images: {total_generated}")
    print(f"  Output images: {OUTPUT_IMAGES_DIR}")
    print(f"  Output labels: {OUTPUT_LABELS_DIR}")


if __name__ == "__main__":
    main()
