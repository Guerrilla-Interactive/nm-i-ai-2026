"""
End-to-end pipeline test for NorgesGruppen object detection submission.

Tests the ENTIRE pipeline using synthetic data:
  1. Generates a dummy ONNX model (YOLOv8 output shape)
  2. Generates category_map.json
  3. Tests submission/run.py inference end-to-end
  4. Validates blocked imports via AST
  5. Tests convert_coco_to_yolo.py with synthetic COCO annotations

Usage:
    python test_e2e.py

No real data or trained models required.
"""
import ast
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

PROJECT_DIR = Path(__file__).parent.resolve()
SYNTHETIC_DIR = PROJECT_DIR / "data" / "synthetic"
SUBMISSION_DIR = PROJECT_DIR / "submission"
NUM_CLASSES = 356
NUM_DETECTIONS = 8400
IMG_W, IMG_H = 2000, 1500
NUM_TEST_IMAGES = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class TestResult:
    def __init__(self):
        self.results = []

    def record(self, name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results.append((name, passed, detail))
        icon = "+" if passed else "x"
        msg = f"  [{icon}] {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)

    def summary(self):
        total = len(self.results)
        passed = sum(1 for _, p, _ in self.results if p)
        failed = total - passed
        print(f"\n{'='*60}")
        if failed == 0:
            print(f"ALL {total} TESTS PASSED")
        else:
            print(f"{passed}/{total} passed, {failed} FAILED:")
            for name, p, detail in self.results:
                if not p:
                    print(f"  FAIL: {name} — {detail}")
        print(f"{'='*60}")
        return failed == 0


# ---------------------------------------------------------------------------
# 1. Generate dummy ONNX model
# ---------------------------------------------------------------------------
def generate_dummy_onnx(output_path: Path) -> bool:
    """Create a minimal ONNX model that outputs (1, 360, 8400) for any (1, 3, 640, 640) input.

    Uses a Constant node (ignores input) + Reshape to produce the right shape.
    Uses the onnx library if available, otherwise falls back to raw protobuf.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate synthetic output data: (1, 360, 8400) with realistic-ish values
    rng = np.random.RandomState(42)
    out_data = np.zeros((1, 4 + NUM_CLASSES, NUM_DETECTIONS), dtype=np.float32)
    # Box coords: reasonable values in 640x640 space
    out_data[0, 0, :] = rng.uniform(50, 590, NUM_DETECTIONS)   # cx
    out_data[0, 1, :] = rng.uniform(50, 590, NUM_DETECTIONS)   # cy
    out_data[0, 2, :] = rng.uniform(20, 120, NUM_DETECTIONS)   # w
    out_data[0, 3, :] = rng.uniform(20, 120, NUM_DETECTIONS)   # h
    # Class scores: mostly very low
    out_data[0, 4:, :] = rng.randn(NUM_CLASSES, NUM_DETECTIONS).astype(np.float32) * 0.1 - 3.0
    # Sprinkle ~20 confident detections
    for i in range(20):
        cls = i % NUM_CLASSES
        out_data[0, 4 + cls, i] = 0.5 + rng.rand() * 0.5

    try:
        import onnx
        from onnx import helper, TensorProto, numpy_helper

        # Constant node for the output data
        const_tensor = numpy_helper.from_array(out_data, name="const_value")
        const_node = helper.make_node("Constant", inputs=[], outputs=["raw_output"],
                                       value=const_tensor, name="const0")

        # Shape constant for reshape
        shape_data = np.array([1, 4 + NUM_CLASSES, NUM_DETECTIONS], dtype=np.int64)
        shape_tensor = numpy_helper.from_array(shape_data, name="shape_value")
        shape_node = helper.make_node("Constant", inputs=[], outputs=["output_shape"],
                                       value=shape_tensor, name="shape_const")

        # Reshape node
        reshape_node = helper.make_node("Reshape", inputs=["raw_output", "output_shape"],
                                         outputs=["output0"], name="reshape0")

        # Input/output definitions
        input_info = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 640, 640])
        output_info = helper.make_tensor_value_info("output0", TensorProto.FLOAT, [1, 4 + NUM_CLASSES, NUM_DETECTIONS])

        # Build graph and model
        graph = helper.make_graph(
            [const_node, shape_node, reshape_node],
            "dummy_yolo",
            [input_info],
            [output_info],
        )
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
        model.ir_version = 8
        onnx.save(model, str(output_path))

    except ImportError:
        # Fallback: write a minimal valid ONNX file using raw numpy save
        # This won't be a real ONNX model but signals that onnx library is needed
        np.save(str(output_path), out_data)
        return False

    return output_path.exists() and output_path.stat().st_size > 0


# ---------------------------------------------------------------------------
# 2. Generate category_map.json
# ---------------------------------------------------------------------------
def generate_category_map(output_path: Path) -> bool:
    """Generate identity mapping: {"0": 0, "1": 1, ..., "355": 355}."""
    # submission/run.py expects a dict with string keys (calls .items())
    cat_map = {str(i): i for i in range(NUM_CLASSES)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(cat_map, f)
    return output_path.exists()


# ---------------------------------------------------------------------------
# 3. Generate synthetic test images
# ---------------------------------------------------------------------------
def generate_test_images(output_dir: Path, count: int = NUM_TEST_IMAGES) -> list:
    """Create simple colored test images with known filenames."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i in range(1, count + 1):
        filename = f"img_{i:05d}.jpg"
        img = np.random.randint(50, 200, (IMG_H, IMG_W, 3), dtype=np.uint8)
        # Add some rectangles to make it more image-like
        cv2.rectangle(img, (100 * i, 100), (100 * i + 200, 300), (255, 0, 0), 3)
        cv2.rectangle(img, (50, 400 + 50 * i), (350, 600 + 50 * i), (0, 255, 0), 3)
        path = output_dir / filename
        cv2.imwrite(str(path), img)
        paths.append(path)
    return paths


# ---------------------------------------------------------------------------
# 4. Generate synthetic COCO annotations
# ---------------------------------------------------------------------------
def generate_synthetic_coco(output_path: Path, image_paths: list) -> bool:
    """Generate a minimal COCO annotations file for testing convert_coco_to_yolo."""
    categories = [{"id": i, "name": f"product_{i}"} for i in range(NUM_CLASSES)]

    images = []
    annotations = []
    ann_id = 1

    for img_path in image_paths:
        # Extract image_id from filename
        stem = img_path.stem
        digits = "".join(c for c in stem if c.isdigit())
        image_id = int(digits) if digits else hash(stem) % 10**6

        images.append({
            "id": image_id,
            "file_name": img_path.name,
            "width": IMG_W,
            "height": IMG_H,
        })

        # Add 5 random annotations per image
        for j in range(5):
            cat_id = (image_id + j) % NUM_CLASSES
            x = 50 + j * 200
            y = 100 + j * 150
            w = 150
            h = 120
            annotations.append({
                "id": ann_id,
                "image_id": image_id,
                "category_id": cat_id,
                "bbox": [x, y, w, h],
                "area": w * h,
                "iscrowd": 0,
            })
            ann_id += 1

    coco = {
        "images": images,
        "annotations": annotations,
        "categories": categories,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(coco, f, indent=2)
    return output_path.exists()


# ---------------------------------------------------------------------------
# Test: submission/run.py inference
# ---------------------------------------------------------------------------
def test_submission_inference(tr: TestResult, image_paths: list):
    """Test submission/run.py end-to-end with dummy model and images."""
    print("\n--- Test: Submission Inference ---")

    run_py = SUBMISSION_DIR / "run.py"
    if not run_py.exists():
        tr.record("run.py exists", False, f"Not found: {run_py}")
        return

    tr.record("run.py exists", True)

    # Copy dummy model + category_map to submission dir
    dummy_onnx = SYNTHETIC_DIR / "dummy_model.onnx"
    dummy_cat_map = SYNTHETIC_DIR / "category_map.json"
    sub_onnx = SUBMISSION_DIR / "best.onnx"
    sub_cat_map = SUBMISSION_DIR / "category_map.json"

    # Track files we created so we can clean up
    created_files = []

    try:
        shutil.copy2(str(dummy_onnx), str(sub_onnx))
        created_files.append(sub_onnx)
        shutil.copy2(str(dummy_cat_map), str(sub_cat_map))
        created_files.append(sub_cat_map)
        tr.record("Copy model to submission/", True)
    except Exception as e:
        tr.record("Copy model to submission/", False, str(e))
        return

    # Create temp dir for images and output
    with tempfile.TemporaryDirectory(prefix="e2e_imgs_") as tmp_img_dir, \
         tempfile.NamedTemporaryFile(suffix=".json", delete=False, prefix="e2e_out_") as tmp_out:

        tmp_out_path = Path(tmp_out.name)
        tmp_img_path = Path(tmp_img_dir)

        # Copy test images to temp dir
        for p in image_paths:
            shutil.copy2(str(p), str(tmp_img_path / p.name))

        # Run submission/run.py
        cmd = [
            "python3", str(run_py),
            "--input", str(tmp_img_path),
            "--output", str(tmp_out_path),
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                cwd=str(SUBMISSION_DIR),
            )
            tr.record("run.py executes", result.returncode == 0,
                      result.stderr.strip()[:200] if result.returncode != 0 else "")
        except subprocess.TimeoutExpired:
            tr.record("run.py executes", False, "Timed out (60s)")
            return
        except Exception as e:
            tr.record("run.py executes", False, str(e))
            return
        finally:
            # Clean up copied files
            for f in created_files:
                if f.exists():
                    f.unlink()

        if result.returncode != 0:
            # Still clean up
            if tmp_out_path.exists():
                tmp_out_path.unlink()
            return

        # Validate output JSON
        try:
            with open(tmp_out_path, "r") as f:
                predictions = json.load(f)
            tr.record("Output is valid JSON", True, f"{len(predictions)} detections")
        except (json.JSONDecodeError, Exception) as e:
            tr.record("Output is valid JSON", False, str(e))
            if tmp_out_path.exists():
                tmp_out_path.unlink()
            return

        # Validate it's a list
        tr.record("Output is a list", isinstance(predictions, list))

        if not isinstance(predictions, list) or len(predictions) == 0:
            tr.record("Has detections", False, "Empty or not a list")
            if tmp_out_path.exists():
                tmp_out_path.unlink()
            return

        tr.record("Has detections", True, f"{len(predictions)} total")

        # Validate each prediction
        expected_image_ids = set()
        for p in image_paths:
            stem = p.stem
            digits = "".join(c for c in stem if c.isdigit())
            if digits:
                expected_image_ids.add(int(digits))

        all_valid = True
        seen_image_ids = set()
        errors = []

        for i, pred in enumerate(predictions):
            # Check required fields
            for field in ["image_id", "category_id", "bbox", "score"]:
                if field not in pred:
                    errors.append(f"Detection {i}: missing '{field}'")
                    all_valid = False

            if not all_valid:
                break

            # image_id
            if not isinstance(pred["image_id"], int):
                errors.append(f"Detection {i}: image_id not int: {type(pred['image_id'])}")
                all_valid = False
            else:
                seen_image_ids.add(pred["image_id"])

            # category_id
            if not isinstance(pred["category_id"], int):
                errors.append(f"Detection {i}: category_id not int")
                all_valid = False
            elif pred["category_id"] < 0 or pred["category_id"] >= NUM_CLASSES:
                errors.append(f"Detection {i}: category_id {pred['category_id']} out of range [0, {NUM_CLASSES})")
                all_valid = False

            # bbox
            bbox = pred.get("bbox", [])
            if not isinstance(bbox, list) or len(bbox) != 4:
                errors.append(f"Detection {i}: bbox not a list of 4: {bbox}")
                all_valid = False
            else:
                x, y, w, h = bbox
                if not all(isinstance(v, (int, float)) for v in [x, y, w, h]):
                    errors.append(f"Detection {i}: bbox contains non-numeric values")
                    all_valid = False
                elif w <= 0 or h <= 0:
                    errors.append(f"Detection {i}: bbox has non-positive w/h: {bbox}")
                    all_valid = False
                elif x < -1 or y < -1:
                    errors.append(f"Detection {i}: bbox has negative x/y: {bbox}")
                    all_valid = False

            # score
            score = pred.get("score", -1)
            if not isinstance(score, (int, float)):
                errors.append(f"Detection {i}: score not numeric")
                all_valid = False
            elif score < 0 or score > 1.01:
                errors.append(f"Detection {i}: score {score} out of [0, 1]")
                all_valid = False

            if len(errors) >= 5:
                break

        detail = errors[0] if errors else ""
        tr.record("Prediction fields valid", all_valid, detail)

        # Check image_ids match input
        ids_match = seen_image_ids.issubset(expected_image_ids)
        tr.record("image_ids match filenames", ids_match,
                  f"expected {expected_image_ids}, got {seen_image_ids}" if not ids_match else "")

        # Clean up temp output
        if tmp_out_path.exists():
            tmp_out_path.unlink()


# ---------------------------------------------------------------------------
# Test: blocked imports via AST
# ---------------------------------------------------------------------------
def test_blocked_imports(tr: TestResult):
    """Validate submission/run.py for blocked imports using AST parsing."""
    print("\n--- Test: Blocked Import Validation ---")

    run_py = SUBMISSION_DIR / "run.py"
    if not run_py.exists():
        tr.record("run.py exists for import check", False)
        return

    blocked_modules = {
        "os", "sys", "subprocess", "socket", "ctypes", "builtins",
        "importlib", "pickle", "marshal", "shelve", "shutil", "yaml",
        "requests", "urllib", "http", "http.client",
        "multiprocessing", "threading", "signal", "gc",
        "code", "codeop", "pty",
    }
    blocked_calls = {"eval", "exec", "compile", "__import__"}

    source = run_py.read_text()
    try:
        tree = ast.parse(source)
        tr.record("run.py parses as valid Python", True)
    except SyntaxError as e:
        tr.record("run.py parses as valid Python", False, str(e))
        return

    issues = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in blocked_modules or alias.name in blocked_modules:
                    issues.append(f"Line {node.lineno}: import {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top in blocked_modules or node.module in blocked_modules:
                    issues.append(f"Line {node.lineno}: from {node.module} import ...")

        elif isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name in blocked_calls:
                issues.append(f"Line {node.lineno}: {func_name}()")

    tr.record("No blocked imports", len(issues) == 0,
              "; ".join(issues[:3]) if issues else "")

    # Also run validate_submission.py if it exists
    validator = PROJECT_DIR / "validate_submission.py"
    if validator.exists():
        try:
            result = subprocess.run(
                ["python3", str(validator), "--file", str(run_py)],
                capture_output=True, text=True, timeout=10,
            )
            tr.record("validate_submission.py passes", result.returncode == 0,
                      result.stdout.strip().split("\n")[-1] if result.returncode != 0 else "")
        except Exception as e:
            tr.record("validate_submission.py passes", False, str(e))


# ---------------------------------------------------------------------------
# Test: convert_coco_to_yolo.py
# ---------------------------------------------------------------------------
def test_coco_converter(tr: TestResult, image_paths: list):
    """Test convert_coco_to_yolo.py with synthetic COCO annotations."""
    print("\n--- Test: COCO to YOLO Converter ---")

    converter = PROJECT_DIR / "convert_coco_to_yolo.py"
    if not converter.exists():
        tr.record("convert_coco_to_yolo.py exists", False)
        return

    tr.record("convert_coco_to_yolo.py exists", True)

    # Use synthetic annotations
    annotations_path = SYNTHETIC_DIR / "annotations.json"
    if not annotations_path.exists():
        tr.record("Synthetic annotations exist", False, "Generating inline")
        generate_synthetic_coco(annotations_path, image_paths)

    tr.record("Synthetic annotations exist", annotations_path.exists())

    # Create a temp working directory to avoid polluting project
    with tempfile.TemporaryDirectory(prefix="e2e_coco_") as tmpdir:
        tmpdir = Path(tmpdir)

        # Copy images to temp images dir
        tmp_images = tmpdir / "images"
        tmp_images.mkdir()
        for p in image_paths:
            shutil.copy2(str(p), str(tmp_images / p.name))

        # Copy annotations
        tmp_ann = tmpdir / "annotations.json"
        shutil.copy2(str(annotations_path), str(tmp_ann))

        # Run converter
        cmd = [
            "python3", str(converter),
            "--annotations", str(tmp_ann),
            "--images-dir", str(tmp_images),
            "--val-ratio", "0.33",
            "--seed", "42",
            "--copy",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=str(PROJECT_DIR),
            )
            tr.record("Converter runs successfully", result.returncode == 0,
                      result.stderr.strip()[:200] if result.returncode != 0 else "")
        except Exception as e:
            tr.record("Converter runs successfully", False, str(e))
            return

        if result.returncode != 0:
            print(f"  STDOUT: {result.stdout[:500]}")
            print(f"  STDERR: {result.stderr[:500]}")
            return

        # The converter writes to PROJECT_DIR/data/labels/ and PROJECT_DIR/category_map.json
        # Check for label files
        labels_dir = PROJECT_DIR / "data" / "labels"
        train_labels = list((labels_dir / "train").glob("*.txt")) if (labels_dir / "train").exists() else []
        val_labels = list((labels_dir / "val").glob("*.txt")) if (labels_dir / "val").exists() else []
        all_labels = train_labels + val_labels

        tr.record("Label files created", len(all_labels) > 0,
                  f"{len(train_labels)} train + {len(val_labels)} val")

        if not all_labels:
            return

        # Validate label format
        all_valid = True
        error_detail = ""
        for label_file in all_labels:
            text = label_file.read_text().strip()
            if not text:
                continue  # Empty labels are valid (images with no annotations)
            for line_num, line in enumerate(text.splitlines(), 1):
                parts = line.strip().split()
                if len(parts) != 5:
                    error_detail = f"{label_file.name}:{line_num}: expected 5 fields, got {len(parts)}"
                    all_valid = False
                    break
                try:
                    cls_id = int(parts[0])
                    x_center, y_center, w, h = [float(v) for v in parts[1:]]
                except ValueError:
                    error_detail = f"{label_file.name}:{line_num}: non-numeric value"
                    all_valid = False
                    break

                if cls_id < 0 or cls_id >= NUM_CLASSES:
                    error_detail = f"{label_file.name}:{line_num}: class_id {cls_id} out of range"
                    all_valid = False
                    break

                for name, val in [("x_center", x_center), ("y_center", y_center), ("w", w), ("h", h)]:
                    if val < 0.0 or val > 1.0:
                        error_detail = f"{label_file.name}:{line_num}: {name}={val} not in [0,1]"
                        all_valid = False
                        break

                if not all_valid:
                    break
            if not all_valid:
                break

        tr.record("Label format valid (cls xcyc wh normalized)", all_valid, error_detail)

        # Check category_map.json was created
        cat_map_path = PROJECT_DIR / "category_map.json"
        cat_map_exists = cat_map_path.exists()
        tr.record("category_map.json created", cat_map_exists)

        if cat_map_exists:
            with open(cat_map_path, "r") as f:
                cat_map = json.load(f)
            tr.record("category_map has correct length",
                      len(cat_map) == NUM_CLASSES,
                      f"got {len(cat_map)}, expected {NUM_CLASSES}")

        # Check norgesgruppen.yaml was created
        yaml_path = PROJECT_DIR / "norgesgruppen.yaml"
        tr.record("norgesgruppen.yaml created", yaml_path.exists())

        # Clean up converter output (labels, images split dirs, yaml, category_map)
        # Only clean synthetic split dirs, not real data
        for split in ["train", "val"]:
            img_split = PROJECT_DIR / "data" / "images" / split
            lbl_split = labels_dir / split
            if img_split.exists():
                shutil.rmtree(str(img_split), ignore_errors=True)
            if lbl_split.exists():
                shutil.rmtree(str(lbl_split), ignore_errors=True)
        # Remove generated yaml/catmap only if they're from our synthetic data
        if yaml_path.exists():
            yaml_text = yaml_path.read_text()
            if "product_0" in yaml_text:  # synthetic category name
                yaml_path.unlink()
        if cat_map_path.exists():
            with open(cat_map_path) as f:
                cm = json.load(f)
            # Only remove if it's the identity map we generated
            if isinstance(cm, list) and len(cm) == NUM_CLASSES and cm[0] == 0:
                cat_map_path.unlink()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    tr = TestResult()

    print("=" * 60)
    print("NorgesGruppen E2E Pipeline Test")
    print("=" * 60)

    # --- Step 1: Generate dummy ONNX model ---
    print("\n--- Setup: Generate Synthetic Data ---")

    dummy_onnx_path = SYNTHETIC_DIR / "dummy_model.onnx"
    onnx_ok = generate_dummy_onnx(dummy_onnx_path)
    tr.record("Dummy ONNX model generated", onnx_ok,
              f"{dummy_onnx_path.stat().st_size / 1024:.1f} KB" if onnx_ok else "")

    # Verify ONNX loads in onnxruntime
    ort_available = False
    if onnx_ok:
        try:
            import onnxruntime as ort
            ort_available = True
            sess = ort.InferenceSession(str(dummy_onnx_path), providers=["CPUExecutionProvider"])
            inp = sess.get_inputs()[0]
            out = sess.get_outputs()[0]
            shape_ok = (list(inp.shape) == [1, 3, 640, 640] and
                        out.shape[1] == 4 + NUM_CLASSES)
            tr.record("ONNX loads in onnxruntime", True,
                      f"in={inp.shape} out={out.shape}")
            tr.record("ONNX shapes correct", shape_ok,
                      f"expected [1,3,640,640]->[1,360,8400], got {inp.shape}->{out.shape}")
        except ImportError:
            tr.record("ONNX loads in onnxruntime", True, "SKIPPED (onnxruntime not installed)")
        except Exception as e:
            tr.record("ONNX loads in onnxruntime", False, str(e))

    # --- Step 2: Generate category_map.json ---
    cat_map_path = SYNTHETIC_DIR / "category_map.json"
    cat_map_ok = generate_category_map(cat_map_path)
    tr.record("category_map.json generated", cat_map_ok)

    # --- Step 3: Generate test images ---
    image_dir = SYNTHETIC_DIR / "images"
    image_paths = generate_test_images(image_dir, NUM_TEST_IMAGES)
    tr.record("Test images generated", len(image_paths) == NUM_TEST_IMAGES,
              f"{len(image_paths)} images at {IMG_W}x{IMG_H}")

    # --- Step 4: Generate synthetic COCO annotations ---
    ann_path = SYNTHETIC_DIR / "annotations.json"
    ann_ok = generate_synthetic_coco(ann_path, image_paths)
    tr.record("Synthetic COCO annotations generated", ann_ok)

    # --- Run tests ---
    if onnx_ok and ort_available:
        test_submission_inference(tr, image_paths)
    elif onnx_ok:
        print("\n--- Test: Submission Inference ---")
        tr.record("Submission inference", True,
                  "SKIPPED (onnxruntime not installed — run.py requires it)")

    test_blocked_imports(tr)
    test_coco_converter(tr, image_paths)

    # --- Summary ---
    all_passed = tr.summary()

    # Clean up synthetic data dir
    print(f"\nSynthetic data preserved at: {SYNTHETIC_DIR}")

    raise SystemExit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
