"""
Generate synthetic shelf images and COCO-format annotations for pipeline testing.
"""
import json
from pathlib import Path

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data" / "synthetic"
TRAIN_IMG_DIR = DATA_DIR / "images"
TEST_IMG_DIR = DATA_DIR / "test_images"
ANN_PATH = DATA_DIR / "annotations.json"

IMG_W, IMG_H = 2000, 1500
NUM_TRAIN = 10
NUM_TEST = 5
NUM_CATEGORIES = 356
SHELF_ROWS = 5
PRODUCTS_PER_ROW = 8
MARGIN = 20
SHELF_GAP = 10

np.random.seed(42)


def random_color():
    return tuple(int(c) for c in np.random.randint(40, 240, size=3))


def draw_shelf_image(rng: np.random.RandomState):
    """Draw a synthetic shelf image with grid-laid products. Returns image and bbox list."""
    # Beige/gray shelf background
    bg_color = (200 + rng.randint(-20, 20), 195 + rng.randint(-20, 20), 180 + rng.randint(-20, 20))
    img = np.full((IMG_H, IMG_W, 3), bg_color, dtype=np.uint8)

    # Draw shelf lines
    row_h = (IMG_H - MARGIN * 2) // SHELF_ROWS
    for r in range(SHELF_ROWS + 1):
        y = MARGIN + r * row_h
        cv2.line(img, (0, y), (IMG_W, y), (120, 100, 80), 3)

    bboxes = []
    col_w = (IMG_W - MARGIN * 2) // PRODUCTS_PER_ROW

    for row in range(SHELF_ROWS):
        y_start = MARGIN + row * row_h + SHELF_GAP
        available_h = row_h - SHELF_GAP * 2

        # Vary number of products per row
        n_products = PRODUCTS_PER_ROW + rng.randint(-2, 3)
        n_products = max(3, min(n_products, 12))
        actual_col_w = (IMG_W - MARGIN * 2) // n_products

        for col in range(n_products):
            x_start = MARGIN + col * actual_col_w + SHELF_GAP

            # Random product size with some variation
            pw = actual_col_w - SHELF_GAP * 2 + rng.randint(-15, 15)
            ph = available_h + rng.randint(-40, 10)
            pw = max(30, min(pw, actual_col_w - SHELF_GAP))
            ph = max(30, min(ph, available_h))

            # Small random offset within cell
            x_off = rng.randint(0, max(1, actual_col_w - SHELF_GAP * 2 - pw))
            y_off = rng.randint(0, max(1, available_h - ph))

            x = x_start + x_off
            y = y_start + y_off

            # Clip to image
            x = max(0, min(x, IMG_W - pw - 1))
            y = max(0, min(y, IMG_H - ph - 1))

            # Draw product rectangle
            color = random_color()
            cv2.rectangle(img, (x, y), (x + pw, y + ph), color, -1)

            # Add a darker border
            border = tuple(max(0, c - 40) for c in color)
            cv2.rectangle(img, (x, y), (x + pw, y + ph), border, 2)

            # Add a simple "label" stripe
            label_h = max(10, ph // 5)
            label_y = y + ph - label_h
            label_color = tuple(min(255, c + 60) for c in color)
            cv2.rectangle(img, (x + 3, label_y), (x + pw - 3, y + ph - 3), label_color, -1)

            cat_id = rng.randint(0, NUM_CATEGORIES)
            bboxes.append((x, y, pw, ph, cat_id))

    return img, bboxes


def main():
    TRAIN_IMG_DIR.mkdir(parents=True, exist_ok=True)
    TEST_IMG_DIR.mkdir(parents=True, exist_ok=True)

    rng = np.random.RandomState(42)

    images_meta = []
    annotations = []
    ann_id = 1

    # Generate training images with annotations
    for i in range(1, NUM_TRAIN + 1):
        img, bboxes = draw_shelf_image(rng)
        fname = f"img_{i:05d}.jpg"
        cv2.imwrite(str(TRAIN_IMG_DIR / fname), img)

        images_meta.append({
            "id": i,
            "file_name": fname,
            "width": IMG_W,
            "height": IMG_H,
        })

        for (x, y, w, h, cat_id) in bboxes:
            annotations.append({
                "id": ann_id,
                "image_id": i,
                "category_id": int(cat_id),
                "bbox": [int(x), int(y), int(w), int(h)],
                "area": int(w * h),
                "iscrowd": 0,
            })
            ann_id += 1

    # Generate test images (no annotations)
    for i in range(NUM_TRAIN + 1, NUM_TRAIN + NUM_TEST + 1):
        img, _ = draw_shelf_image(rng)
        fname = f"img_{i:05d}.jpg"
        cv2.imwrite(str(TEST_IMG_DIR / fname), img)

    # Build categories list
    categories = [
        {"id": c, "name": f"product_{c}", "supercategory": "product"}
        for c in range(NUM_CATEGORIES)
    ]

    coco = {
        "images": images_meta,
        "categories": categories,
        "annotations": annotations,
    }

    with open(str(ANN_PATH), "w") as f:
        json.dump(coco, f, indent=2)

    print(f"Created {NUM_TRAIN} training images in {TRAIN_IMG_DIR}")
    print(f"Created {NUM_TEST} test images in {TEST_IMG_DIR}")
    print(f"Created {len(annotations)} annotations across {NUM_TRAIN} images")
    print(f"Annotations saved to {ANN_PATH}")


if __name__ == "__main__":
    main()
