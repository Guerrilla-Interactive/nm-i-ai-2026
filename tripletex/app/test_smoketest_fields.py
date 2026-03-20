"""Smoke tests for field extraction and post-processing functions (~80 cases)."""
import os, sys
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("GCP_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_types import TaskType
from classifier import _post_process_fields, _normalize_fields
from main import _extract_fields_rule_based, _extract_invoice_lines

passed = 0
failed = 0


def check(label, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {label}\n  expected: {expected}\n  actual:   {actual}")


# =====================================================================
# _post_process_fields (20 cases)
# =====================================================================

check("postproc: strip 'named' prefix",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "named Acme AS"})["name"],
      "Acme AS")

check("postproc: strip 'med navn' prefix",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "med navn Test"})["name"],
      "Test")

check("postproc: strip 'called' prefix",
      _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "called BigCo"})["name"],
      "BigCo")

check("postproc: strip 'heter' prefix",
      _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "heter Ola"})["name"],
      "Ola")

check("postproc: strip 'som heter' prefix",
      _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "som heter Firma"})["name"],
      "Firma")

check("postproc: strip 'kalt' prefix",
      _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "kalt Prosjekt"})["name"],
      "Prosjekt")

check("postproc: strip 'med navnet' prefix",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "med navnet HR"})["name"],
      "HR")

check("postproc: strip 'appelé' prefix",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "appelé Marketing"})["name"],
      "Marketing")

check("postproc: price text from product name",
      _post_process_fields(TaskType.CREATE_PRODUCT, {"name": "Widget til 500 kr"})["name"],
      "Widget")

check("postproc: price text 'at' in product",
      _post_process_fields(TaskType.CREATE_PRODUCT, {"name": "Service at 1200 NOK"})["name"],
      "Service")

check("postproc: price text 'for' in product",
      _post_process_fields(TaskType.CREATE_PRODUCT, {"name": "Gadget for 250 kr"})["name"],
      "Gadget")

check("postproc: number text from dept name",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "HR med nummer 40"})["name"],
      "HR")

check("postproc: number text 'with number' from dept",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "Sales with number 50"})["name"],
      "Sales")

check("postproc: number text 'og nummer' from dept",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "IT og nummer 60"})["name"],
      "IT")

check("postproc: email suffix from customer name",
      _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "Acme AS med e-post test@test.no"})["name"],
      "Acme AS")

check("postproc: email suffix 'with email' from name",
      _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "BigCo with email info@big.co"})["name"],
      "BigCo")

check("postproc: trailing comma stripped",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "Acme AS,"})["name"],
      "Acme AS")

check("postproc: trailing period stripped",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "Acme AS."})["name"],
      "Acme AS")

check("postproc: trailing semicolon stripped",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "Acme AS;"})["name"],
      "Acme AS")

check("postproc: no change needed",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "HR"})["name"],
      "HR")

check("postproc: phone suffix stripped from name",
      _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "Acme med telefon 12345678"})["name"],
      "Acme")

check("postproc: only-prefix value removed",
      _post_process_fields(TaskType.CREATE_DEPARTMENT, {"name": "named"}).get("name"),
      None)

check("postproc: non-name fields untouched",
      _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "Test", "email": "a@b.c"})["email"],
      "a@b.c")

check("postproc: price strip only on CREATE_PRODUCT",
      _post_process_fields(TaskType.CREATE_CUSTOMER, {"name": "Widget til 500 kr"})["name"],
      "Widget til 500 kr")


# =====================================================================
# _normalize_fields (20 cases)
# =====================================================================

r = _normalize_fields(TaskType.CREATE_EMPLOYEE, {"employee_identifier": "Ola Nordmann"})
check("normalize: emp name -> first_name", r.get("first_name"), "Ola")
check("normalize: emp name -> last_name", r.get("last_name"), "Nordmann")
check("normalize: employee_identifier removed", "employee_identifier" in r, False)

r = _normalize_fields(TaskType.UPDATE_EMPLOYEE, {"employee_identifier": "12345"})
check("normalize: emp number", r.get("employee_number"), "12345")

r = _normalize_fields(TaskType.UPDATE_EMPLOYEE, {"employee_identifier": "Hansen"})
check("normalize: single name -> last_name", r.get("last_name"), "Hansen")

r = _normalize_fields(TaskType.CREATE_INVOICE, {"customer_identifier": "Acme AS"})
check("normalize: cust -> customer_name", r.get("customer_name"), "Acme AS")
check("normalize: cust -> name", r.get("name"), "Acme AS")
check("normalize: customer_identifier removed", "customer_identifier" in r, False)

r = _normalize_fields(TaskType.REGISTER_PAYMENT, {"invoice_identifier": "10042"})
check("normalize: invoice -> invoice_number", r.get("invoice_number"), "10042")
check("normalize: invoice_identifier removed", "invoice_identifier" in r, False)

r = _normalize_fields(TaskType.CREATE_PROJECT, {"project_identifier": "123"})
check("normalize: proj numeric -> project_id", r.get("project_id"), 123)

r = _normalize_fields(TaskType.CREATE_PROJECT, {"project_identifier": "Nettside"})
check("normalize: proj text -> project_name", r.get("project_name"), "Nettside")
check("normalize: project_identifier removed", "project_identifier" in r, False)

r = _normalize_fields(TaskType.DELETE_TRAVEL_EXPENSE, {"travel_expense_identifier": "11142218"})
check("normalize: te numeric -> travel_expense_id", r.get("travel_expense_id"), 11142218)

r = _normalize_fields(TaskType.DELETE_TRAVEL_EXPENSE, {"travel_expense_identifier": "Trondheim-tur"})
check("normalize: te text -> title", r.get("title"), "Trondheim-tur")
check("normalize: travel_expense_identifier removed", "travel_expense_identifier" in r, False)

r = _normalize_fields(TaskType.CREATE_CUSTOMER, {"organization_number": "922-976-457"})
check("normalize: org_number cleaned", r.get("organization_number"), "922976457")

r = _normalize_fields(TaskType.CREATE_CUSTOMER, {"org_number": "922 976 457"})
check("normalize: org_number alt cleaned", r.get("org_number"), "922976457")

r = _normalize_fields(TaskType.FIND_CUSTOMER, {"search_query": "Acme", "search_field": "name"})
check("normalize: find_customer name", r.get("name"), "Acme")

r = _normalize_fields(TaskType.FIND_CUSTOMER, {"search_query": "922976457", "search_field": "organization_number"})
check("normalize: find_customer org", r.get("org_number"), "922976457")

r = _normalize_fields(TaskType.PROJECT_WITH_CUSTOMER, {"project_name": "Alpha"})
check("normalize: project_with_customer name", r.get("name"), "Alpha")


# =====================================================================
# _extract_fields_rule_based (20 cases)
# =====================================================================

r = _extract_fields_rule_based(TaskType.CREATE_DEPARTMENT, "Opprett avdeling HR med avdelingsnummer 40")
check("rule: dept name", r.get("name"), "HR")
check("rule: dept number", r.get("department_number"), "40")

r = _extract_fields_rule_based(TaskType.CREATE_EMPLOYEE, "Opprett ansatt med fornavn Kari og etternavn Hansen")
check("rule: emp first_name", r.get("first_name"), "Kari")
check("rule: emp last_name", r.get("last_name"), "Hansen")

r = _extract_fields_rule_based(TaskType.CREATE_CUSTOMER, "Create customer Acme AS, email info@acme.no")
check("rule: customer email", r.get("email"), "info@acme.no")

r = _extract_fields_rule_based(TaskType.CREATE_INVOICE, "Lag faktura til kunde Test AS: 3 stk Frakttjeneste til 2500 kr")
check("rule: invoice customer", r.get("customer_name"), "Test AS")
check("rule: invoice has lines", len(r.get("lines", [])), 1)
if r.get("lines"):
    check("rule: invoice line qty", r["lines"][0]["quantity"], 3)
    check("rule: invoice line price", r["lines"][0]["unit_price"], 2500.0)

r = _extract_fields_rule_based(TaskType.CREATE_TRAVEL_EXPENSE, "Opprett reiseregning Oslo-Bergen for ansatt Per Hansen")
check("rule: travel first_name", r.get("first_name"), "Per")
check("rule: travel last_name", r.get("last_name"), "Hansen")

r = _extract_fields_rule_based(TaskType.CREATE_PRODUCT, "Opprett produkt Widget med pris 250 kr")
check("rule: product name", r.get("name"), "Widget")
check("rule: product price", r.get("price_excluding_vat"), 250.0)

r = _extract_fields_rule_based(TaskType.CREATE_EMPLOYEE, "Create employee named Kari Hansen")
check("rule: english emp first", r.get("first_name"), "Kari")
check("rule: english emp last", r.get("last_name"), "Hansen")

r = _extract_fields_rule_based(TaskType.CREATE_DEPARTMENT, "Opprett avdeling Salg med nummer 10")
check("rule: dept name Salg", r.get("name"), "Salg")
check("rule: dept num 10", r.get("department_number"), "10")

r = _extract_fields_rule_based(TaskType.CREATE_CUSTOMER, "Opprett kunde med navn Acme AS og org.nr 922976457")
check("rule: customer org_number", r.get("organization_number"), "922976457")

r = _extract_fields_rule_based(TaskType.CREATE_EMPLOYEE, "Opprett ansatt med fornavn Per og etternavn Olsen, telefon 12345678")
check("rule: emp phone", r.get("phone"), "12345678")


# =====================================================================
# _extract_invoice_lines (16 cases)
# =====================================================================

r = _extract_invoice_lines("3 stk Widget til 500 kr")
check("lines: basic count", len(r), 1)
check("lines: basic desc", r[0]["description"] if r else None, "Widget")
check("lines: basic qty", r[0]["quantity"] if r else None, 3)
check("lines: basic price", r[0]["unit_price"] if r else None, 500.0)

r = _extract_invoice_lines("1 stk Emballasje til 150 kr")
check("lines: single item count", len(r), 1)
check("lines: single desc", r[0]["description"] if r else None, "Emballasje")
check("lines: single price", r[0]["unit_price"] if r else None, 150.0)

r = _extract_invoice_lines("3 stk Widget til 500 kr, 1 stk Emballasje til 150 kr")
check("lines: multiple items", len(r), 2)

r = _extract_invoice_lines("10 timer Konsultering til 1200 kr")
check("lines: time-based count", len(r), 1)
check("lines: time-based desc", r[0]["description"] if r else None, "Konsultering")
check("lines: time-based qty", r[0]["quantity"] if r else None, 10)
check("lines: time-based price", r[0]["unit_price"] if r else None, 1200.0)

r = _extract_invoice_lines("5 pcs Consulting at 900 NOK")
check("lines: english pcs", len(r), 1)
check("lines: english desc", r[0]["description"] if r else None, "Consulting")
check("lines: english price", r[0]["unit_price"] if r else None, 900.0)

r = _extract_invoice_lines("no invoice lines here")
check("lines: no match", len(r), 0)


# =====================================================================
# Summary
# =====================================================================

total = passed + failed
print(f"\n{'='*50}")
print(f"Results: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"FAILURES: {failed}")
    sys.exit(1)
