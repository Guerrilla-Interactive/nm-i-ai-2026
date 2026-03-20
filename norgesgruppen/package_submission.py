"""
Package submission ZIP for NorgesGruppen object detection task.

Collects submission/run.py + model weights + category_map.json into a ZIP.
Validates structure, sizes, and constraints before creating the archive.

Usage:
    python package_submission.py
    python package_submission.py --submission-dir submission --output submission.zip
"""
import argparse
import json
import zipfile
from pathlib import Path

from validate_submission import validate_file

# Submission constraints
MAX_UNCOMPRESSED_SIZE = 420 * 1024 * 1024  # 420 MB
MAX_FILES = 1000
MAX_PY_FILES = 10
MAX_WEIGHT_FILES = 3
ALLOWED_EXTENSIONS = {
    ".py", ".json", ".yaml", ".yml", ".cfg",
    ".pt", ".pth", ".onnx", ".safetensors", ".npy",
}
WEIGHT_EXTENSIONS = {".pt", ".pth", ".onnx", ".safetensors"}

PROJECT_DIR = Path(__file__).parent


def validate_submission_dir(submission_dir: Path) -> list:
    """Validate submission directory contents. Returns list of error strings."""
    errors = []

    if not submission_dir.exists():
        errors.append(f"Submission directory not found: {submission_dir}")
        return errors

    run_py = submission_dir / "run.py"
    if not run_py.exists():
        errors.append("run.py not found in submission directory!")

    # Collect all files
    all_files = [f for f in submission_dir.rglob("*") if f.is_file()]

    if not all_files:
        errors.append("No files found in submission directory")
        return errors

    # Check file count
    if len(all_files) > MAX_FILES:
        errors.append(f"Too many files: {len(all_files)} > {MAX_FILES}")

    # Check extensions
    py_count = 0
    weight_count = 0
    total_size = 0

    for f in all_files:
        rel = f.relative_to(submission_dir)
        total_size += f.stat().st_size

        # Check for hidden files / macOS artifacts
        parts = rel.parts
        if any(p.startswith(".") or p == "__MACOSX" for p in parts):
            errors.append(f"Hidden/macOS file found: {rel}")
            continue

        # Check extension
        if f.suffix.lower() not in ALLOWED_EXTENSIONS:
            errors.append(f"Disallowed extension: {rel} ({f.suffix})")

        if f.suffix.lower() == ".py":
            py_count += 1
        if f.suffix.lower() in WEIGHT_EXTENSIONS:
            weight_count += 1

    if py_count > MAX_PY_FILES:
        errors.append(f"Too many .py files: {py_count} > {MAX_PY_FILES}")

    if weight_count > MAX_WEIGHT_FILES:
        errors.append(f"Too many weight files: {weight_count} > {MAX_WEIGHT_FILES}")

    if total_size > MAX_UNCOMPRESSED_SIZE:
        errors.append(
            f"Total size {total_size / 1024 / 1024:.1f} MB exceeds "
            f"{MAX_UNCOMPRESSED_SIZE / 1024 / 1024:.0f} MB limit"
        )

    return errors


def create_zip(submission_dir: Path, output_path: Path) -> None:
    """Create submission ZIP with files at root level."""
    all_files = sorted(
        f for f in submission_dir.rglob("*")
        if f.is_file()
        and not any(p.startswith(".") or p == "__MACOSX" for p in f.relative_to(submission_dir).parts)
    )

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath in all_files:
            arcname = str(filepath.relative_to(submission_dir))
            zf.write(filepath, arcname)

    return all_files


def verify_zip(zip_path: Path) -> bool:
    """Verify the ZIP structure — run.py must be at root."""
    ok = True
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

        if "run.py" not in names:
            print("  ERROR: run.py is NOT at ZIP root!")
            # Check if it's nested
            nested = [n for n in names if n.endswith("run.py")]
            if nested:
                print(f"  Found nested: {nested}")
                print("  FIX: run.py must be at the ZIP root, not in a subfolder")
            ok = False
        else:
            print("  OK: run.py is at ZIP root")

    return ok


def main():
    parser = argparse.ArgumentParser(description="Package NorgesGruppen submission")
    parser.add_argument(
        "--submission-dir", type=str,
        default=str(PROJECT_DIR / "submission"),
        help="Directory containing submission files (default: submission/)",
    )
    parser.add_argument(
        "--output", type=str,
        default=str(PROJECT_DIR / "submission.zip"),
        help="Output ZIP path (default: submission.zip)",
    )
    args = parser.parse_args()

    submission_dir = Path(args.submission_dir).resolve()
    output_path = Path(args.output).resolve()

    print(f"Submission directory: {submission_dir}")
    print(f"Output: {output_path}")
    print()

    # Validate structure
    print("--- Structure Validation ---")
    errors = validate_submission_dir(submission_dir)
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  - {e}")
        print("\nFix errors before packaging.")
        raise SystemExit(1)
    print("All structure checks passed.")

    # Validate imports (blocked modules check)
    print("\n--- Import Validation ---")
    py_files_to_check = sorted(submission_dir.rglob("*.py"))
    import_issues = 0
    for py_file in py_files_to_check:
        issues = validate_file(py_file)
        if issues:
            print(f"FAIL: {py_file.name}")
            for issue in issues:
                icon = "IMPORT" if issue["type"] == "blocked_import" else "CALL"
                print(f"  Line {issue['line']:>4d}: [{icon}] {issue['detail']}")
            import_issues += len(issues)
        else:
            print(f"PASS: {py_file.name}")
    if import_issues:
        print(f"\n{import_issues} blocked import(s) found — fix before packaging.")
        raise SystemExit(1)
    print("All import checks passed.")
    print()

    # Create ZIP
    print("--- Creating ZIP ---")
    all_files = create_zip(submission_dir, output_path)

    # Print contents summary
    print(f"\nZIP contents ({len(all_files)} files):")
    total_size = 0
    for f in all_files:
        rel = f.relative_to(submission_dir)
        size = f.stat().st_size
        total_size += size
        if size > 1024 * 1024:
            print(f"  {str(rel):<50s} {size / 1024 / 1024:>8.1f} MB")
        else:
            print(f"  {str(rel):<50s} {size / 1024:>8.1f} KB")

    print(f"\n  Total (uncompressed): {total_size / 1024 / 1024:.1f} MB")
    zip_size = output_path.stat().st_size
    print(f"  ZIP size (compressed): {zip_size / 1024 / 1024:.1f} MB")
    print()

    # Verify ZIP structure
    print("--- ZIP Verification ---")
    ok = verify_zip(output_path)

    if ok:
        print(f"\nSubmission ready: {output_path}")
    else:
        print("\nWARNING: ZIP verification failed — fix issues before uploading!")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
