#!/usr/bin/env python3
from __future__ import annotations

"""Full E2E smoke tests from graded Cloud Run logs.

Tests classification AND execution against live Tripletex sandbox.
Loads 1,241 unique prompts from /tmp/tripletex_all_parsed.json.

Usage:
    # Classify-only (fast, ~5s)
    python test_smoketest_graded.py --classify-only

    # Full E2E against local server
    python test_smoketest_graded.py --sample 3

    # Full E2E against Cloud Run
    python test_smoketest_graded.py --cloud --sample 3

    # Filter by task type / tier
    python test_smoketest_graded.py --task-type CREATE_CUSTOMER --cloud
    python test_smoketest_graded.py --tier 2 --sample 2 --cloud

    # High concurrency for classify-only
    python test_smoketest_graded.py --classify-only --concurrency 10
"""
import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATA_FILE = "/tmp/tripletex_all_parsed.json"
DEFAULT_ENDPOINT = "http://localhost:8080"
MAX_REQ_PER_SEC = 5.0  # API rate limit

# Tier assignments (mirrors task_types.py)
TIER_MAP = {
    # Tier 1
    "CREATE_EMPLOYEE": 1, "UPDATE_EMPLOYEE": 1, "DELETE_EMPLOYEE": 1,
    "SET_EMPLOYEE_ROLES": 1, "CREATE_CUSTOMER": 1, "UPDATE_CUSTOMER": 1,
    "CREATE_PRODUCT": 1, "DELETE_PRODUCT": 1, "UPDATE_PRODUCT": 1,
    "CREATE_INVOICE": 1, "CREATE_DEPARTMENT": 1, "CREATE_PROJECT": 1,
    # Tier 2
    "INVOICE_EXISTING_CUSTOMER": 2, "REGISTER_PAYMENT": 2,
    "CREATE_CREDIT_NOTE": 2, "INVOICE_WITH_PAYMENT": 2,
    "CREATE_TRAVEL_EXPENSE": 2, "DELETE_TRAVEL_EXPENSE": 2,
    "PROJECT_WITH_CUSTOMER": 2, "PROJECT_BILLING": 2,
    "CREATE_CONTACT": 2, "FIND_CUSTOMER": 2, "UPDATE_PROJECT": 2,
    "DELETE_PROJECT": 2, "LOG_HOURS": 2, "DELETE_CUSTOMER": 2,
    "UPDATE_CONTACT": 2, "UPDATE_DEPARTMENT": 2,
    "CREATE_SUPPLIER_INVOICE": 2, "CREATE_SUPPLIER": 2,
    "DELETE_DEPARTMENT": 2, "DELETE_SUPPLIER": 2,
    "FIND_SUPPLIER": 2, "UPDATE_SUPPLIER": 2,
    "RUN_PAYROLL": 2, "REVERSE_PAYMENT": 2,
    # Tier 3
    "BANK_RECONCILIATION": 3, "ERROR_CORRECTION": 3,
    "YEAR_END_CLOSING": 3, "MONTH_END_CLOSING": 3,
    "ENABLE_MODULE": 3, "REGISTER_SUPPLIER_INVOICE": 3,
    "CREATE_DIMENSION_VOUCHER": 3,
    # Special
    "BATCH": 0, "UNKNOWN": 0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env(env_path: str | None = None) -> dict[str, str]:
    """Load dotenv-style file into a dict (no dependencies)."""
    env = {}
    paths = [env_path] if env_path else [
        str(Path(__file__).resolve().parent.parent / ".env"),
        str(Path(__file__).resolve().parent / ".env"),
    ]
    for p in paths:
        if p and os.path.isfile(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    val = val.strip().strip("'\"")
                    env[key.strip()] = val
    return env


def strip_task_type(raw: str) -> str:
    """'TaskType.CREATE_CUSTOMER' -> 'CREATE_CUSTOMER'."""
    return raw.replace("TaskType.", "").strip()


def load_test_data(path: str) -> list[dict]:
    """Load and parse test data from JSON file, deduplicating by prompt."""
    if not os.path.isfile(path):
        print(f"ERROR: Test data file not found: {path}")
        print("Generate it from Cloud Run logs first.")
        sys.exit(1)
    with open(path) as f:
        raw = json.load(f)

    entries = []
    seen_prompts = set()
    for entry in raw:
        prompt = entry.get("prompt", "").strip()
        if not prompt:
            continue
        task_type = strip_task_type(entry.get("task_type", "UNKNOWN"))
        # Deduplicate by prompt (keep first occurrence)
        if prompt in seen_prompts:
            continue
        seen_prompts.add(prompt)
        entries.append({
            "prompt": prompt,
            "expected_type": task_type,
            "result": entry.get("result", ""),
            "fields": entry.get("fields", "{}"),
            "tier": TIER_MAP.get(task_type, 0),
        })
    return entries


def discover_cloud_url() -> str:
    """Use gcloud to discover the Cloud Run service URL."""
    try:
        result = subprocess.run(
            ["gcloud", "run", "services", "describe", "tripletex-agent",
             "--region", "europe-north1", "--format", "value(status.url)"],
            capture_output=True, text=True, timeout=15,
        )
        url = result.stdout.strip()
        if url and url.startswith("https://"):
            return url
        print(f"WARNING: gcloud returned unexpected URL: {url!r}")
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"WARNING: Could not discover Cloud Run URL: {e}")
    # Fallback
    return "https://tripletex-agent-490723.europe-north1.run.app"


# ---------------------------------------------------------------------------
# Rate-limited async HTTP client
# ---------------------------------------------------------------------------

class RateLimiter:
    """Token-bucket rate limiter."""

    def __init__(self, max_per_sec: float):
        self._interval = 1.0 / max_per_sec
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._last + self._interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


class TestResult:
    """Result of a single test."""

    def __init__(self, prompt: str, expected_type: str, tier: int):
        self.prompt = prompt
        self.expected_type = expected_type
        self.tier = tier
        self.actual_type: str | None = None
        self.classify_ok: bool = False
        self.exec_status: str | None = None  # "completed", "error", etc.
        self.exec_ok: bool = False
        self.duration: float = 0.0
        self.error: str | None = None
        self.response: dict | None = None


async def send_request(
    client: httpx.AsyncClient,
    rate_limiter: RateLimiter,
    endpoint: str,
    prompt: str,
    credentials: dict | None,
    classify_only: bool,
    timeout: float = 120.0,
) -> dict:
    """Send a single request to the /solve endpoint."""
    await rate_limiter.acquire()

    payload: dict = {"prompt": prompt, "files": []}
    if credentials:
        payload["tripletex_credentials"] = credentials

    url = f"{endpoint.rstrip('/')}/solve"
    t0 = time.monotonic()
    try:
        resp = await client.post(url, json=payload, timeout=timeout)
        elapsed = time.monotonic() - t0
        if resp.status_code == 200:
            data = resp.json()
            data["_elapsed"] = elapsed
            return data
        else:
            return {
                "_error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                "_elapsed": elapsed,
            }
    except Exception as e:
        elapsed = time.monotonic() - t0
        return {"_error": f"{type(e).__name__}: {e}", "_elapsed": elapsed}


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

async def run_tests(
    entries: list[dict],
    endpoint: str,
    credentials: dict | None,
    classify_only: bool,
    concurrency: int,
    timeout: float,
) -> list[TestResult]:
    """Run all tests with bounded concurrency and rate limiting."""
    rate_limiter = RateLimiter(MAX_REQ_PER_SEC)
    semaphore = asyncio.Semaphore(concurrency)
    results: list[TestResult] = []

    async def run_one(entry: dict) -> TestResult:
        tr = TestResult(entry["prompt"], entry["expected_type"], entry["tier"])
        async with semaphore:
            resp = await send_request(
                client, rate_limiter, endpoint,
                entry["prompt"], credentials, classify_only, timeout,
            )

        tr.duration = resp.get("_elapsed", 0.0)
        tr.response = resp

        if "_error" in resp:
            tr.error = resp["_error"]
            return tr

        # Check classification
        actual = resp.get("task_type", "")
        # Normalize: the endpoint may return "create_customer" or "CREATE_CUSTOMER"
        tr.actual_type = actual.upper().replace("TASKTYPE.", "").replace(".", "_")
        tr.classify_ok = tr.actual_type == tr.expected_type

        # Check execution (full mode)
        if not classify_only:
            status = resp.get("status", "")
            tr.exec_status = status
            tr.exec_ok = status == "completed"

        return tr

    # Use a single client for connection pooling
    transport = httpx.AsyncHTTPTransport(retries=1)
    async with httpx.AsyncClient(transport=transport) as client:
        tasks = [run_one(e) for e in entries]
        total = len(tasks)
        completed = 0

        # Process with progress updates
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1
            if completed % 20 == 0 or completed == total:
                pct = 100 * completed / total
                print(f"  Progress: {completed}/{total} ({pct:.0f}%)", flush=True)

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_summary(results: list[TestResult], classify_only: bool) -> int:
    """Print summary table and detailed failure report. Returns exit code."""
    # Group by expected type
    by_type: dict[str, list[TestResult]] = defaultdict(list)
    for r in results:
        by_type[r.expected_type].append(r)

    total_classify_ok = sum(1 for r in results if r.classify_ok)
    total_exec_ok = sum(1 for r in results if r.exec_ok) if not classify_only else 0
    total_errors = sum(1 for r in results if r.error)
    total = len(results)

    mode = "CLASSIFY-ONLY" if classify_only else "FULL E2E"
    print(f"\n{'=' * 80}")
    print(f"  SMOKE TEST RESULTS ({mode})")
    print(f"  {total} prompts | {len(by_type)} task types")
    print(f"{'=' * 80}\n")

    # Header
    if classify_only:
        hdr = f"{'Task Type':<35} {'N':>4} {'Cls OK':>7} {'Rate':>6} {'Err':>4}"
    else:
        hdr = f"{'Task Type':<35} {'N':>4} {'Cls OK':>7} {'Exec OK':>8} {'Rate':>6} {'Err':>4} {'Avg(s)':>7}"
    print(hdr)
    print("-" * len(hdr))

    for ttype in sorted(by_type.keys()):
        group = by_type[ttype]
        n = len(group)
        cls_ok = sum(1 for r in group if r.classify_ok)
        cls_rate = 100 * cls_ok / n if n else 0
        errs = sum(1 for r in group if r.error)

        if classify_only:
            print(f"{ttype:<35} {n:>4} {cls_ok:>4}/{n:<2} {cls_rate:>5.0f}% {errs:>4}")
        else:
            exec_ok = sum(1 for r in group if r.exec_ok)
            avg_dur = sum(r.duration for r in group) / n if n else 0
            print(f"{ttype:<35} {n:>4} {cls_ok:>4}/{n:<2} {exec_ok:>5}/{n:<2} {cls_rate:>5.0f}% {errs:>4} {avg_dur:>6.1f}s")

    # Totals
    print("-" * len(hdr))
    cls_pct = 100 * total_classify_ok / total if total else 0
    if classify_only:
        print(f"{'TOTAL':<35} {total:>4} {total_classify_ok:>4}/{total:<2} {cls_pct:>5.1f}% {total_errors:>4}")
    else:
        exec_pct = 100 * total_exec_ok / total if total else 0
        avg_all = sum(r.duration for r in results) / total if total else 0
        print(f"{'TOTAL':<35} {total:>4} {total_classify_ok:>4}/{total:<2} {total_exec_ok:>5}/{total:<2} {cls_pct:>5.1f}% {total_errors:>4} {avg_all:>6.1f}s")

    # ----- Misclassification details -----
    misclassified = [r for r in results if not r.classify_ok and not r.error]
    if misclassified:
        print(f"\n{'=' * 80}")
        print(f"  MISCLASSIFICATIONS ({len(misclassified)})")
        print(f"{'=' * 80}")
        # Group by (expected, actual) for a confusion-matrix view
        confusion: dict[tuple[str, str], list[str]] = defaultdict(list)
        for r in misclassified:
            confusion[(r.expected_type, r.actual_type or "NONE")].append(r.prompt)
        for (exp, act), prompts in sorted(confusion.items()):
            print(f"\n  {exp} -> {act}  ({len(prompts)}x)")
            for p in prompts[:5]:
                print(f"    - {p[:110]}")
            if len(prompts) > 5:
                print(f"    ... and {len(prompts) - 5} more")

    # ----- Execution failures (full mode only) -----
    if not classify_only:
        exec_failures = [r for r in results if r.classify_ok and not r.exec_ok and not r.error]
        if exec_failures:
            print(f"\n{'=' * 80}")
            print(f"  EXECUTION FAILURES ({len(exec_failures)}) -- correctly classified but execution failed")
            print(f"{'=' * 80}")
            for r in exec_failures[:30]:
                status = r.exec_status or "N/A"
                detail = ""
                if r.response:
                    detail = r.response.get("error", "")
                    if not detail:
                        details_obj = r.response.get("details", {})
                        if isinstance(details_obj, dict):
                            detail = details_obj.get("error", "")
                    if isinstance(detail, dict):
                        detail = json.dumps(detail)[:200]
                    elif isinstance(detail, str):
                        detail = detail[:200]
                print(f"\n  Type:   {r.expected_type}")
                print(f"  Status: {status}")
                print(f"  Prompt: {r.prompt[:120]}")
                if detail:
                    print(f"  Error:  {detail}")
            if len(exec_failures) > 30:
                print(f"\n  ... and {len(exec_failures) - 30} more failures")

    # ----- HTTP / transport errors -----
    http_errors = [r for r in results if r.error]
    if http_errors:
        print(f"\n{'=' * 80}")
        print(f"  HTTP / TRANSPORT ERRORS ({len(http_errors)})")
        print(f"{'=' * 80}")
        for r in http_errors[:20]:
            print(f"\n  Type:   {r.expected_type}")
            print(f"  Error:  {r.error}")
            print(f"  Prompt: {r.prompt[:100]}")
        if len(http_errors) > 20:
            print(f"\n  ... and {len(http_errors) - 20} more errors")

    # ----- Final verdict -----
    print(f"\n{'=' * 80}")
    if classify_only:
        ok = total_classify_ok == total and total_errors == 0
        verdict = "PASS" if ok else "FAIL"
        print(f"  Classification accuracy: {cls_pct:.1f}% ({total_classify_ok}/{total})")
    else:
        exec_pct = 100 * total_exec_ok / total if total else 0
        ok = total_exec_ok == total and total_errors == 0
        verdict = "PASS" if ok else ("MIXED" if total_exec_ok > total * 0.8 else "FAIL")
        print(f"  Classification: {cls_pct:.1f}% | Execution: {exec_pct:.1f}% | Errors: {total_errors}")
    print(f"  Verdict: {verdict}")
    print(f"{'=' * 80}\n")

    return 0 if verdict != "FAIL" else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="E2E smoke test for Tripletex AI agent using graded Cloud Run logs",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                        help="Service URL (default: http://localhost:8080)")
    parser.add_argument("--cloud", action="store_true",
                        help="Discover and use Cloud Run URL")
    parser.add_argument("--classify-only", action="store_true",
                        help="Test only classification (no execution)")
    parser.add_argument("--task-type", type=str, default=None,
                        help="Filter to a specific task type (e.g. CREATE_CUSTOMER)")
    parser.add_argument("--tier", type=int, default=None,
                        help="Filter to a specific tier (1, 2, or 3)")
    parser.add_argument("--sample", type=int, default=None,
                        help="Random sample N prompts per task type")
    parser.add_argument("--concurrency", type=int, default=3,
                        help="Max concurrent requests (default: 3)")
    parser.add_argument("--timeout", type=float, default=120.0,
                        help="Request timeout in seconds (default: 120)")
    parser.add_argument("--data-file", default=DATA_FILE,
                        help=f"Path to parsed grader JSON (default: {DATA_FILE})")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for --sample (default: 42)")
    args = parser.parse_args()

    # Endpoint
    endpoint = args.endpoint
    if args.cloud:
        print("Discovering Cloud Run URL...")
        endpoint = discover_cloud_url()
    print(f"Endpoint: {endpoint}")

    # Credentials
    env = load_env()
    base_url = os.environ.get("TRIPLETEX_BASE_URL") or env.get("TRIPLETEX_BASE_URL", "")
    session_token = os.environ.get("TRIPLETEX_SESSION_TOKEN") or env.get("TRIPLETEX_SESSION_TOKEN", "")
    credentials = None
    if base_url and session_token:
        credentials = {"base_url": base_url, "session_token": session_token}
        print(f"Credentials: loaded (base_url={base_url[:40]}...)")
    else:
        if not args.classify_only:
            print("WARNING: No Tripletex credentials found. Full E2E tests will fail.")
            print("  Set TRIPLETEX_BASE_URL and TRIPLETEX_SESSION_TOKEN in env or .env file.")

    # Load data
    print(f"Loading test data from {args.data_file}...")
    entries = load_test_data(args.data_file)
    print(f"  Loaded {len(entries)} unique prompts")

    # Filter by task type
    if args.task_type:
        target = args.task_type.upper().replace("TASKTYPE.", "")
        entries = [e for e in entries if e["expected_type"] == target]
        print(f"  Filtered to task type {target}: {len(entries)} prompts")

    # Filter by tier
    if args.tier is not None:
        entries = [e for e in entries if e["tier"] == args.tier]
        print(f"  Filtered to tier {args.tier}: {len(entries)} prompts")

    if not entries:
        print("ERROR: No test entries after filtering.")
        sys.exit(1)

    # Sample
    if args.sample:
        random.seed(args.seed)
        by_type: dict[str, list[dict]] = defaultdict(list)
        for e in entries:
            by_type[e["expected_type"]].append(e)
        sampled = []
        for ttype in sorted(by_type.keys()):
            group = by_type[ttype]
            n = min(args.sample, len(group))
            sampled.extend(random.sample(group, n))
        entries = sampled
        print(f"  Sampled {args.sample} per type: {len(entries)} prompts total")

    # Type summary
    type_counts: dict[str, int] = defaultdict(int)
    for e in entries:
        type_counts[e["expected_type"]] += 1
    print(f"  Task types: {len(type_counts)}")
    for t in sorted(type_counts):
        print(f"    {t}: {type_counts[t]}")

    mode = "classify-only" if args.classify_only else "full E2E"
    print(f"\nRunning {mode} tests ({len(entries)} prompts, concurrency={args.concurrency})...\n")

    t0 = time.monotonic()
    results = asyncio.run(run_tests(
        entries, endpoint, credentials,
        classify_only=args.classify_only,
        concurrency=args.concurrency,
        timeout=args.timeout,
    ))
    elapsed = time.monotonic() - t0

    print(f"\nCompleted in {elapsed:.1f}s ({len(results) / elapsed:.1f} req/s)")

    exit_code = print_summary(results, args.classify_only)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
