#!/usr/bin/env python3
"""Test INVOICE_WITH_PAYMENT classification and paid_amount calculation.

Tests the full pipeline: classify prompt -> build order lines -> compute paid_amount.
Does NOT modify any source code. Uses the rule-based classifier (no LLM key needed).
"""
import asyncio
import sys
import os

# Ensure rule-based mode (no LLM)
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("GCP_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)

sys.path.insert(0, "/Users/pelle/Documents/github/nm-i-ai-2026/tripletex/app")

from main import classify
from executor import _build_order_lines
from task_types import TaskType

# Suppress JSON log noise
import main as _main_mod
_main_mod.LLM_MODE = "none"


TEST_CASES = [
    {
        "id": 1,
        "prompt": "Kunden Brattli AS (org.nr 909268265) har en utestående faktura på 31300 kr eksklusiv MVA for 'Konsulenttimer'. Registrer betalingen.",
        "expected_task": TaskType.INVOICE_WITH_PAYMENT,
        "expected_paid": 31300 * 1.25,  # 39125.0
        "description": "Norwegian - single line, ex-VAT amount",
    },
    {
        "id": 2,
        "prompt": "Le client Colline SARL (nº org. 850491941) a une facture impayée de 10550 NOK hors TVA pour 'Heures de conseil'. Enregistrer le paiement",
        "expected_task": TaskType.INVOICE_WITH_PAYMENT,
        "expected_paid": 10550 * 1.25,  # 13187.5
        "description": "French - unpaid invoice, register payment",
    },
    {
        "id": 3,
        "prompt": "Der Kunde Müller GmbH hat eine unbezahlte Rechnung über 5000 NOK exkl. MwSt für Beratung. Zahlung registrieren.",
        "expected_task": TaskType.INVOICE_WITH_PAYMENT,
        "expected_paid": 5000 * 1.25,  # 6250.0
        "description": "German - unpaid invoice, register payment",
    },
    {
        "id": 4,
        "prompt": "Create an invoice for Acme Corp for 3 hours consulting at 1500 NOK/hr, already paid in full",
        "expected_task": TaskType.INVOICE_WITH_PAYMENT,
        "expected_paid": 3 * 1500 * 1.25,  # 5625.0
        "description": "English - hours-based, paid in full",
    },
    {
        "id": 5,
        "prompt": "Opprett faktura til kunde Fjord AS for 5 stk Produkt A til 200 kr og registrer betaling",
        "expected_task": TaskType.INVOICE_WITH_PAYMENT,
        "expected_paid": 5 * 200 * 1.25,  # 1250.0
        "description": "Norwegian - multi-quantity product, register payment",
    },
    {
        "id": 6,
        "prompt": "Faktura til Nordfjord AS: 2 stk Konsulenttjeneste til 1500 kr, betalt",
        "expected_task": TaskType.INVOICE_WITH_PAYMENT,
        "expected_paid": 2 * 1500 * 1.25,  # 3750.0
        "description": "Edge case - short form, 'betalt' signals payment",
    },
]


def compute_paid_amount(order_lines: list[dict]) -> float:
    """Replicate the paid_amount calculation from _exec_invoice_with_payment."""
    computed_total = 0.0
    for ol in order_lines:
        count = ol.get("count", 1.0)
        ex_vat = ol.get("unitPriceExcludingVatCurrency")
        inc_vat = ol.get("unitPriceIncludingVatCurrency")
        if ex_vat:
            computed_total += count * float(ex_vat) * 1.25
        elif inc_vat:
            computed_total += count * float(inc_vat)
    return computed_total


async def run_tests():
    results = []
    print("=" * 80)
    print("INVOICE_WITH_PAYMENT - Classification & Payment Amount Tests")
    print("=" * 80)

    for tc in TEST_CASES:
        print(f"\n--- Test {tc['id']}: {tc['description']} ---")
        print(f"Prompt: {tc['prompt'][:100]}...")

        # Step 1: Classify
        classification = await classify(tc["prompt"], [])
        task_match = classification.task_type == tc["expected_task"]

        print(f"  Task type: {classification.task_type.value} "
              f"({'PASS' if task_match else 'FAIL - expected ' + tc['expected_task'].value})")
        print(f"  Confidence: {classification.confidence}")
        print(f"  Fields: {classification.fields}")

        # Step 2: Build order lines
        order_lines = _build_order_lines(classification.fields)
        print(f"  Order lines: {order_lines}")

        # Step 3: Compute paid amount
        computed_paid = compute_paid_amount(order_lines)
        expected_paid = tc["expected_paid"]
        amount_match = abs(computed_paid - expected_paid) < 0.01

        print(f"  Computed paid_amount: {computed_paid}")
        print(f"  Expected paid_amount: {expected_paid}")
        print(f"  Amount: {'PASS' if amount_match else 'FAIL'}")

        overall = "PASS" if (task_match and amount_match) else "FAIL"
        print(f"  Overall: {overall}")

        results.append({
            "id": tc["id"],
            "description": tc["description"],
            "task_match": task_match,
            "actual_task": classification.task_type.value,
            "expected_task": tc["expected_task"].value,
            "amount_match": amount_match,
            "computed_paid": computed_paid,
            "expected_paid": expected_paid,
            "fields": classification.fields,
            "order_lines": order_lines,
            "overall": overall,
        })

    # Summary
    print("\n" + "=" * 80)
    passed = sum(1 for r in results if r["overall"] == "PASS")
    failed = sum(1 for r in results if r["overall"] == "FAIL")
    print(f"SUMMARY: {passed}/{len(results)} passed, {failed} failed")
    print("=" * 80)

    return results


def write_report(results: list[dict]):
    """Write results to TEST-PAYMENT.md."""
    lines = []
    lines.append("# INVOICE_WITH_PAYMENT Test Results")
    lines.append("")
    lines.append(f"**Date**: 2026-03-20")
    lines.append(f"**Classifier mode**: rule-based (no LLM)")
    lines.append("")

    passed = sum(1 for r in results if r["overall"] == "PASS")
    total = len(results)
    lines.append(f"## Summary: {passed}/{total} passed")
    lines.append("")

    lines.append("| # | Description | Task | Amount | Overall |")
    lines.append("|---|-------------|------|--------|---------|")
    for r in results:
        task_icon = "PASS" if r["task_match"] else "FAIL"
        amt_icon = "PASS" if r["amount_match"] else "FAIL"
        lines.append(
            f"| {r['id']} | {r['description']} | {task_icon} | {amt_icon} | {r['overall']} |"
        )

    lines.append("")
    lines.append("## Detailed Results")
    lines.append("")

    for r in results:
        lines.append(f"### Test {r['id']}: {r['description']}")
        lines.append("")
        lines.append(f"- **Expected task**: `{r['expected_task']}`")
        lines.append(f"- **Actual task**: `{r['actual_task']}` {'PASS' if r['task_match'] else 'FAIL'}")
        lines.append(f"- **Expected paid_amount**: {r['expected_paid']}")
        lines.append(f"- **Computed paid_amount**: {r['computed_paid']} {'PASS' if r['amount_match'] else 'FAIL'}")
        lines.append(f"- **Extracted fields**: `{r['fields']}`")
        lines.append(f"- **Order lines**: `{r['order_lines']}`")
        lines.append("")

    # Analysis of failures
    failures = [r for r in results if r["overall"] == "FAIL"]
    if failures:
        lines.append("## Failure Analysis")
        lines.append("")
        for r in failures:
            lines.append(f"### Test {r['id']}: {r['description']}")
            if not r["task_match"]:
                lines.append(
                    f"- **Classification failure**: Got `{r['actual_task']}`, "
                    f"expected `{r['expected_task']}`. The rule-based classifier may lack "
                    f"patterns for this language/phrasing."
                )
            if not r["amount_match"]:
                lines.append(
                    f"- **Amount calculation failure**: Computed {r['computed_paid']}, "
                    f"expected {r['expected_paid']}. "
                )
                if not r["order_lines"]:
                    lines.append(
                        "  - Root cause: No order lines were extracted from the prompt. "
                        "The line extraction regex did not match."
                    )
                else:
                    lines.append(
                        f"  - Order lines extracted: {r['order_lines']}"
                    )
            lines.append("")

    report = "\n".join(lines) + "\n"
    path = "/Users/pelle/Documents/github/nm-i-ai-2026/tripletex/TEST-PAYMENT.md"
    with open(path, "w") as f:
        f.write(report)
    print(f"\nReport written to {path}")


if __name__ == "__main__":
    results = asyncio.run(run_tests())
    write_report(results)
