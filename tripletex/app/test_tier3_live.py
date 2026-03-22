"""Comprehensive Tier 3 E2E test — tests all 8 Tier 3 task types against the live endpoint.

Usage:
    python test_tier3_live.py                          # localhost:8080
    python test_tier3_live.py --endpoint https://...   # Cloud Run or ngrok
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

import httpx

# ---------------------------------------------------------------------------
# .env loading
# ---------------------------------------------------------------------------
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
_env: dict[str, str] = {}
if os.path.exists(ENV_PATH):
    for line in open(ENV_PATH):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            _env[k] = v

CREDS = {
    "base_url": _env.get("TRIPLETEX_BASE_URL", ""),
    "session_token": _env.get("TRIPLETEX_SESSION_TOKEN", ""),
}

# ---------------------------------------------------------------------------
# Tier 3 test cases: (id, prompt, expected_task_type)
# ---------------------------------------------------------------------------
TIER3_TESTS: list[tuple[str, str, str]] = [
    # ── Norwegian (primary) ──────────────────────────────────────────────
    ("T3-nb-bank",      "Utfor bankavstemming for konto 1920",                                      "bank_reconciliation"),
    ("T3-nb-errcorr",   "Korriger feilpostering pa bilag 12345",                                    "error_correction"),
    ("T3-nb-yearend",   "Utfor arsavslutning for 2025",                                             "year_end_closing"),
    ("T3-nb-module",    "Aktiver modulen Prosjekt",                                                 "enable_module"),
    ("T3-nb-payroll",   "Kjor lonnskjoring for mars 2026",                                          "run_payroll"),
    ("T3-nb-supinv",    "Registrer leverandorfaktura fra Acme AS pa 10000 kr",                      "register_supplier_invoice"),
    ("T3-nb-revpay",    "Reverser betaling pa faktura 99999",                                       "reverse_payment"),
    ("T3-nb-dimvch",    "Opprett dimensjon Avdeling med verdi Oslo og for bilag",                   "create_dimension_voucher"),

    # ── English variants ─────────────────────────────────────────────────
    ("T3-en-bank",      "Perform bank reconciliation for account 1920",                             "bank_reconciliation"),
    ("T3-en-errcorr",   "Correct the posting error on voucher 12345",                               "error_correction"),
    ("T3-en-yearend",   "Perform year-end closing for 2025",                                        "year_end_closing"),
    ("T3-en-module",    "Enable the Project module",                                                "enable_module"),
    ("T3-en-payroll",   "Run payroll for March 2026",                                               "run_payroll"),
    ("T3-en-supinv",    "Register a supplier invoice from Acme AS for 10000 NOK",                   "register_supplier_invoice"),
    ("T3-en-revpay",    "Reverse payment on invoice 99999",                                         "reverse_payment"),
    ("T3-en-dimvch",    "Create dimension Department with value Oslo and post a voucher",           "create_dimension_voucher"),

    # ── German variants (key tests) ──────────────────────────────────────
    ("T3-de-bank",      "Bankabstimmung fuer Konto 1920 durchfuehren",                              "bank_reconciliation"),
    ("T3-de-errcorr",   "Fehlbuchung auf Beleg 12345 korrigieren",                                  "error_correction"),
    ("T3-de-yearend",   "Jahresabschluss fuer 2025 durchfuehren",                                   "year_end_closing"),
    ("T3-de-module",    "Modul Projekt aktivieren",                                                 "enable_module"),
    ("T3-de-payroll",   "Gehaltsabrechnung fuer Maerz 2026 ausfuehren",                             "run_payroll"),
    ("T3-de-supinv",    "Lieferantenrechnung von Acme AS ueber 10000 NOK erfassen",                 "register_supplier_invoice"),
]

RESULTS: list[dict] = []


async def run_test(client: httpx.AsyncClient, endpoint: str, test_id: str, prompt: str, expected_type: str) -> dict:
    body = {"prompt": prompt, "files": [], "tripletex_credentials": CREDS}
    start = time.monotonic()
    try:
        resp = await client.post(f"{endpoint}/solve", json=body)
        elapsed = round(time.monotonic() - start, 2)
        data = resp.json() if resp.status_code == 200 else {}

        actual_type = data.get("task_type", "")
        # Normalize enum repr like "TaskType.BANK_RECONCILIATION" → "bank_reconciliation"
        normalized_type = actual_type.split(".")[-1].lower() if "." in actual_type else actual_type
        status_field = data.get("status", "")
        success_field = data.get("success", False)

        type_ok = normalized_type == expected_type
        status_ok = status_field == "completed"
        success_ok = success_field is True

        all_ok = type_ok and status_ok and success_ok and resp.status_code == 200

        result = {
            "id": test_id,
            "prompt": prompt,
            "expected_type": expected_type,
            "actual_type": actual_type,
            "status_code": resp.status_code,
            "status": status_field,
            "success": success_field,
            "type_ok": type_ok,
            "status_ok": status_ok,
            "success_ok": success_ok,
            "all_ok": all_ok,
            "elapsed": elapsed,
            "response_preview": resp.text[:300],
        }

        icon = "PASS" if all_ok else "FAIL"
        issues = []
        if not type_ok:
            issues.append(f"type={actual_type} (expected {expected_type})")
        if not status_ok:
            issues.append(f"status={status_field}")
        if not success_ok:
            issues.append(f"success={success_field}")
        if resp.status_code != 200:
            issues.append(f"HTTP {resp.status_code}")
        detail = " | " + ", ".join(issues) if issues else ""

        print(f"  [{icon}] {test_id:18s} | {elapsed:5.1f}s | type={actual_type:30s}{detail}")

    except Exception as e:
        elapsed = round(time.monotonic() - start, 2)
        result = {
            "id": test_id,
            "prompt": prompt,
            "expected_type": expected_type,
            "actual_type": "",
            "status_code": 0,
            "status": "",
            "success": False,
            "type_ok": False,
            "status_ok": False,
            "success_ok": False,
            "all_ok": False,
            "elapsed": elapsed,
            "response_preview": str(e)[:300],
        }
        print(f"  [ERR ] {test_id:18s} | {elapsed:5.1f}s | {e}")

    RESULTS.append(result)
    return result


async def main(endpoint: str):
    print(f"Tier 3 E2E Test Suite")
    print(f"Endpoint: {endpoint}")
    print(f"Credentials: base_url={CREDS['base_url'][:50]}...")
    print(f"Token: {CREDS['session_token'][:20]}..." if CREDS['session_token'] else "Token: (empty!)")
    print()

    # Health check
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{endpoint}/health")
            print(f"Health check: {resp.status_code} — {resp.text[:100]}")
    except Exception as e:
        print(f"Health check FAILED: {e}")
        print("Is the server running?")
        sys.exit(1)

    print()
    print(f"Running {len(TIER3_TESTS)} tests...")
    print("-" * 90)

    async with httpx.AsyncClient(timeout=120) as client:
        for test_id, prompt, expected in TIER3_TESTS:
            await run_test(client, endpoint, test_id, prompt, expected)
            await asyncio.sleep(0.5)  # Don't hammer the endpoint

    # ── Summary table ────────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("SUMMARY")
    print("=" * 90)
    print(f"{'ID':18s} | {'Expected':30s} | {'Actual':30s} | {'Type':4s} | {'Stat':4s} | {'Succ':4s} | {'Time':5s}")
    print("-" * 90)

    for r in RESULTS:
        t = "OK" if r["type_ok"] else "FAIL"
        s = "OK" if r["status_ok"] else "FAIL"
        u = "OK" if r["success_ok"] else "FAIL"
        print(f"{r['id']:18s} | {r['expected_type']:30s} | {r['actual_type']:30s} | {t:4s} | {s:4s} | {u:4s} | {r['elapsed']:5.1f}s")

    print("-" * 90)

    total = len(RESULTS)
    all_pass = sum(1 for r in RESULTS if r["all_ok"])
    type_pass = sum(1 for r in RESULTS if r["type_ok"])
    status_pass = sum(1 for r in RESULTS if r["status_ok"])
    success_pass = sum(1 for r in RESULTS if r["success_ok"])

    print(f"All pass:     {all_pass}/{total}")
    print(f"Type correct: {type_pass}/{total}")
    print(f"Status OK:    {status_pass}/{total}")
    print(f"Success OK:   {success_pass}/{total}")
    print()

    # Group by language
    for lang, label in [("nb", "Norwegian"), ("en", "English"), ("de", "German")]:
        lang_results = [r for r in RESULTS if r["id"].startswith(f"T3-{lang}-")]
        if lang_results:
            lang_pass = sum(1 for r in lang_results if r["all_ok"])
            print(f"  {label}: {lang_pass}/{len(lang_results)} passed")

    print()
    total_time = sum(r["elapsed"] for r in RESULTS)
    print(f"Total time: {total_time:.1f}s")

    # Exit code
    if all_pass == total:
        print("\nAll tests PASSED!")
        sys.exit(0)
    else:
        print(f"\n{total - all_pass} test(s) FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tier 3 E2E live test suite")
    parser.add_argument("--endpoint", default="http://localhost:8080", help="Server endpoint URL")
    args = parser.parse_args()
    asyncio.run(main(args.endpoint.rstrip("/")))
