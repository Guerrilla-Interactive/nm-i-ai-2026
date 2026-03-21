"""Test classifier for Tier 3 task types and regressions.

Run: python3 test_classifier_tier3.py
"""
import os
import sys

# Force rule-based mode — no LLM backends
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("GCP_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_types import TaskType
from classifier import _classify_with_keywords, _last_resort_classify

_PASS = 0
_FAIL = 0


def check(prompt, expected, label=""):
    global _PASS, _FAIL
    result = _classify_with_keywords(prompt)
    tag = f" [{label}]" if label else ""
    if result.task_type == expected:
        _PASS += 1
        print(f"  PASS{tag}: {prompt[:60]!r} → {result.task_type.value}")
    else:
        _FAIL += 1
        print(f"  FAIL{tag}: {prompt[:60]!r} → {result.task_type.value} (expected {expected.value})")


def check_last_resort(prompt, expected, label=""):
    global _PASS, _FAIL
    result = _last_resort_classify(prompt)
    tag = f" [{label}]" if label else ""
    if result.task_type == expected:
        _PASS += 1
        print(f"  PASS{tag} (last_resort): {prompt[:60]!r} → {result.task_type.value}")
    else:
        _FAIL += 1
        print(f"  FAIL{tag} (last_resort): {prompt[:60]!r} → {result.task_type.value} (expected {expected.value})")


print("=" * 70)
print("TIER 3 CLASSIFIER TESTS")
print("=" * 70)

# ── YEAR_END_CLOSING ─────────────────────────────────────────────────
print("\n--- YEAR_END_CLOSING ---")
check("Utfør årsavslutning for 2025", TaskType.YEAR_END_CLOSING, "NO-special")
check("Utfør arsavslutning for 2025", TaskType.YEAR_END_CLOSING, "NO-ascii")
check("Årsoppgjør for regnskap 2025", TaskType.YEAR_END_CLOSING, "NO-special2")
check("Perform year-end closing for 2025", TaskType.YEAR_END_CLOSING, "EN")
check("Jahresabschluss für 2025", TaskType.YEAR_END_CLOSING, "DE")
check("Clôture annuelle pour 2025", TaskType.YEAR_END_CLOSING, "FR")
check("Avslutt år 2025", TaskType.YEAR_END_CLOSING, "NO-variant")
check("Year-end closing procedures for 2025", TaskType.YEAR_END_CLOSING, "EN2")
check_last_resort("Utfør arsavslutning for 2025", TaskType.YEAR_END_CLOSING, "NO-ascii-lastresort")

# ── RUN_PAYROLL ──────────────────────────────────────────────────────
print("\n--- RUN_PAYROLL ---")
check("Kjør lønnskjøring for mars 2026", TaskType.RUN_PAYROLL, "NO-special")
check("Kjor lonnskjoring for mars 2026", TaskType.RUN_PAYROLL, "NO-ascii")
check("Utfør lønn for alle ansatte", TaskType.RUN_PAYROLL, "NO-simple")
check("Run payroll for March 2026", TaskType.RUN_PAYROLL, "EN")
check("Execute payroll for all employees", TaskType.RUN_PAYROLL, "EN2")
check("Exécuter la paie pour mars", TaskType.RUN_PAYROLL, "FR")
check("Lønnsutbetaling for mars", TaskType.RUN_PAYROLL, "NO-utbetaling")
check("Kjør lønn for mars måned", TaskType.RUN_PAYROLL, "NO-lonn")
check_last_resort("Kjor lonnskjoring for mars 2026", TaskType.RUN_PAYROLL, "NO-ascii-lastresort")

# ── ENABLE_MODULE ────────────────────────────────────────────────────
print("\n--- ENABLE_MODULE ---")
check("Aktiver modul Reiseregning", TaskType.ENABLE_MODULE, "NO-travel")
check("Aktiver modulen Prosjekt", TaskType.ENABLE_MODULE, "NO-project")
check("Slå på modul for lønn", TaskType.ENABLE_MODULE, "NO-payroll")
check("Enable module Travel Expense", TaskType.ENABLE_MODULE, "EN")
check("Aktiver modul for prosjekt", TaskType.ENABLE_MODULE, "NO-for-project")
check("Activer le module Frais de voyage", TaskType.ENABLE_MODULE, "FR")
check("Enable module for payroll", TaskType.ENABLE_MODULE, "EN-payroll")
check("Aktiver modul for regnskap", TaskType.ENABLE_MODULE, "NO-regnskap")
check_last_resort("Aktiver modulen Prosjekt", TaskType.ENABLE_MODULE, "NO-project-lastresort")

# ── REGISTER_SUPPLIER_INVOICE ────────────────────────────────────────
print("\n--- REGISTER_SUPPLIER_INVOICE ---")
check("Registrer leverandørfaktura fra Bygg AS", TaskType.REGISTER_SUPPLIER_INVOICE, "NO-special")
check("Registrer leverandorfaktura fra Acme AS på 10000 kr", TaskType.REGISTER_SUPPLIER_INVOICE, "NO-ascii")
check("Bokfør inngående faktura fra Nordic Parts", TaskType.REGISTER_SUPPLIER_INVOICE, "NO-inngaende")
check("Register supplier invoice from Hardware Inc", TaskType.REGISTER_SUPPLIER_INVOICE, "EN")
check("Book incoming invoice from vendor", TaskType.REGISTER_SUPPLIER_INVOICE, "EN-incoming")
check("Eingangsrechnung von Müller GmbH", TaskType.REGISTER_SUPPLIER_INVOICE, "DE")
check("Enregistrer la facture fournisseur de Dupont", TaskType.REGISTER_SUPPLIER_INVOICE, "FR")
check_last_resort("Registrer leverandorfaktura fra Acme AS", TaskType.REGISTER_SUPPLIER_INVOICE, "NO-ascii-lastresort")

# ── REGRESSIONS: existing types should still work ────────────────────
print("\n--- REGRESSIONS ---")
check("Lag en faktura til kunde Test AS for 3 stk varer à 500 kr", TaskType.CREATE_INVOICE, "invoice")
check("Opprett et prosjekt Webside", TaskType.CREATE_PROJECT, "project")
check("Opprett en ansatt med navn Ola Nordmann", TaskType.CREATE_EMPLOYEE, "employee")
check("Opprett kunde Fjord AS", TaskType.CREATE_CUSTOMER, "customer")
check("Opprett en avdeling som heter Salg", TaskType.CREATE_DEPARTMENT, "department")
check("Registrer leverandøren Havbris AS", TaskType.CREATE_SUPPLIER, "supplier")
check("Opprett reiseregning for Per Hansen", TaskType.CREATE_TRAVEL_EXPENSE, "travel")
check("Slett ansatt Ola Nordmann", TaskType.DELETE_EMPLOYEE, "delete-emp")
check("Registrer innbetaling på faktura 10042 med beløp 15000 kr", TaskType.REGISTER_PAYMENT, "payment")
check("Opprett kreditnota for faktura 10055", TaskType.CREATE_CREDIT_NOTE, "credit")

# ── Tricky disambiguation ────────────────────────────────────────────
print("\n--- DISAMBIGUATION ---")
# "Aktiver modul Prosjekt" should NOT be CREATE_PROJECT
check("Aktiver modul Prosjekt", TaskType.ENABLE_MODULE, "modul-not-project")
# "Kjør lønn" should NOT be CREATE_EMPLOYEE
check("Kjør lønn for Kari Hansen", TaskType.RUN_PAYROLL, "lonn-not-employee")
# "leverandørfaktura" should NOT be CREATE_INVOICE
check("Registrer leverandørfaktura fra Acme AS på 5000 kr", TaskType.REGISTER_SUPPLIER_INVOICE, "supplier-inv-not-inv")

print("\n" + "=" * 70)
print(f"RESULTS: {_PASS} passed, {_FAIL} failed, {_PASS + _FAIL} total")
print("=" * 70)
sys.exit(1 if _FAIL > 0 else 0)
