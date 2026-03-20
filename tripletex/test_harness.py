#!/usr/bin/env python3
"""
Test harness for the Tripletex AI accounting agent.
Simulates the NM i AI 2026 competition judge by sending POST /solve requests.

Usage:
    python test_harness.py                              # Run all tests
    python test_harness.py --filter create_employee     # Filter by task type
    python test_harness.py --language norwegian          # Filter by language
    python test_harness.py --tier 1                      # Filter by tier
    python test_harness.py --endpoint http://host:8080   # Custom endpoint
    python test_harness.py --id create_employee_nb_1     # Run specific test
    python test_harness.py --list                        # List all test cases
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    try:
        import requests as _requests_mod
        # Minimal httpx-like shim over requests
        class _RequestsShim:
            class TimeoutException(Exception):
                pass
            def post(self, url, *, json=None, headers=None, timeout=None):
                try:
                    r = _requests_mod.post(url, json=json, headers=headers, timeout=timeout)
                    return r
                except _requests_mod.exceptions.Timeout:
                    raise self.TimeoutException("Request timed out")
                except _requests_mod.exceptions.ConnectionError as e:
                    raise ConnectionError(str(e))
        httpx = _RequestsShim()
        _USING_REQUESTS = True
    except ImportError:
        print("ERROR: Install httpx or requests: pip install httpx")
        sys.exit(1)
    else:
        _USING_REQUESTS = True
else:
    _USING_REQUESTS = False

# Fake credentials for local testing
FAKE_CREDENTIALS = {
    "base_url": "https://tripletex-proxy.example.com/v2",
    "session_token": "test-session-token-00000000-0000-0000-0000-000000000000",
}

FAKE_BEARER_TOKEN = "test-bearer-token-for-judge"

DEFAULT_ENDPOINT = "http://localhost:8080"
DEFAULT_TIMEOUT = 300  # 5 min, matching competition


def load_test_cases(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    return data["test_cases"]


def filter_cases(
    cases: list[dict],
    task_type: str | None = None,
    language: str | None = None,
    tier: int | None = None,
    test_id: str | None = None,
) -> list[dict]:
    filtered = cases
    if test_id:
        filtered = [c for c in filtered if c["id"] == test_id]
    if task_type:
        filtered = [c for c in filtered if task_type in c["task_type"]]
    if language:
        filtered = [c for c in filtered if language.lower() in c["language"].lower()]
    if tier is not None:
        filtered = [c for c in filtered if c["tier"] == tier]
    return filtered


def run_test(endpoint: str, case: dict, timeout: int) -> dict:
    """Send a single test case to the /solve endpoint and return results."""
    url = f"{endpoint.rstrip('/')}/solve"

    payload = {
        "prompt": case["prompt"],
        "tripletex_credentials": FAKE_CREDENTIALS,
        "files": [],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FAKE_BEARER_TOKEN}",
    }

    result = {
        "id": case["id"],
        "task_type": case["task_type"],
        "language": case["language"],
        "status": "unknown",
        "time_ms": 0,
        "response_code": None,
        "response_body": None,
        "error": None,
    }

    start = time.monotonic()
    try:
        if _USING_REQUESTS:
            resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        else:
            resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        result["time_ms"] = elapsed_ms
        result["response_code"] = resp.status_code

        try:
            result["response_body"] = resp.json()
        except Exception:
            result["response_body"] = getattr(resp, "text", str(resp.content))

        if resp.status_code == 200:
            body = result["response_body"]
            if isinstance(body, dict) and body.get("status") == "completed":
                result["status"] = "pass"
            else:
                result["status"] = "fail"
                result["error"] = f"Expected status=completed, got: {body}"
        else:
            result["status"] = "fail"
            result["error"] = f"HTTP {resp.status_code}"

    except (ConnectionError, OSError) as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        result["time_ms"] = elapsed_ms
        result["status"] = "error"
        result["error"] = f"Connection error: {e}"
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        result["time_ms"] = elapsed_ms
        if "timeout" in type(e).__name__.lower() or "timeout" in str(e).lower():
            result["status"] = "timeout"
            result["error"] = f"Timed out after {timeout}s"
        else:
            result["status"] = "error"
            result["error"] = str(e)

    return result


def print_result(r: dict, verbose: bool = False) -> None:
    status_icon = {
        "pass": "\033[32m✓\033[0m",
        "fail": "\033[31m✗\033[0m",
        "timeout": "\033[33m⏱\033[0m",
        "error": "\033[31m⚠\033[0m",
        "unknown": "\033[90m?\033[0m",
    }
    icon = status_icon.get(r["status"], "?")
    time_str = f"{r['time_ms']}ms"
    print(f"  {icon} [{r['id']:<35}] {r['status']:<8} {time_str:>8}  {r['language']}")
    if r["error"] and (verbose or r["status"] != "pass"):
        print(f"    └─ {r['error']}")


def print_summary(results: list[dict]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    errors = sum(1 for r in results if r["status"] == "error")
    timeouts = sum(1 for r in results if r["status"] == "timeout")
    avg_ms = sum(r["time_ms"] for r in results) / total if total else 0

    print("\n" + "=" * 70)
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f", {failed} failed", end="")
    if errors:
        print(f", {errors} errors", end="")
    if timeouts:
        print(f", {timeouts} timeouts", end="")
    print(f"\n  Avg response time: {avg_ms:.0f}ms")
    print("=" * 70)

    # Per task-type breakdown
    task_types = sorted(set(r["task_type"] for r in results))
    if len(task_types) > 1:
        print("\n  By task type:")
        for tt in task_types:
            tt_results = [r for r in results if r["task_type"] == tt]
            tt_pass = sum(1 for r in tt_results if r["status"] == "pass")
            print(f"    {tt:<25} {tt_pass}/{len(tt_results)}")


def list_cases(cases: list[dict]) -> None:
    print(f"\n  {len(cases)} test cases:\n")
    for c in cases:
        print(f"  [{c['id']:<35}] T{c['tier']} {c['task_type']:<20} {c['language']}")
        print(f"    {c['prompt'][:80]}{'...' if len(c['prompt']) > 80 else ''}")


def main():
    parser = argparse.ArgumentParser(description="Tripletex AI agent test harness")
    parser.add_argument(
        "--endpoint", default=DEFAULT_ENDPOINT, help=f"Solve endpoint base URL (default: {DEFAULT_ENDPOINT})"
    )
    parser.add_argument("--filter", dest="task_type", help="Filter by task type (substring match)")
    parser.add_argument("--language", help="Filter by language")
    parser.add_argument("--tier", type=int, help="Filter by tier")
    parser.add_argument("--id", dest="test_id", help="Run a specific test case by ID")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"Timeout per request in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show response bodies")
    parser.add_argument("--list", action="store_true", help="List test cases without running")
    parser.add_argument("--json-output", help="Write results to JSON file")
    parser.add_argument(
        "--prompts", default=str(Path(__file__).parent / "test_prompts.json"),
        help="Path to test_prompts.json",
    )
    args = parser.parse_args()

    prompts_path = Path(args.prompts)
    if not prompts_path.exists():
        print(f"ERROR: Test prompts not found: {prompts_path}")
        sys.exit(1)

    cases = load_test_cases(prompts_path)
    cases = filter_cases(cases, args.task_type, args.language, args.tier, args.test_id)

    if not cases:
        print("No test cases match the given filters.")
        sys.exit(1)

    if args.list:
        list_cases(cases)
        sys.exit(0)

    print(f"\n  Tripletex Agent Test Harness")
    print(f"  Endpoint: {args.endpoint}")
    print(f"  Tests:    {len(cases)}")
    print(f"  Timeout:  {args.timeout}s\n")
    print("-" * 70)

    results = []
    for case in cases:
        result = run_test(args.endpoint, case, args.timeout)
        results.append(result)
        print_result(result, args.verbose)

    print_summary(results)

    if args.json_output:
        with open(args.json_output, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n  Results written to {args.json_output}")

    # Exit code: 0 if all pass, 1 if any failure
    sys.exit(0 if all(r["status"] == "pass" for r in results) else 1)


if __name__ == "__main__":
    main()
