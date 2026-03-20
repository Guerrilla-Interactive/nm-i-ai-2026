# YOLOv8 Strategy for NorgesGruppen Object Detection

**Competition constraints:** 356 product categories, ~248 training images (~22,700 annotations), NVIDIA L4 24GB GPU, max 420MB weights, 300s inference timeout.

---

## 1. Model Variant Selection (Size vs 420MB Limit)

All YOLOv8 variants fit well under the 420MB weight limit:

| Variant | Params (M) | Approx .pt Size | mAP (COCO val) | A100 TensorRT Speed | Under 420MB? |
|---------|-----------|-----------------|----------------|---------------------|--------------|
| YOLOv8n | 3.2M | ~6.5 MB | 37.3 | 0.99 ms | Yes |
| YOLOv8s | 11.2M | ~22 MB | 44.9 | 1.20 ms | Yes |
| YOLOv8m | 25.9M | ~52 MB | 50.2 | 1.83 ms | Yes |
| YOLOv8l | 43.7M | ~87 MB | 52.9 | 2.39 ms | Yes |
| YOLOv8x | 68.2M | ~136 MB | 53.9 | 3.53 ms | Yes |

**Note:** .pt file sizes are approximately 2x the parameter count in MB (FP32, 4 bytes per param, plus optimizer state and metadata). After fine-tuning on 356 classes the output head grows slightly but all variants remain well under 420MB. Even an ensemble of two models would fit.

**Recommendation:** Start with **YOLOv8m** or **YOLOv8l** — best accuracy-speed tradeoff. YOLOv8x is viable too if inference budget allows.

---

## 2. Transfer Learning: COCO Pretrained Weights

### Strategy
```python
from ultralytics import YOLO
model = YOLO('yolov8m.pt')  # COCO pretrained
model.train(data='norgesgruppen.yaml', epochs=300, imgsz=640)
```

The pretrained backbone learns general visual features (edges, textures, shapes, spatial relationships) that transfer well to grocery products. Only the detection head needs to learn the new 356-class taxonomy.

### COCO Classes That Overlap with Grocery Products

COCO has 80 classes. Relevant grocery overlaps:
- **Direct food items:** banana, apple, orange, carrot, broccoli, sandwich, hot dog, pizza, donut, cake
- **Containers:** bottle, cup, bowl, wine glass
- **Utensils:** fork, knife, spoon

**Impact:** The pretrained backbone already understands produce shapes, packaged goods, and container forms. This is a strong foundation for grocery detection.

### Fine-tuning Tips for 356 Classes with Few Images
- **Do NOT freeze the backbone** — with only ~248 images, unfreezing allows the model to adapt features to grocery-specific patterns
- Use a **lower initial learning rate** (lr0=0.001 instead of 0.01) to preserve pretrained features
- Train for **200-300 epochs** with early stopping (patience=50)
- Use **imgsz=640** (default) or **imgsz=1280** if images have many small products

---

## 3. Data Augmentation (Critical for Small Datasets)

### Default Ultralytics Augmentation Config

```yaml
# Recommended augmentation settings for small grocery dataset
hsv_h: 0.015       # Hue shift (default)
hsv_s: 0.7         # Saturation (default)
hsv_v: 0.4         # Brightness (default)
degrees: 10.0      # Slight rotation (default 0.0, increase for shelf angles)
translate: 0.2     # Translation (default 0.1, increase slightly)
scale: 0.9         # Scale variation (default 0.5, increase for size diversity)
shear: 2.0         # Slight shear (default 0.0)
perspective: 0.0   # Keep 0 for shelf-mounted cameras
flipud: 0.0        # No vertical flip (products have orientation)
fliplr: 0.5        # Horizontal flip (default, fine for most products)
mosaic: 1.0        # CRITICAL: combines 4 images (default ON)
mixup: 0.15        # Blend images (default 0.0, enable for small datasets)
copy_paste: 0.1    # Copy objects between images (default 0.0, enable)
close_mosaic: 10   # Disable mosaic last 10 epochs for fine-tuning
```

### Mosaic Augmentation (Default ON)
- Combines 4 training images into one, effectively 4x the diversity
- Especially valuable with only 248 images — every batch sees novel combinations
- Forces model to detect objects at various positions and scales
- **Keep at 1.0** (always on) but use `close_mosaic=10` to disable in final epochs

### MixUp Augmentation
- Blends two images with alpha blending
- Helps regularize with small datasets
- Set `mixup=0.1` to `0.2` — too much can confuse with 356 fine-grained classes

### Copy-Paste Augmentation
- Copies object instances from one image to another
- **Requires segmentation masks** — if only bounding boxes are available, this won't work
- Set `copy_paste=0.1` if masks are available

### Albumentations Integration
```python
import albumentations as A

# Custom augmentations passed via 'augmentations' parameter
augmentations = [
    A.CLAHE(clip_limit=2.0, p=0.3),              # Contrast enhancement
    A.RandomBrightnessContrast(p=0.5),            # Lighting variation
    A.GaussNoise(var_limit=(10, 50), p=0.3),      # Camera noise
    A.Blur(blur_limit=3, p=0.1),                  # Slight blur
    A.MedianBlur(blur_limit=3, p=0.1),            # Shelf glass blur
    A.ToGray(p=0.05),                             # Grayscale robustness
    A.ImageCompression(quality_lower=75, p=0.2),  # JPEG artifacts
]

model.train(data='norgesgruppen.yaml', epochs=300, augmentations=augmentations)
```

### Training Command with All Augmentations
```python
model.train(
    data='norgesgruppen.yaml',
    epochs=300,
    imgsz=640,
    batch=-1,           # Auto batch size
    mosaic=1.0,
    mixup=0.15,
    copy_paste=0.0,     # Enable only if segmentation masks available
    close_mosaic=10,
    scale=0.9,
    degrees=10,
    translate=0.2,
    shear=2.0,
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    patience=50,
    lr0=0.001,
    amp=True,           # Mixed precision
)
```

---

## 4. Pseudo-Labeling / Self-Training Strategy

Ultralytics does **not** natively support semi-supervised learning, but pseudo-labeling can be implemented manually:

### Step-by-Step Approach
1. **Train initial model** on the 248 labeled images
2. **Run inference** on the unlabeled test images
3. **Filter predictions** by confidence threshold (e.g., conf > 0.7)
4. **Convert predictions to YOLO annotation format** (class x_center y_center width height)
5. **Merge** pseudo-labeled data with original training data
6. **Retrain** from the same pretrained weights on the combined dataset
7. **Iterate** 2-3 rounds, increasing confidence threshold each round

### Implementation
```python
from ultralytics import YOLO

# Round 1: Train on labeled data
model = YOLO('yolov8m.pt')
model.train(data='norgesgruppen.yaml', epochs=200)

# Generate pseudo-labels on test set
results = model.predict(source='test_images/', conf=0.7, save_txt=True)

# Merge pseudo-labels with training data (manual step: copy labels to train dir)
# Round 2: Retrain on combined dataset
model2 = YOLO('yolov8m.pt')
model2.train(data='norgesgruppen_combined.yaml', epochs=200)
```

### Caveats
- **Competition rules**: Check if using test images for training (even pseudo-labeled) is allowed
- Risk of **confirmation bias** — high-confidence threshold mitigates this
- Best for classes that are well-represented in training data; rare classes may not generate reliable pseudo-labels

---

## 5. Mixed Precision Training on NVIDIA L4 24GB

### L4 GPU Specs
- 24GB GDDR6 memory
- Ada Lovelace architecture
- FP16 Tensor Core support
- ~120 TFLOPS FP16

### Estimated Batch Sizes (imgsz=640, amp=True)

| Variant | ~VRAM per image | Est. Max Batch | Recommended Batch |
|---------|----------------|----------------|-------------------|
| YOLOv8n | ~0.5 GB | 40+ | 32 |
| YOLOv8s | ~0.8 GB | 24+ | 16 |
| YOLOv8m | ~1.2 GB | 16+ | 16 |
| YOLOv8l | ~1.8 GB | 10-12 | 8 |
| YOLOv8x | ~2.5 GB | 8 | 8 |

**Notes:**
- Use `batch=-1` to let Ultralytics auto-detect optimal batch size
- `amp=True` (default) enables mixed precision — reduces memory ~40% and speeds up training
- Mosaic augmentation effectively increases batch diversity even at smaller batch sizes
- With only 248 images, even batch=8 means seeing all images in ~31 iterations per epoch

### imgsz=1280 (if needed for small product detection)

| Variant | Est. Max Batch | Recommended Batch |
|---------|----------------|-------------------|
| YOLOv8n | 16 | 8-16 |
| YOLOv8s | 8-12 | 8 |
| YOLOv8m | 4-8 | 4 |
| YOLOv8l | 2-4 | 4 |
| YOLOv8x | 2-3 | 2 |

---

## 6. Inference Speed & 300-Second Timeout

### Inference Speed Estimates on NVIDIA L4 (FP16)

| Variant | ~ms/image (L4) | Images in 300s | Safe for 500 test images? |
|---------|----------------|----------------|--------------------------|
| YOLOv8n | ~2-3 ms | ~100,000+ | Yes (massive margin) |
| YOLOv8s | ~3-5 ms | ~60,000+ | Yes (massive margin) |
| YOLOv8m | ~5-8 ms | ~37,000+ | Yes (massive margin) |
| YOLOv8l | ~8-12 ms | ~25,000+ | Yes (massive margin) |
| YOLOv8x | ~12-18 ms | ~16,000+ | Yes (massive margin) |

**Conclusion:** The 300s timeout is NOT a constraint for any YOLOv8 variant. Even YOLOv8x can process tens of thousands of images in that timeframe. This means we should **optimize for accuracy, not speed**.

### Additional Inference Optimizations (if needed)
- **TensorRT export**: `model.export(format='engine', half=True)` — 2-3x faster
- **Batch inference**: Process multiple images at once
- **Test-Time Augmentation (TTA)**: `model.predict(augment=True)` — slower but more accurate, still well within budget

### Recommendation
Use the **largest model that fits accuracy needs** (YOLOv8l or YOLOv8x). Speed is not a concern. Consider TTA for extra accuracy.

---

## 7. Alternative Models

### YOLO-World (Open-Vocabulary Detection)
- **What:** Detects objects using text prompts instead of fixed classes
- **Strength:** Zero-shot detection — can detect "milk carton", "cereal box" etc. without training
- **Weakness:** Lower accuracy than fine-tuned YOLOv8 on specific classes. With 356 known classes and labeled data, fine-tuning will always win
- **Verdict:** NOT recommended as primary approach. Could be useful for:
  - Generating initial pseudo-labels before any training
  - Detecting categories with zero training examples
  - Fallback for rare classes

### YOLOE (2025, ICCV)
- **What:** Successor to YOLO-World, built on YOLOv10
- **Strength:** +11.4 AP over YOLO-World-S on LVIS, 1.4x faster inference
- **Key feature:** Can be re-parameterized into standard YOLO head with zero overhead after training
- **Verdict:** Worth exploring if YOLO-World approach is considered. Available in ultralytics.

### RT-DETR (Transformer-based)
- **What:** Baidu's real-time detection transformer
- **Strength:** Better at handling occlusion (global attention), marginally higher mAP at large scales
- **Weakness:** Higher VRAM usage (transformer attention is quadratic), larger parameter count, less community support
- **Verdict:** NOT recommended. YOLOv8 is better suited for this competition:
  - More memory-efficient (important for L4 24GB)
  - Better ecosystem (ultralytics, augmentation pipeline)
  - Comparable or better accuracy at similar scales
  - Easier to deploy and optimize

### YOLO11 / YOLOv9 / YOLOv10
- Worth benchmarking YOLO11 (ultralytics latest) as a drop-in replacement
- Same API, potentially better accuracy with same constraints

---

## 8. Recommended Competition Strategy

### Phase 1: Baseline (Day 1)
```python
from ultralytics import YOLO
model = YOLO('yolov8m.pt')
model.train(
    data='norgesgruppen.yaml',
    epochs=200,
    imgsz=640,
    batch=-1,
    amp=True,
    patience=50,
    lr0=0.001,
)
```

### Phase 2: Heavy Augmentation (Day 1-2)
- Enable mosaic=1.0, mixup=0.15, scale=0.9
- Add Albumentations (CLAHE, brightness, noise)
- Increase epochs to 300, use close_mosaic=10

### Phase 3: Scale Up (Day 2)
- Try YOLOv8l or YOLOv8x
- Try imgsz=1280 if products are small in images
- Try YOLO11m/l as alternative backbone

### Phase 4: Pseudo-Labeling (Day 2-3)
- Generate pseudo-labels on test data (if allowed)
- Retrain with augmented dataset
- 2-3 rounds of iterative refinement

### Phase 5: Ensemble & TTA (Final)
- Test-Time Augmentation: `model.predict(augment=True)`
- Ensemble multiple models (e.g., YOLOv8m + YOLOv8l) — combined weights still under 420MB
- Use Weighted Boxes Fusion (WBF) for ensemble post-processing

### Key Settings Summary
```yaml
# norgesgruppen.yaml
path: /path/to/dataset
train: images/train
val: images/val
nc: 356
names: [class0, class1, ..., class355]
```

---

## 9. Critical Tips for 356 Classes / 248 Images

1. **Class imbalance is the main challenge** — with ~22,700 annotations across 356 classes, average ~64 annotations per class. Some classes may have very few examples.
2. **Use class weights** or focal loss to handle imbalance
3. **Validation split**: With only 248 images, use 5-fold cross-validation or a very small val split (10-15%)
4. **Image tiling**: If images are high-resolution shelf photos, tile them into sub-images to increase effective dataset size
5. **Multi-scale training**: Use `scale=0.9` and consider training at both 640 and 1280 resolution
6. **Warmup**: Use default warmup (3 epochs) to stabilize with pretrained weights
7. **Label smoothing**: `label_smoothing=0.1` can help with many similar-looking classes
8. **NMS tuning**: With 356 classes, may need to adjust `iou` threshold and `max_det` parameters

---

*Research compiled 2026-03-19 for NM i AI 2026 competition.*
