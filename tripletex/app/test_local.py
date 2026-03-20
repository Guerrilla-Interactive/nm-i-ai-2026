"""Quick local test — sends test tasks to the running /solve endpoint."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import httpx

BASE = "http://localhost:8080"

# Load from .env file
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
_env = {}
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

TEST_TASKS = [
    # Tier 1 basics
    ("create_department", "Opprett en avdeling med navn Salg og avdelingsnummer 10"),
    ("create_customer", "Opprett en kunde med navn Test Firma AS"),
    ("create_employee", "Opprett en ansatt med fornavn Ola og etternavn Nordmann, e-post ola@test.no"),
    ("create_product", "Create a product named Widget with price 299 NOK"),
    ("create_department_fr", "Créer un département appelé Marketing"),
]

RESULTS: list[dict] = []


async def test_task(label: str, prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        body = {
            "prompt": prompt,
            "files": [],
            "tripletex_credentials": CREDS,
        }
        print(f"\n{'='*60}")
        print(f"TASK [{label}]: {prompt[:80]}")
        start = time.monotonic()
        try:
            resp = await client.post(f"{BASE}/solve", json=body)
            elapsed = round(time.monotonic() - start, 2)
            print(f"STATUS: {resp.status_code} ({elapsed}s)")
            print(f"RESPONSE: {resp.text[:300]}")
            result = {
                "label": label,
                "prompt": prompt,
                "status_code": resp.status_code,
                "response": resp.text[:500],
                "elapsed": elapsed,
                "success": resp.status_code == 200,
            }
        except Exception as e:
            elapsed = round(time.monotonic() - start, 2)
            print(f"ERROR: {e}")
            result = {
                "label": label,
                "prompt": prompt,
                "status_code": 0,
                "response": str(e),
                "elapsed": elapsed,
                "success": False,
            }
        RESULTS.append(result)
        return result


async def main():
    # Check health first
    print("Checking health...")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{BASE}/health")
            print(f"Health: {resp.status_code} — {resp.text}")
    except Exception as e:
        print(f"Server not reachable: {e}")
        sys.exit(1)

    print(f"\nCredentials: base_url={CREDS['base_url'][:40]}...")
    print(f"Token: {CREDS['session_token'][:20]}...")

    if len(sys.argv) > 1:
        # Test a single task
        await test_task("custom", " ".join(sys.argv[1:]))
    else:
        # Test all
        for label, task in TEST_TASKS:
            await test_task(label, task)

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for r in RESULTS if r["success"])
    print(f"Passed: {passed}/{len(RESULTS)}")
    for r in RESULTS:
        status = "PASS" if r["success"] else "FAIL"
        print(f"  [{status}] {r['label']}: {r['elapsed']}s")


asyncio.run(main())
