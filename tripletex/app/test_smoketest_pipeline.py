"""Smoketest: full classify → execute pipeline with mock client.

Tests the end-to-end flow: classify(prompt) → execute_task(classification, client)
using rule-based classification (no LLM) and a comprehensive mock TripletexClient.
~30 test cases covering T1/T2/T3, crash safety, and coverage checks.
"""
from __future__ import annotations

import os
import sys

# MUST clear LLM env vars BEFORE importing main.py (reads LLM_MODE at import time)
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("GCP_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import traceback
from unittest.mock import AsyncMock, MagicMock
from typing import Any

from task_types import TaskClassification, TaskType, TASK_FIELD_SPECS, TASK_TYPE_DESCRIPTIONS
from executor import execute_task, _EXECUTORS
from main import classify, _KEYWORD_MAP


# ---------------------------------------------------------------------------
# Comprehensive mock client
# ---------------------------------------------------------------------------

def make_mock_client() -> MagicMock:
    """Create a mock TripletexClient that handles ALL methods any executor might call."""
    client = MagicMock()
    client.api_call_count = 0
    client.error_count = 0

    # Department
    client.get_departments = AsyncMock(return_value=[{"id": 1, "name": "General", "version": 1}])
    client.create_department = AsyncMock(return_value={"id": 99, "name": "New Dept", "version": 1})
    client.get_department = AsyncMock(return_value={"id": 1, "name": "General", "version": 1})
    client.update_department = AsyncMock(return_value={"id": 1, "name": "Updated", "version": 2})
    client.delete = AsyncMock(return_value={})

    # Employee
    client.get_employees = AsyncMock(return_value=[
        {"id": 10, "firstName": "Ola", "lastName": "Nordmann", "email": "ola@test.no",
         "version": 1, "department": {"id": 1}, "employments": [{"id": 1}]}
    ])
    client.create_employee = AsyncMock(return_value={"id": 42, "version": 1})
    client.update_employee = AsyncMock(return_value={"id": 10, "version": 2})
    client.delete_employee = AsyncMock(return_value={})
    client.get_employee = AsyncMock(return_value={
        "id": 10, "firstName": "Ola", "lastName": "Nordmann", "email": "ola@test.no",
        "version": 1, "department": {"id": 1}, "employments": [{"id": 1}],
    })

    # Customer
    client.get_customers = AsyncMock(return_value=[
        {"id": 20, "name": "Acme AS", "version": 2, "organizationNumber": "987654321"}
    ])
    client.create_customer = AsyncMock(return_value={"id": 55, "name": "New Customer", "version": 1})
    client.update_customer = AsyncMock(return_value={"id": 20, "version": 3})
    client.delete_customer = AsyncMock(return_value={})

    # Supplier
    client.get_suppliers = AsyncMock(return_value=[
        {"id": 30, "name": "Elektro AS", "version": 1, "organizationNumber": "111222333"}
    ])
    client.create_supplier = AsyncMock(return_value={"id": 31, "name": "New Supplier", "version": 1})
    client.update_supplier = AsyncMock(return_value={"id": 30, "version": 2})
    client.delete_supplier = AsyncMock(return_value={})

    # Product
    client.create_product = AsyncMock(return_value={"id": 40, "version": 1})
    client.get_products = AsyncMock(return_value=[
        {"id": 40, "name": "Widget", "version": 1, "priceExcludingVatCurrency": 100.0}
    ])
    client.get_product = AsyncMock(return_value={
        "id": 40, "name": "Widget", "version": 1, "priceExcludingVatCurrency": 100.0
    })
    client.put = AsyncMock(return_value={"id": 40, "version": 2})

    # VAT
    client.get_vat_types = AsyncMock(return_value=[
        {"id": 3, "name": "Utgående mva høy sats", "percentage": 25.0},
        {"id": 6, "name": "Utgående mva fritak", "percentage": 0.0},
        {"id": 33, "name": "Utgående mva lav sats", "percentage": 12.0},
        {"id": 10, "name": "Inngående mva høy sats", "percentage": 25.0},
    ])

    # Order / Invoice
    client.create_order = AsyncMock(return_value={"id": 100})
    client.invoice_order = AsyncMock(return_value={"id": 200, "invoiceNumber": 1001})
    client.get_invoices = AsyncMock(return_value=[
        {"id": 200, "invoiceNumber": 1001, "amount": 15000, "version": 1,
         "customer": {"id": 20, "name": "Acme AS"}}
    ])
    client.get_invoice = AsyncMock(return_value={
        "id": 200, "invoiceNumber": 1001, "amount": 15000, "version": 1,
        "customer": {"id": 20, "name": "Acme AS"},
        "voucher": {"id": 500},
    })
    client.create_credit_note = AsyncMock(return_value={"id": 201})

    # Ledger / Bank
    client.get_ledger_accounts = AsyncMock(return_value=[
        {"id": 5, "number": 1920, "name": "Bankinnskudd", "version": 0,
         "bankAccountNumber": "12345678903"}
    ])
    client.update_ledger_account = AsyncMock(return_value={})

    # Payment
    client.get_invoice_payment_types = AsyncMock(return_value=[{"id": 7, "name": "Innbetaling"}])
    client.register_payment = AsyncMock(return_value={"id": 500})

    # Travel expense
    client.create_travel_expense = AsyncMock(return_value={"id": 300, "version": 1})
    client.update_travel_expense = AsyncMock(return_value={"id": 300, "version": 2})
    client.create_travel_expense_cost = AsyncMock(return_value={"id": 301})
    client.get_travel_expense_payment_types = AsyncMock(return_value=[{"id": 33998575, "name": "Privat utlegg"}])
    client.get_travel_expenses = AsyncMock(return_value=[
        {"id": 300, "title": "Kundebesøk", "version": 1, "employee": {"id": 10}}
    ])
    client.get_travel_expense = AsyncMock(return_value={
        "id": 300, "title": "Kundebesøk", "version": 1, "employee": {"id": 10}
    })
    client.delete_travel_expense = AsyncMock(return_value={})
    client.create_per_diem_compensation = AsyncMock(return_value={"id": 302})
    client.create_mileage_allowance = AsyncMock(return_value={"id": 303})

    # Contact
    client.create_contact = AsyncMock(return_value={"id": 400, "version": 1})
    client.get_contacts = AsyncMock(return_value=[
        {"id": 400, "firstName": "Erik", "lastName": "Berg", "version": 1,
         "customer": {"id": 20}}
    ])
    client.get_contact = AsyncMock(return_value={
        "id": 400, "firstName": "Erik", "lastName": "Berg", "version": 1,
        "customer": {"id": 20}
    })
    client.update_contact = AsyncMock(return_value={"id": 400, "version": 2})

    # Project
    client.create_project = AsyncMock(return_value={"id": 600, "version": 1})
    client.get_projects = AsyncMock(return_value=[
        {"id": 600, "name": "Test Project", "version": 1}
    ])
    client.get_project = AsyncMock(return_value={
        "id": 600, "name": "Test Project", "version": 1
    })
    client.update_project = AsyncMock(return_value={"id": 600, "version": 2})
    client.delete_project = AsyncMock(return_value={})

    # Activities / Timesheet
    client.get_activities = AsyncMock(return_value=[
        {"id": 50, "name": "Utvikling", "number": 1}
    ])
    client.create_timesheet_entry = AsyncMock(return_value={"id": 700})

    # Voucher
    client.get_voucher_types = AsyncMock(return_value=[
        {"id": 1, "name": "Manuelt bilag"}
    ])
    client.create_voucher = AsyncMock(return_value={"id": 800, "version": 1})
    client.get_vouchers = AsyncMock(return_value=[
        {"id": 800, "number": 1, "date": "2026-03-20", "version": 1,
         "voucherType": {"id": 1}, "postings": []}
    ])
    client.get_voucher = AsyncMock(return_value={
        "id": 800, "number": 1, "date": "2026-03-20", "version": 1,
        "voucherType": {"id": 1}, "postings": []
    })
    client.reverse_voucher = AsyncMock(return_value={"id": 801})
    client.delete_voucher = AsyncMock(return_value={})
    client.get_postings = AsyncMock(return_value=[])

    # Bank reconciliation
    client.create_bank_reconciliation = AsyncMock(return_value={"id": 900})
    client.get_bank_statements = AsyncMock(return_value=[])

    # Annual accounts / Year-end
    client.get_annual_accounts = AsyncMock(return_value=[])
    client.close_annual_account = AsyncMock(return_value={})
    client.update_annual_account = AsyncMock(return_value={})
    client.get_close_group = AsyncMock(return_value=[])

    # Company / Modules
    client.get_company_modules = AsyncMock(return_value={
        "id": 1, "version": 1,
        "moduleaccountinginternal": True,
        "moduletravelexpense": False,
    })
    client.update_company_modules = AsyncMock(return_value={"id": 1, "version": 2})
    client.post = AsyncMock(return_value={})
    client._request = AsyncMock(return_value={
        "id": 1, "name": "Test Company",
    })

    # Salary / Payroll
    client.get_salary_types = AsyncMock(return_value=[
        {"id": 1, "number": "100", "name": "Fastlønn"},
    ])
    client.create_salary_transaction = AsyncMock(return_value={"id": 1100})
    client.get_employments = AsyncMock(return_value=[
        {"id": 1, "employeeId": 10, "startDate": "2020-01-01"}
    ])
    client.create_employment = AsyncMock(return_value={"id": 2})

    return client


# ---------------------------------------------------------------------------
# Results tracking
# ---------------------------------------------------------------------------

results: list[dict] = []


def record(name: str, passed: bool, details: str = ""):
    results.append({"name": name, "passed": passed, "details": details})


# ---------------------------------------------------------------------------
# End-to-end pipeline tests
# ---------------------------------------------------------------------------

async def run_pipeline(prompt: str, expected_type: TaskType, test_name: str):
    """Classify a prompt, then execute with mock client. Verify type and success."""
    try:
        classification = await classify(prompt)
        # classify() may return a list for batches
        if isinstance(classification, list):
            classification = classification[0]

        if classification.task_type != expected_type:
            record(test_name, False,
                   f"Classification: expected {expected_type.value}, got {classification.task_type.value}")
            return

        client = make_mock_client()
        result = await execute_task(classification, client)
        success = result.get("success", False)
        if success:
            record(test_name, True)
        else:
            record(test_name, False, f"Execution failed: {result.get('error', '?')}")
    except Exception as e:
        record(test_name, False, f"Exception: {e}\n{traceback.format_exc()}")


async def test_e2e_t1():
    """T1 end-to-end pipeline tests (5 cases)."""
    await run_pipeline(
        "Opprett ansatt med fornavn Kari og etternavn Hansen, e-post kari@test.no",
        TaskType.CREATE_EMPLOYEE,
        "E2E T1: create employee",
    )
    await run_pipeline(
        "Create customer Nordfjord Consulting AS, org 987654321",
        TaskType.CREATE_CUSTOMER,
        "E2E T1: create customer",
    )
    await run_pipeline(
        "Opprett produkt Frakttjeneste til 2500 kr",
        TaskType.CREATE_PRODUCT,
        "E2E T1: create product",
    )
    await run_pipeline(
        "Opprett avdeling Markedsføring med avdelingsnummer 40",
        TaskType.CREATE_DEPARTMENT,
        "E2E T1: create department",
    )
    await run_pipeline(
        "Slett ansatt Ola Nordmann",
        TaskType.DELETE_EMPLOYEE,
        "E2E T1: delete employee",
    )


async def test_e2e_t2():
    """T2 end-to-end pipeline tests (5 cases)."""
    await run_pipeline(
        "Faktura for kunde Acme AS med 5 stk Widget til 100 kr",
        TaskType.INVOICE_EXISTING_CUSTOMER,
        "E2E T2: invoice existing customer",
    )
    await run_pipeline(
        "Registrer betaling på faktura 10042 med beløp 15000 kr",
        TaskType.REGISTER_PAYMENT,
        "E2E T2: register payment",
    )
    await run_pipeline(
        "Opprett kontaktperson Erik Berg for kunde Aker Solutions",
        TaskType.CREATE_CONTACT,
        "E2E T2: create contact",
    )
    await run_pipeline(
        "Opprett reiseregning for ansatt Per Hansen, tittel Kundebesøk Oslo",
        TaskType.CREATE_TRAVEL_EXPENSE,
        "E2E T2: create travel expense",
    )
    await run_pipeline(
        "Opprett prosjekt Nettside for kunde Digitalbyrå AS, start 2026-04-01",
        TaskType.PROJECT_WITH_CUSTOMER,
        "E2E T2: project with customer",
    )


async def test_e2e_t3():
    """T3 end-to-end pipeline tests (4 cases)."""
    await run_pipeline(
        "Korriger feil i bilag 1234",
        TaskType.ERROR_CORRECTION,
        "E2E T3: error correction",
    )
    await run_pipeline(
        "Utfør årsavslutning for 2025",
        TaskType.YEAR_END_CLOSING,
        "E2E T3: year end closing",
    )
    await run_pipeline(
        "Aktiver modul Reiseregning",
        TaskType.ENABLE_MODULE,
        "E2E T3: enable module",
    )
    await run_pipeline(
        "Bankavsteming for mars 2026",
        TaskType.BANK_RECONCILIATION,
        "E2E T3: bank reconciliation",
    )


# ---------------------------------------------------------------------------
# Additional pipeline tests (to reach ~30 total)
# ---------------------------------------------------------------------------

async def test_e2e_extra():
    """Additional end-to-end tests for more task types (6 cases)."""
    await run_pipeline(
        "Opprett prosjekt Nettsideutvikling med start 2026-04-01",
        TaskType.CREATE_PROJECT,
        "E2E extra: create project",
    )
    await run_pipeline(
        "Opprett kreditnota for faktura 1001",
        TaskType.CREATE_CREDIT_NOTE,
        "E2E extra: create credit note",
    )
    await run_pipeline(
        "Slett prosjekt med navn Test Project",
        TaskType.DELETE_PROJECT,
        "E2E extra: delete project",
    )
    await run_pipeline(
        "Oppdater kunde Acme AS med ny e-post ny@acme.no",
        TaskType.UPDATE_CUSTOMER,
        "E2E extra: update customer",
    )
    await run_pipeline(
        "Logg 8 timer på prosjekt Alpha for ansatt Ola",
        TaskType.LOG_HOURS,
        "E2E extra: log hours",
    )
    await run_pipeline(
        "Finn kunde Nordfjord Consulting",
        TaskType.FIND_CUSTOMER,
        "E2E extra: find customer",
    )


# ---------------------------------------------------------------------------
# Crash safety tests (3 cases)
# ---------------------------------------------------------------------------

async def test_crash_safety():
    """Pipeline should not crash on malformed/empty prompts."""
    # Empty string
    try:
        result = await classify("")
        if isinstance(result, list):
            result = result[0]
        record("Crash safety: empty prompt", True, f"Got type={result.task_type.value}")
    except Exception as e:
        record("Crash safety: empty prompt", False, f"Crashed: {e}")

    # Very long prompt
    try:
        long_prompt = "Opprett ansatt med fornavn Test og etternavn " + "A" * 5000
        result = await classify(long_prompt)
        if isinstance(result, list):
            result = result[0]
        record("Crash safety: very long prompt", True, f"Got type={result.task_type.value}")
    except Exception as e:
        record("Crash safety: very long prompt", False, f"Crashed: {e}")

    # Gibberish prompt → should return UNKNOWN, not crash
    try:
        result = await classify("asdfghjkl zxcvbnm qwerty 12345")
        if isinstance(result, list):
            result = result[0]
        if result.task_type == TaskType.UNKNOWN:
            record("Crash safety: gibberish → UNKNOWN", True)
        else:
            record("Crash safety: gibberish → UNKNOWN", False,
                   f"Got {result.task_type.value} instead of UNKNOWN")
    except Exception as e:
        record("Crash safety: gibberish → UNKNOWN", False, f"Crashed: {e}")


# ---------------------------------------------------------------------------
# Coverage checks (6 cases)
# ---------------------------------------------------------------------------

def test_coverage():
    """Verify every TaskType has entries in _EXECUTORS, TASK_FIELD_SPECS, TASK_TYPE_DESCRIPTIONS."""
    all_types = set(TaskType)

    # 1. Every TaskType in _EXECUTORS
    missing_executors = all_types - set(_EXECUTORS.keys())
    if not missing_executors:
        record("Coverage: all TaskTypes in _EXECUTORS", True)
    else:
        record("Coverage: all TaskTypes in _EXECUTORS", False,
               f"Missing: {[t.value for t in missing_executors]}")

    # 2. Every TaskType in TASK_FIELD_SPECS
    missing_specs = all_types - set(TASK_FIELD_SPECS.keys())
    if not missing_specs:
        record("Coverage: all TaskTypes in TASK_FIELD_SPECS", True)
    else:
        record("Coverage: all TaskTypes in TASK_FIELD_SPECS", False,
               f"Missing: {[t.value for t in missing_specs]}")

    # 3. Every TaskType in TASK_TYPE_DESCRIPTIONS
    missing_descs = all_types - set(TASK_TYPE_DESCRIPTIONS.keys())
    if not missing_descs:
        record("Coverage: all TaskTypes in TASK_TYPE_DESCRIPTIONS", True)
    else:
        record("Coverage: all TaskTypes in TASK_TYPE_DESCRIPTIONS", False,
               f"Missing: {[t.value for t in missing_descs]}")

    # 4. _KEYWORD_MAP covers all non-UNKNOWN TaskTypes
    keyword_types = set(tt for tt, _ in _KEYWORD_MAP)
    non_unknown = all_types - {TaskType.UNKNOWN}
    missing_keywords = non_unknown - keyword_types
    if not missing_keywords:
        record("Coverage: _KEYWORD_MAP covers all non-UNKNOWN types", True)
    else:
        record("Coverage: _KEYWORD_MAP covers all non-UNKNOWN types", False,
               f"Missing: {[t.value for t in missing_keywords]}")

    # 5. _EXECUTORS keys are subset of TaskType enum (no stale keys)
    extra_executors = set(_EXECUTORS.keys()) - all_types
    if not extra_executors:
        record("Coverage: no stale keys in _EXECUTORS", True)
    else:
        record("Coverage: no stale keys in _EXECUTORS", False,
               f"Extra: {[str(t) for t in extra_executors]}")

    # 6. Every executor function is callable
    all_callable = all(callable(fn) for fn in _EXECUTORS.values())
    if all_callable:
        record("Coverage: all executor values are callable", True)
    else:
        non_callable = [k.value for k, v in _EXECUTORS.items() if not callable(v)]
        record("Coverage: all executor values are callable", False,
               f"Non-callable: {non_callable}")


# ---------------------------------------------------------------------------
# Post-processing pipeline tests (4 cases)
# ---------------------------------------------------------------------------

async def test_post_processing():
    """Test that post-processing is applied during classification."""
    from classifier import _post_process_fields, _normalize_fields

    # 1. _post_process_fields cleans name prefixes
    fields = {"name": "named TestProduct"}
    cleaned = _post_process_fields(TaskType.CREATE_PRODUCT, dict(fields))
    has_prefix = cleaned.get("name", "").startswith("named ")
    record("PostProcess: strips 'named' prefix from name",
           not has_prefix,
           f"Got: {cleaned.get('name')}" if has_prefix else "")

    # 2. Full classify applies post-processing (employee name extraction)
    result = await classify("Opprett ansatt med fornavn Kari og etternavn Hansen")
    if isinstance(result, list):
        result = result[0]
    has_first = result.fields.get("first_name") == "Kari"
    has_last = result.fields.get("last_name") == "Hansen"
    record("PostProcess: classify extracts first/last name",
           has_first and has_last,
           f"fields={result.fields}" if not (has_first and has_last) else "")

    # 3. _normalize_fields converts field names
    fields2 = {"customer_name": "Test AS"}
    normalized = _normalize_fields(TaskType.CREATE_INVOICE, dict(fields2))
    record("PostProcess: _normalize_fields preserves customer_name",
           "customer_name" in normalized,
           f"Got keys: {list(normalized.keys())}")

    # 4. Classify with email in prompt keeps email
    result2 = await classify("Opprett ansatt med fornavn Kari og etternavn Hansen, e-post kari@test.no")
    if isinstance(result2, list):
        result2 = result2[0]
    has_email = "email" in result2.fields or "e-post" in str(result2.fields)
    record("PostProcess: classify preserves email from prompt",
           has_email,
           f"fields={result2.fields}" if not has_email else "")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("Smoketest: classify -> execute pipeline")
    print("=" * 70)
    print()

    # End-to-end tests: T1 (5) + T2 (5) + T3 (4) + extra (6) = 20
    await test_e2e_t1()
    await test_e2e_t2()
    await test_e2e_t3()
    await test_e2e_extra()

    # Crash safety (3)
    await test_crash_safety()

    # Coverage checks (6) — sync
    test_coverage()

    # Post-processing (4)
    await test_post_processing()

    # Report
    print()
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)

    for r in results:
        status = "\033[32mPASS\033[0m" if r["passed"] else "\033[31mFAIL\033[0m"
        print(f"  [{status}] {r['name']}")
        if r.get("details") and not r["passed"]:
            for line in r["details"].split("\n")[:5]:
                print(f"         {line}")
    print()
    print("=" * 70)
    color = "\033[32m" if failed == 0 else "\033[31m"
    print(f"  {color}{passed}/{total} passed, {failed} failed\033[0m")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
