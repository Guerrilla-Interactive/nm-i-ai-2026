"""
Validate submission run.py for blocked imports and unsafe operations.

Uses AST parsing for accurate detection — not just string matching.

Usage:
    python validate_submission.py
    python validate_submission.py --file submission/run.py
"""
import argparse
import ast
from pathlib import Path


PROJECT_DIR = Path(__file__).parent

# Modules blocked in the competition sandbox
BLOCKED_MODULES = {
    "os", "sys", "subprocess", "socket", "ctypes", "builtins",
    "importlib", "pickle", "marshal", "shelve", "shutil", "yaml",
    "requests", "urllib", "http", "http.client",
    "multiprocessing", "threading", "signal", "gc",
    "code", "codeop", "pty",
    # ultralytics eagerly imports os/sys/socket/yaml/pickle — always crashes in sandbox
    "ultralytics",
}

# Dangerous built-in calls
BLOCKED_CALLS = {"eval", "exec", "compile", "__import__"}


class BlockedImportVisitor(ast.NodeVisitor):
    """AST visitor that detects blocked imports and unsafe operations."""

    def __init__(self):
        self.issues = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            top_module = alias.name.split(".")[0]
            if top_module in BLOCKED_MODULES or alias.name in BLOCKED_MODULES:
                self.issues.append({
                    "line": node.lineno,
                    "type": "blocked_import",
                    "detail": f"import {alias.name}",
                    "module": alias.name,
                })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            top_module = node.module.split(".")[0]
            if top_module in BLOCKED_MODULES or node.module in BLOCKED_MODULES:
                names = ", ".join(a.name for a in node.names)
                self.issues.append({
                    "line": node.lineno,
                    "type": "blocked_import",
                    "detail": f"from {node.module} import {names}",
                    "module": node.module,
                })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name in BLOCKED_CALLS:
            self.issues.append({
                "line": node.lineno,
                "type": "blocked_call",
                "detail": f"{func_name}()",
                "module": None,
            })
        self.generic_visit(node)


def validate_file(file_path: Path) -> list:
    """Parse and validate a Python file. Returns list of issue dicts."""
    source = file_path.read_text(encoding="utf-8")

    # Parse AST
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        return [{
            "line": e.lineno or 0,
            "type": "syntax_error",
            "detail": str(e),
            "module": None,
        }]

    visitor = BlockedImportVisitor()
    visitor.visit(tree)
    return visitor.issues


def main():
    parser = argparse.ArgumentParser(description="Validate submission for blocked imports")
    parser.add_argument(
        "--file", type=str,
        default=str(PROJECT_DIR / "submission" / "run.py"),
        help="Path to run.py to validate (default: submission/run.py)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Validate all .py files in the submission directory",
    )
    args = parser.parse_args()

    target = Path(args.file).resolve()

    if args.all:
        # Validate all .py files in submission dir
        submission_dir = target.parent if target.suffix == ".py" else target
        py_files = sorted(submission_dir.rglob("*.py"))
    else:
        py_files = [target]

    total_issues = 0

    for py_file in py_files:
        if not py_file.exists():
            print(f"SKIP: {py_file} (not found)")
            continue

        rel_path = py_file.name
        issues = validate_file(py_file)

        if issues:
            print(f"FAIL: {rel_path}")
            for issue in issues:
                icon = "IMPORT" if issue["type"] == "blocked_import" else "CALL"
                print(f"  Line {issue['line']:>4d}: [{icon}] {issue['detail']}")
            total_issues += len(issues)
        else:
            print(f"PASS: {rel_path}")

    print()
    if total_issues > 0:
        print(f"RESULT: FAIL — {total_issues} issue(s) found")
        print()
        print("Blocked modules (will crash in sandbox):")
        for mod in sorted(BLOCKED_MODULES):
            print(f"  - {mod}")
        print()
        print("Blocked calls:")
        for call in sorted(BLOCKED_CALLS):
            print(f"  - {call}()")
        print()
        print("Alternatives:")
        print("  os         -> pathlib.Path")
        print("  yaml       -> json")
        print("  pickle     -> json")
        print("  subprocess -> (not available, pre-compute offline)")
        print("  requests   -> (not available, no network in sandbox)")
        raise SystemExit(1)
    else:
        print(f"RESULT: PASS — all {len(py_files)} file(s) clean")


if __name__ == "__main__":
    main()
