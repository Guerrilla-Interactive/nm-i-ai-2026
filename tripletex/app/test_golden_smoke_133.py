#!/usr/bin/env python3
"""Golden smoke tests from 19 real grader prompts (revision tripletex-agent-00133-ckz).

Prompts reconstructed from 120-char previews + extracted fields from golden_grader_data.json.

Usage:
    # Classification only (fast, no API calls)
    python test_golden_smoke_133.py --classify-only

    # Full E2E against local server
    python test_golden_smoke_133.py

    # Full E2E against Cloud Run
    python test_golden_smoke_133.py --endpoint https://tripletex-agent-785696234845.europe-north1.run.app
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def _load_env() -> dict[str, str]:
    env = {}
    for p in [
        str(Path(__file__).resolve().parent.parent / ".env"),
        str(Path(__file__).resolve().parent / ".env"),
    ]:
        if os.path.isfile(p):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, _, v = line.partition("=")
                        env[k.strip()] = v.strip().strip("'\"")
    return env


_env = _load_env()
CREDS = {
    "base_url": os.environ.get("TRIPLETEX_BASE_URL") or _env.get("TRIPLETEX_BASE_URL", ""),
    "session_token": os.environ.get("TRIPLETEX_SESSION_TOKEN") or _env.get("TRIPLETEX_SESSION_TOKEN", ""),
}

# ---------------------------------------------------------------------------
# 19 reconstructed grader prompts from revision 00133
# Format: (index, expected_task_type, prompt, has_files, notes)
# ---------------------------------------------------------------------------

GOLDEN_PROMPTS = [
    # [0] MONTH_END_CLOSING (Nynorsk) — misclassified as RUN_PAYROLL
    (0, "MONTH_END_CLOSING",
     "Gjer månavslutninga for mars 2026. Periodiser forskotsbetalt kostnad (11700 kr per månad frå konto 1720 til kostnadskonto 6300). Rekn ut og bokfør lineære avskrivingar for eit driftsmiddel (anskaffelseskost 468000 kr, levetid 5 år, restverd 0, avskrivingskonto 6010, balanseført på konto 1200).",
     False,
     "Nynorsk month-end: accrual + depreciation. Was misclassified as RUN_PAYROLL."),

    # [1] INVOICE_WITH_PAYMENT (Spanish)
    (1, "INVOICE_WITH_PAYMENT",
     'El cliente Viento SL (org. nº 908616537) tiene una factura pendiente de 37850 NOK sin IVA por "Mantenimiento". Registre el pago completo con fecha de hoy.',
     False,
     "Spanish: unpaid invoice for customer, register payment."),

    # [2] REGISTER_SUPPLIER_INVOICE (French, with PDF)
    (2, "REGISTER_SUPPLIER_INVOICE",
     "Vous avez recu une facture fournisseur (voir PDF ci-joint). Enregistrez la facture dans Tripletex. Creez le fournisseur s'il n'existe pas encore.",
     True,
     "French supplier invoice with PDF attachment. Classify-only (needs file)."),

    # [3] REGISTER_SUPPLIER_INVOICE (French/Portuguese, with receipt)
    (3, "REGISTER_SUPPLIER_INVOICE",
     "Nous avons besoin de la depense Overnatting de ce recu enregistree au departement HR. Utilisez le bon compte de charges et le bon taux de TVA. Fournisseur: Scandic Hotels (org. 940394058). Montant TTC: 3180 NOK, TVA: 795 NOK (25%). Date: 2026-05-07.",
     True,
     "French expense receipt for Scandic Hotels, dept HR."),

    # [4] REGISTER_SUPPLIER_INVOICE (German — was misclassified as CREATE_INVOICE)
    (4, "REGISTER_SUPPLIER_INVOICE",
     "Wir haben die Rechnung INV-2026-8810 vom Lieferanten Sonnental GmbH (Org.-Nr. 988926221) über 8050 NOK einschließlich MwSt. erhalten. Bitte registrieren Sie die Lieferantenrechnung in Tripletex.",
     False,
     "German supplier invoice — Rechnung vom Lieferanten."),

    # [5] INVOICE_WITH_PAYMENT (Norwegian — complex order)
    (5, "INVOICE_WITH_PAYMENT",
     "Opprett en ordre for kunden Snøhetta AS (org.nr 914443806) med produktene Datarådgivning (7906) til 34450 kr og Systemutvikling (7907) til 28500 kr. Fakturer ordren og registrer full betaling med dagens dato.",
     False,
     "Norwegian: create order with 2 products, invoice, register payment."),

    # [6] BANK_RECONCILIATION (English, with CSV)
    (6, "BANK_RECONCILIATION",
     "Reconcile the bank statement (attached CSV) against open invoices in Tripletex. Match incoming payments to customer invoices and outgoing payments to supplier invoices. Use bank account 1920.",
     True,
     "English bank reconciliation with CSV. Classify-only (needs file)."),

    # [7] CREATE_CREDIT_NOTE (French)
    (7, "CREATE_CREDIT_NOTE",
     'Le client Colline SARL (nº org. 879532124) a réclamé concernant la facture pour "Conseil en données" (28600 NOK HT). Émettez une note de crédit complète pour cette facture.',
     False,
     "French credit note for customer complaint."),

    # [8] BANK_RECONCILIATION (French, with CSV — was misclassified)
    (8, "BANK_RECONCILIATION",
     "Rapprochez le releve bancaire (CSV ci-joint) avec les factures ouvertes dans Tripletex. Associez les paiements entrants aux factures clients et les paiements sortants aux factures fournisseurs. Utilisez le compte bancaire 1920.",
     True,
     "French bank reconciliation with CSV. Classify-only (needs file)."),

    # [9] MONTH_END_CLOSING (French)
    (9, "MONTH_END_CLOSING",
     "Effectuez la clôture mensuelle de mars 2026. Comptabilisez la régularisation (13850 NOK par mois du compte 1700 vers charges, compte 6300). Calculez et comptabilisez l'amortissement linéaire pour un actif (coût 554000 NOK, durée 5 ans, valeur résiduelle 0, compte amortissement 6010, compte bilan 1200).",
     False,
     "French month-end: accrual + depreciation."),

    # [10] CREATE_PRODUCT (German)
    (10, "CREATE_PRODUCT",
     'Erstellen Sie das Produkt "Beratungsstunden" mit der Produktnummer 3512. Der Preis beträgt 42600 NOK ohne MwSt., mit dem Standard-Mehrwertsteuersatz.',
     False,
     "German: create product with number and price."),

    # [11] YEAR_END_CLOSING (Nynorsk — was misclassified as ERROR_CORRECTION)
    (11, "YEAR_END_CLOSING",
     "Gjer forenkla årsoppgjer for 2025: 1) Rekn ut og bokfør årlege avskrivingar for tre eigedelar: IT-utstyr (472700 kr, 5 år, lineær, konto 1200/6010), Kontorinventar (285000 kr, 10 år, lineær, konto 1200/6010), Programvare (156000 kr, 3 år, lineær, konto 1200/6010). 2) Overfør årsresultatet til eigenkapital (konto 8800 til 2050). 3) Avslut alle resultatkonti mot konto 8300.",
     False,
     "Nynorsk year-end closing with 3 assets depreciation + equity transfer."),

    # [12] PROJECT_WITH_CUSTOMER (French — complex lifecycle)
    (12, "PROJECT_WITH_CUSTOMER",
     "Exécutez le cycle de vie complet du projet 'Mise à Niveau Système Soleil' (Soleil SARL, nº org. 869871079) : 1) Le projet a un budget de 475350 NOK. 2) Le chef de projet est Gabriel Richard (gabriel.richard@example.org). 3) Enregistrez une facture fournisseur de 93950 NOK de Forêt SARL. 4) Facturez le client pour le montant total et enregistrez le paiement.",
     False,
     "French project lifecycle: create project, supplier invoice, bill customer."),

    # [13] CREATE_EMPLOYEE (Nynorsk, with PDF contract)
    (13, "CREATE_EMPLOYEE",
     "Du har motteke ein arbeidskontrakt (sjaa vedlagt PDF). Opprett den tilsette i Tripletex med alle detaljar fraa kontrakten. Inkluder fornavn, etternavn, e-post, startdato og avdeling.",
     True,
     "Nynorsk: create employee from PDF contract. Classify-only (needs file)."),

    # [14] REGISTER_SUPPLIER_INVOICE (Portuguese, with receipt)
    (14, "REGISTER_SUPPLIER_INVOICE",
     "Precisamos da despesa de Oppbevaringsboks deste recibo registada no departamento Markedsføring. Use a conta de despesas correta e a taxa de IVA correta. Fornecedor: Biltema (org. 827484202). Montante com IVA: 13350 NOK, IVA: 2670 NOK (25%). Data: 2026-01-12.",
     True,
     "Portuguese expense receipt for Biltema, dept Marketing."),

    # [15] CREATE_CUSTOMER (German)
    (15, "CREATE_CUSTOMER",
     "Erstellen Sie den Kunden Grünfeld GmbH mit der Organisationsnummer 835026434. Die Adresse ist Fjordveien 105, 3015 Drammen. E-Mail: post@grunfeld.no. Telefon: +47 32 00 55 00.",
     False,
     "German: create customer with full details."),

    # [16] PROJECT_WITH_CUSTOMER (German — complex lifecycle)
    (16, "PROJECT_WITH_CUSTOMER",
     "Führen Sie den vollständigen Projektzyklus für 'Digitalportal Brückentor' (Brückentor GmbH, Org.-Nr. 952086421) durch: 1) Das Projekt hat ein Budget von 441800 NOK. 2) Projektleiter ist Emma Müller (emma.muller@example.org). 3) Registrieren Sie eine Lieferantenrechnung von 52 Stunden à 1200 NOK von Sonnental GmbH. 4) Fakturieren Sie den Kunden für den Gesamtbetrag und registrieren Sie die Zahlung.",
     False,
     "German project lifecycle: create project, supplier invoice, bill customer."),

    # [17] REGISTER_PAYMENT (Portuguese — overdue invoice reminder)
    (17, "REGISTER_PAYMENT",
     "Um dos seus clientes tem uma fatura vencida. Encontre a fatura vencida e registe uma taxa de lembrete de 35 NOK. Debito na conta 2400, crédito na conta 3400. Envie um lembrete ao cliente.",
     False,
     "Portuguese: find overdue invoice, register reminder fee."),

    # [18] INVOICE_WITH_PAYMENT (German — EUR with exchange rate)
    (18, "INVOICE_WITH_PAYMENT",
     "Wir haben eine Rechnung über 6073 EUR an Flussgold GmbH (Org.-Nr. 849416243) gesendet, als der Wechselkurs 11.50 NOK/EUR war. Der Kunde hat nun bezahlt, aber der aktuelle Kurs ist 11.80 NOK/EUR. Registrieren Sie die Zahlung und buchen Sie die Wechselkursdifferenz.",
     False,
     "German: EUR invoice with exchange rate difference on payment."),
]

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

async def run_one(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    endpoint: str,
    idx: int,
    expected_type: str,
    prompt: str,
    has_files: bool,
    classify_only: bool,
) -> dict:
    """Run a single test case."""
    async with sem:
        creds = CREDS if not classify_only else {
            "base_url": CREDS["base_url"] or "https://tx-proxy.ainm.no/v2",
            "session_token": CREDS["session_token"] or "dry-run-no-token",
        }

        payload = {
            "prompt": prompt,
            "files": [],
            "tripletex_credentials": creds,
        }

        t0 = time.monotonic()
        try:
            resp = await client.post(f"{endpoint.rstrip('/')}/solve", json=payload, timeout=120)
            elapsed = time.monotonic() - t0
            body = resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            elapsed = time.monotonic() - t0
            return {
                "idx": idx, "expected": expected_type, "got": "ERROR",
                "classify_ok": False, "exec_ok": False,
                "elapsed": elapsed, "error": str(e),
            }

        # Normalize task type
        got_type = (body.get("task_type") or "UNKNOWN").upper().replace("TASKTYPE.", "")

        # Aliases
        aliases = {
            "CREATE_SUPPLIER_INVOICE": "REGISTER_SUPPLIER_INVOICE",
        }
        got_cmp = aliases.get(got_type, got_type)
        exp_cmp = aliases.get(expected_type.upper(), expected_type.upper())

        classify_ok = got_cmp == exp_cmp
        exec_ok = body.get("status") == "completed" if not classify_only else None

        return {
            "idx": idx,
            "expected": expected_type,
            "got": got_type,
            "classify_ok": classify_ok,
            "exec_ok": exec_ok,
            "elapsed": elapsed,
            "has_files": has_files,
            "error": body.get("error") or body.get("_error"),
            "http_status": resp.status_code,
        }


async def run_all(endpoint: str, classify_only: bool, concurrency: int) -> list[dict]:
    sem = asyncio.Semaphore(concurrency)
    results = []

    async with httpx.AsyncClient() as client:
        tasks = []
        for idx, expected_type, prompt, has_files, _notes in GOLDEN_PROMPTS:
            # Skip file-dependent prompts in full E2E mode
            skip_exec = has_files and not classify_only
            mode = True if skip_exec else classify_only
            tasks.append(run_one(client, sem, endpoint, idx, expected_type, prompt, has_files, mode))

        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)

    results.sort(key=lambda r: r["idx"])
    return results


def print_results(results: list[dict], classify_only: bool):
    mode = "CLASSIFY-ONLY" if classify_only else "FULL E2E"
    print(f"\n{'=' * 90}")
    print(f"  GOLDEN SMOKE TEST — Rev 00133 ({mode})")
    print(f"  {len(results)} prompts")
    print(f"{'=' * 90}\n")

    print(f"{'#':>3} {'Expected':<35} {'Got':<30} {'Cls':>4} {'Exec':>5} {'Time':>6}")
    print("-" * 90)

    cls_pass = cls_fail = exec_pass = exec_fail = exec_skip = 0

    for r in results:
        cls_mark = " OK " if r["classify_ok"] else "FAIL"
        if r["classify_ok"]:
            cls_pass += 1
        else:
            cls_fail += 1

        if classify_only or r["has_files"]:
            exec_mark = " skip"
            exec_skip += 1
        elif r["exec_ok"]:
            exec_mark = "  OK "
            exec_pass += 1
        else:
            exec_mark = " FAIL"
            exec_fail += 1

        print(f"{r['idx']:>3} {r['expected']:<35} {r['got']:<30} {cls_mark} {exec_mark} {r['elapsed']:>5.1f}s")

    print("-" * 90)
    print(f"Classification: {cls_pass}/{cls_pass + cls_fail} ({100 * cls_pass / (cls_pass + cls_fail):.0f}%)")
    if not classify_only:
        tested = exec_pass + exec_fail
        if tested:
            print(f"Execution:      {exec_pass}/{tested} ({100 * exec_pass / tested:.0f}%) [{exec_skip} skipped — need files]")

    # Show failures
    failures = [r for r in results if not r["classify_ok"]]
    if failures:
        print(f"\nMISCLASSIFICATIONS:")
        for r in failures:
            print(f"  [{r['idx']:>2}] Expected {r['expected']}, got {r['got']}")

    exec_failures = [r for r in results if r["exec_ok"] is False and r["classify_ok"]]
    if exec_failures:
        print(f"\nEXECUTION FAILURES (correctly classified):")
        for r in exec_failures:
            err = (r.get("error") or "")[:100]
            print(f"  [{r['idx']:>2}] {r['expected']}: {err}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Golden smoke tests — rev 00133")
    parser.add_argument("--endpoint", default="http://localhost:8080")
    parser.add_argument("--classify-only", action="store_true")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()

    print(f"Golden Smoke Test: 19 prompts from rev 00133")
    print(f"Endpoint: {args.endpoint}")
    print(f"Mode: {'classify-only' if args.classify_only else 'full E2E'}")

    t0 = time.monotonic()
    results = asyncio.run(run_all(args.endpoint, args.classify_only, args.concurrency))
    elapsed = time.monotonic() - t0

    print_results(results, args.classify_only)
    print(f"Total time: {elapsed:.1f}s")

    # Exit code: 1 if any classification failures
    if any(not r["classify_ok"] for r in results):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
