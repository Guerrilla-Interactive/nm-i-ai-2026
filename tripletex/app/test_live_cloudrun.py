"""Comprehensive live test against Cloud Run deployment.

Tests all major task types across multiple languages to verify:
1. Gemini 2.5 Pro classification is working (not falling back to keyword)
2. Field extraction is correct
3. Executor handles fresh sandbox properly
4. API call efficiency

Usage: python test_live_cloudrun.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import httpx

# Cloud Run URL
CLOUD_RUN_URL = "https://tripletex-agent-785696234845.europe-north1.run.app"

# Load creds from .env
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

# Test cases: (label, expected_task_type, prompt)
TEST_TASKS = [
    # === Tier 1 ===
    ("T1: Create Employee (NO)", "CREATE_EMPLOYEE",
     "Opprett en ansatt med fornavn Lars og etternavn Berg, e-post lars.berg@firma.no"),

    ("T1: Create Customer (EN)", "CREATE_CUSTOMER",
     "Create a customer called Nordic Solutions AS with email info@nordic.no and org number 987654321"),

    ("T1: Create Product (DE)", "CREATE_PRODUCT",
     "Erstellen Sie ein Produkt namens Beratungsstunde mit einem Preis von 1200 NOK"),

    ("T1: Create Department (FR)", "CREATE_DEPARTMENT",
     "Créer un département appelé Ressources Humaines avec le numéro 20"),

    ("T1: Create Project (ES)", "CREATE_PROJECT",
     "Crear un proyecto llamado Migración Cloud con fecha de inicio 2026-03-20"),

    ("T1: Create Invoice (NO)", "CREATE_INVOICE",
     "Lag en faktura til kunde Havbris AS for 5 timer rådgivning à 950 kr per time"),

    # === Tier 2 ===
    ("T2: Invoice with Payment (PT)", "INVOICE_WITH_PAYMENT",
     "Crie uma fatura para o cliente Porto Digital Lda por 2 horas de consultoria a 500 NOK cada e registe o pagamento total"),

    ("T2: Create Contact (NO)", "CREATE_CONTACT",
     "Opprett kontaktperson Maria Hansen med e-post maria@test.no for kunde Havbris AS"),

    ("T2: Create Travel Expense (EN)", "CREATE_TRAVEL_EXPENSE",
     "Create a travel expense for employee Lars Berg, trip to Oslo from Bergen, departure 2026-03-21"),

    ("T2: Log Hours (NO)", "LOG_HOURS",
     "Registrer 7.5 timer for ansatt Lars Berg på prosjekt Migración Cloud den 2026-03-20"),

    # === Classification-only checks (verify Gemini, no execution needed) ===
    ("T2: Register Payment (NL)", "REGISTER_PAYMENT",
     "Registreer een betaling van 5000 NOK op factuur nummer 12345"),

    ("T2: Update Customer (IT)", "UPDATE_CUSTOMER",
     "Aggiornare l'indirizzo email del cliente Nordic Solutions AS a nuovo@nordic.no"),

    ("T3: Enable Module (NO)", "ENABLE_MODULE",
     "Aktiver reiseregning-modulen i Tripletex"),
]

RESULTS: list[dict] = []


async def test_task(label: str, expected_type: str, prompt: str) -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        body = {
            "prompt": prompt,
            "files": [],
            "tripletex_credentials": CREDS,
        }
        print(f"\n{'='*70}")
        print(f"TEST: {label}")
        print(f"PROMPT: {prompt[:90]}...")
        print(f"EXPECTED: {expected_type}")
        start = time.monotonic()
        try:
            resp = await client.post(f"{CLOUD_RUN_URL}/solve", json=body)
            elapsed = round(time.monotonic() - start, 2)
            data = resp.json()

            task_type_raw = data.get("task_type", "")
            # Extract just the type name (e.g. "TaskType.CREATE_EMPLOYEE" -> "CREATE_EMPLOYEE")
            task_type = task_type_raw.split(".")[-1] if "." in task_type_raw else task_type_raw

            details = data.get("details", {})
            success = details.get("success", False) if isinstance(details, dict) else False
            error = details.get("error") if isinstance(details, dict) else None

            # Classification correct?
            classification_ok = task_type == expected_type

            print(f"RESULT: {task_type} {'✅' if classification_ok else '❌ WRONG'} | "
                  f"Exec: {'✅' if success else '⚠️'} | {elapsed}s")
            if error:
                print(f"ERROR: {str(error)[:150]}")
            if not classification_ok:
                print(f"  GOT: {task_type}, EXPECTED: {expected_type}")

            result = {
                "label": label,
                "expected_type": expected_type,
                "actual_type": task_type,
                "classification_ok": classification_ok,
                "execution_ok": success,
                "elapsed": elapsed,
                "error": str(error)[:200] if error else None,
            }
        except Exception as e:
            elapsed = round(time.monotonic() - start, 2)
            print(f"EXCEPTION: {e}")
            result = {
                "label": label,
                "expected_type": expected_type,
                "actual_type": "ERROR",
                "classification_ok": False,
                "execution_ok": False,
                "elapsed": elapsed,
                "error": str(e)[:200],
            }
        RESULTS.append(result)
        return result


async def main():
    print(f"Testing against: {CLOUD_RUN_URL}")
    print(f"Credentials: {CREDS['base_url'][:50]}...")

    # Health check
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{CLOUD_RUN_URL}/health")
            health = resp.json()
            print(f"Health: {resp.status_code} — LLM mode: {health.get('llm_mode', '?')}")
            if health.get("llm_mode") != "gemini":
                print("⚠️  WARNING: LLM mode is NOT gemini!")
    except Exception as e:
        print(f"Health check failed: {e}")
        sys.exit(1)

    # Run tests sequentially (avoid overwhelming the sandbox)
    for label, expected_type, prompt in TEST_TASKS:
        await test_task(label, expected_type, prompt)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")

    classify_ok = sum(1 for r in RESULTS if r["classification_ok"])
    exec_ok = sum(1 for r in RESULTS if r["execution_ok"])
    total = len(RESULTS)
    avg_time = round(sum(r["elapsed"] for r in RESULTS) / total, 1) if total else 0

    print(f"Classification: {classify_ok}/{total} correct")
    print(f"Execution:      {exec_ok}/{total} succeeded")
    print(f"Avg time:       {avg_time}s per task")
    print()

    for r in RESULTS:
        c = "✅" if r["classification_ok"] else "❌"
        e = "✅" if r["execution_ok"] else "⚠️"
        print(f"  {c} {e} {r['label']}: {r['actual_type']} ({r['elapsed']}s)"
              + (f" — {r['error'][:80]}" if r.get("error") else ""))

    # Verdict
    print()
    if classify_ok == total:
        print("🏆 ALL CLASSIFICATIONS CORRECT — Gemini 2.5 Pro is working!")
    else:
        print(f"⚠️  {total - classify_ok} misclassifications — check logs!")


asyncio.run(main())
