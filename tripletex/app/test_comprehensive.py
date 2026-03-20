#!/usr/bin/env python3
"""Comprehensive classifier + field extraction tests for NM i AI 2026 competition.

Run: python test_comprehensive.py
No server or API credentials needed — tests local classification pipeline only.
"""
import os
import sys

# Ensure we can import from the app directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force rule-based mode (no LLM needed for testing)
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("GCP_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

from task_types import TaskType, TASK_FIELD_SPECS, TASK_TYPE_DESCRIPTIONS
from classifier import (
    _classify_with_keywords,
    _last_resort_classify,
    _post_process_fields,
    _normalize_fields,
    _extract_fields_generic,
)

# Track results
_passed = 0
_failed = 0
_errors = []


def check(name: str, condition: bool, detail: str = ""):
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS {name}")
    else:
        _failed += 1
        msg = f"  FAIL {name}" + (f" -- {detail}" if detail else "")
        print(msg)
        _errors.append(msg)


def test_classify(prompt: str, expected_type: TaskType, description: str = ""):
    """Test that a prompt classifies to the expected task type."""
    result = _classify_with_keywords(prompt)
    if result.task_type == TaskType.UNKNOWN:
        result = _last_resort_classify(prompt)
    label = description or f"{expected_type.value}: {prompt[:60]}"
    check(label, result.task_type == expected_type,
          f"got {result.task_type.value}, expected {expected_type.value}")
    return result


def test_field(result, field_name: str, expected_value, description: str = ""):
    """Test that a field has the expected value."""
    actual = result.fields.get(field_name)
    label = description or f"field {field_name}={expected_value}"
    if expected_value is None:
        check(label, actual is None, f"got {actual}")
    elif isinstance(expected_value, float):
        check(label, actual is not None and abs(float(actual) - expected_value) < 0.01,
              f"got {actual}")
    else:
        check(label, str(actual) == str(expected_value), f"got {actual}")


# ============================================================================
# TEST SUITE
# ============================================================================

print("\n" + "="*60)
print("TRIPLETEX CLASSIFIER TEST SUITE -- NM i AI 2026")
print("="*60)

# -- Tier 1 Tests -----------------------------------------------------------

print("\n-- TIER 1: Basic CRUD --")

# Create Employee
r = test_classify("Opprett en ansatt med fornavn Kari og etternavn Hansen, e-post kari@test.no",
                  TaskType.CREATE_EMPLOYEE, "Create employee (Bokmal)")
test_field(r, "first_name", "Kari")
test_field(r, "last_name", "Hansen")

r = test_classify("Create an employee named John Smith with email john@smith.com",
                  TaskType.CREATE_EMPLOYEE, "Create employee (English)")

r = test_classify("Erstellen Sie einen Mitarbeiter namens Hans Mueller",
                  TaskType.CREATE_EMPLOYEE, "Create employee (German)")

# Update Employee
test_classify("Oppdater ansatt Kari Hansen med ny telefon 99887766",
              TaskType.UPDATE_EMPLOYEE, "Update employee (Bokmal)")

# Delete Employee
test_classify("Slett ansatt Ola Nordmann",
              TaskType.DELETE_EMPLOYEE, "Delete employee (Bokmal)")

test_classify("Delete employee John Smith",
              TaskType.DELETE_EMPLOYEE, "Delete employee (English)")

# Set Employee Roles
test_classify("Sett rolle for ansatt Kari Hansen til administrator",
              TaskType.SET_EMPLOYEE_ROLES, "Set employee role (Bokmal)")

# Create Customer
r = test_classify("Opprett kunde Fjord Konsult AS med org.nr 987654321",
                  TaskType.CREATE_CUSTOMER, "Create customer (Bokmal)")
test_field(r, "name", "Fjord Konsult AS")

r = test_classify("Create customer Nordfjord Consulting AS, email post@nordfjord.no",
                  TaskType.CREATE_CUSTOMER, "Create customer (English)")

r = test_classify("Erstellen Sie einen Kunden namens Schmidt GmbH",
                  TaskType.CREATE_CUSTOMER, "Create customer (German)")

# Update Customer
test_classify("Oppdater kunde Nordic Tech AS med ny e-post info@nordictech.no",
              TaskType.UPDATE_CUSTOMER, "Update customer (Bokmal)")

# Create Product
r = test_classify("Opprett produkt Konsulenttjeneste med pris 1500 kr",
                  TaskType.CREATE_PRODUCT, "Create product (Bokmal)")

r = test_classify("Create a product called Premium Support with price 2500 NOK",
                  TaskType.CREATE_PRODUCT, "Create product (English)")

# Create Department
r = test_classify("Opprett avdeling Markedsfoering med avdelingsnummer 40",
                  TaskType.CREATE_DEPARTMENT, "Create department (Bokmal)")
test_field(r, "name", "Markedsfoering")

r = test_classify("Créer un département appelé Finance",
                  TaskType.CREATE_DEPARTMENT, "Create department (French)")

# Create Project
r = test_classify("Opprett prosjekt Nettside Redesign",
                  TaskType.CREATE_PROJECT, "Create project (Bokmal)")

# Create Invoice
r = test_classify("Lag faktura til kunde Hansen AS: 3 stk Frakttjeneste til 2500 kr",
                  TaskType.CREATE_INVOICE, "Create invoice (Bokmal)")
test_field(r, "customer_name", "Hansen AS")

# -- Tier 2 Tests -----------------------------------------------------------

print("\n-- TIER 2: Multi-step workflows --")

# Register Payment
test_classify("Registrer innbetaling paa faktura 10042 med beloep 15000 kr",
              TaskType.REGISTER_PAYMENT, "Register payment (Bokmal)")

# Create Credit Note
test_classify("Opprett kreditnota for faktura 10055",
              TaskType.CREATE_CREDIT_NOTE, "Credit note (Bokmal)")

# Invoice with Payment
test_classify("Opprett faktura med betaling for kunde Acme AS, betalt 5000 kr",
              TaskType.INVOICE_WITH_PAYMENT, "Invoice with payment (Bokmal)")

# Create Travel Expense
test_classify("Registrer reiseregning for ansatt Per Hansen, tittel Kundebesoek Oslo",
              TaskType.CREATE_TRAVEL_EXPENSE, "Create travel expense (Bokmal)")

# Delete Travel Expense
test_classify("Slett reiseregning 11142218",
              TaskType.DELETE_TRAVEL_EXPENSE, "Delete travel expense (Bokmal)")

# Create Contact
test_classify("Opprett kontaktperson Erik Berg for kunde Aker Solutions",
              TaskType.CREATE_CONTACT, "Create contact (Bokmal)")

# Update Contact
test_classify("Oppdater kontaktperson Erik Berg for kunde Aker Solutions",
              TaskType.UPDATE_CONTACT, "Update contact (Bokmal)")

# Find Customer
test_classify("Finn kunde med org.nr 912345678",
              TaskType.FIND_CUSTOMER, "Find customer (Bokmal)")

# Project with Customer
test_classify("Opprett prosjekt Nettside for kunde Digitalbyraa AS",
              TaskType.PROJECT_WITH_CUSTOMER, "Project with customer (Bokmal)")

# Update Project
test_classify("Oppdater prosjekt Nettside med ny startdato",
              TaskType.UPDATE_PROJECT, "Update project (Bokmal)")

# Delete Project
test_classify("Slett prosjekt Nettside Redesign",
              TaskType.DELETE_PROJECT, "Delete project (Bokmal)")

# Log Hours
test_classify("Logg 8 timer paa prosjekt Alpha for ansatt Per Hansen",
              TaskType.LOG_HOURS, "Log hours (Bokmal)")

# Delete Customer
test_classify("Slett kunde Fjord AS",
              TaskType.DELETE_CUSTOMER, "Delete customer (Bokmal)")

# Update Department
test_classify("Oppdater avdeling Salg med nytt navn Marketing",
              TaskType.UPDATE_DEPARTMENT, "Update department (Bokmal)")

# -- Tier 3 Tests -----------------------------------------------------------

print("\n-- TIER 3: Complex scenarios --")

# Bank Reconciliation
test_classify("Bankavsteming for konto 1920 for mars 2026",
              TaskType.BANK_RECONCILIATION, "Bank reconciliation (Bokmal)")

# Error Correction
test_classify("Korriger feil i bilag 1234",
              TaskType.ERROR_CORRECTION, "Error correction (Bokmal)")

# Year-End Closing
test_classify("Utfør årsavslutning for 2025",
              TaskType.YEAR_END_CLOSING, "Year-end closing (Bokmal)")

# Enable Module
test_classify("Aktiver modul Reiseregning",
              TaskType.ENABLE_MODULE, "Enable module (Bokmal)")

test_classify("Enable module Invoicing",
              TaskType.ENABLE_MODULE, "Enable module (English)")

# -- Multilingual Tests -----------------------------------------------------

print("\n-- MULTILINGUAL --")

test_classify("Crear un cliente llamado Empresa SA",
              TaskType.CREATE_CUSTOMER, "Create customer (Spanish)")

test_classify("Criar um funcionário chamado Joao Silva",
              TaskType.CREATE_EMPLOYEE, "Create employee (Portuguese)")

test_classify("Créer un employé appelé Pierre Dupont",
              TaskType.CREATE_EMPLOYEE, "Create employee (French)")

# -- Field Extraction Tests -------------------------------------------------

print("\n-- FIELD EXTRACTION --")

# Post-processing: strip name prefixes
fields = _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "named Fjord AS"})
check("Strip 'named' prefix", fields.get("name") == "Fjord AS",
      f"got {fields.get('name')}")

fields = _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "med navn Test AS"})
check("Strip 'med navn' prefix", fields.get("name") == "Test AS",
      f"got {fields.get('name')}")

# Post-processing: strip price from product names
fields = _post_process_fields(TaskType.CREATE_PRODUCT, {"name": "Widget til 500 kr"})
check("Strip price from product name", fields.get("name") == "Widget",
      f"got {fields.get('name')}")

# Normalization: employee_identifier -> first_name + last_name
fields = _normalize_fields(TaskType.CREATE_EMPLOYEE, {"employee_identifier": "Kari Hansen"})
check("Normalize employee_identifier",
      fields.get("first_name") == "Kari" and fields.get("last_name") == "Hansen",
      f"got first={fields.get('first_name')}, last={fields.get('last_name')}")

# Normalization: org number stripping
fields = _normalize_fields(TaskType.CREATE_CUSTOMER, {"organization_number": "922 976 457"})
check("Normalize org number (spaces)", fields.get("organization_number") == "922976457",
      f"got {fields.get('organization_number')}")

# Normalization: customer_identifier -> customer_name
fields = _normalize_fields(TaskType.UPDATE_CUSTOMER, {"customer_identifier": "Nordic Tech AS"})
check("Normalize customer_identifier",
      fields.get("customer_name") == "Nordic Tech AS",
      f"got {fields.get('customer_name')}")

# Normalization: invoice_identifier -> invoice_number
fields = _normalize_fields(TaskType.REGISTER_PAYMENT, {"invoice_identifier": "10042"})
check("Normalize invoice_identifier",
      fields.get("invoice_number") == "10042",
      f"got {fields.get('invoice_number')}")

# Normalization: project_identifier (numeric) -> project_id
fields = _normalize_fields(TaskType.UPDATE_PROJECT, {"project_identifier": "123"})
check("Normalize project_identifier (numeric)",
      fields.get("project_id") == 123,
      f"got {fields.get('project_id')}")

# Normalization: project_identifier (name) -> project_name
fields = _normalize_fields(TaskType.UPDATE_PROJECT, {"project_identifier": "Nettside"})
check("Normalize project_identifier (name)",
      fields.get("project_name") == "Nettside",
      f"got {fields.get('project_name')}")

# Normalization: travel_expense_identifier (numeric) -> travel_expense_id
fields = _normalize_fields(TaskType.DELETE_TRAVEL_EXPENSE, {"travel_expense_identifier": "11142218"})
check("Normalize travel_expense_identifier (numeric)",
      fields.get("travel_expense_id") == 11142218,
      f"got {fields.get('travel_expense_id')}")

# -- Coverage Check ----------------------------------------------------------

print("\n-- COVERAGE --")

# Check all task types have descriptions
for tt in TaskType:
    if tt == TaskType.UNKNOWN:
        continue
    check(f"Description exists: {tt.value}",
          tt in TASK_TYPE_DESCRIPTIONS and TASK_TYPE_DESCRIPTIONS[tt],
          "missing description")

# Check all task types have field specs
for tt in TaskType:
    check(f"Field spec exists: {tt.value}",
          tt in TASK_FIELD_SPECS,
          "missing field spec")

# ============================================================================
# RESULTS
# ============================================================================

print("\n" + "="*60)
print(f"RESULTS: {_passed} passed, {_failed} failed")
print("="*60)

if _errors:
    print("\nFailed tests:")
    for e in _errors:
        print(e)

sys.exit(1 if _failed > 0 else 0)
