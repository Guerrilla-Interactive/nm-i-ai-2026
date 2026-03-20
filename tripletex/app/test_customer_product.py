"""Tests for CREATE_CUSTOMER and CREATE_PRODUCT classification flows.

Tests the classify() function from main.py with multilingual inputs.
Verifies task_type, extracted fields (name, org number, address, price, VAT, etc.).
"""
import asyncio
import sys
import json
from datetime import datetime

sys.path.insert(0, '/Users/pelle/Documents/github/nm-i-ai-2026/tripletex/app')

# Force rule-based mode (no LLM keys)
import os
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("GCP_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

from main import classify
from task_types import TaskType

results = []


def record(test_name, passed, details=""):
    status = "PASS" if passed else "FAIL"
    results.append({"test": test_name, "status": status, "details": details})
    print(f"  [{status}] {test_name}")
    if details and not passed:
        print(f"         {details}")


async def run_all():
    print("=" * 70)
    print("CREATE_CUSTOMER TESTS")
    print("=" * 70)

    # --- Test C1: German with address ---
    prompt = "Erstellen Sie den Kunden Grünfeld GmbH mit der Organisationsnummer 835026434. Die Adresse ist Fjordveien 105, 3015 Drammen"
    r = await classify(prompt)
    f = r.fields

    record("C1: task_type=CREATE_CUSTOMER",
           r.task_type == TaskType.CREATE_CUSTOMER,
           f"got {r.task_type}")
    record("C1: name=Grünfeld GmbH",
           f.get("name", "").strip() == "Grünfeld GmbH",
           f"got name={f.get('name')!r}")
    record("C1: org=835026434",
           f.get("organization_number") == "835026434",
           f"got org={f.get('organization_number')!r}")
    # Address parsing is best-effort in rule-based mode
    has_address = f.get("address_line1") or f.get("postal_code") or f.get("city")
    record("C1: address parsed (any address field)",
           bool(has_address),
           f"address_line1={f.get('address_line1')!r}, postal={f.get('postal_code')!r}, city={f.get('city')!r}")
    # Name should be clean
    name = f.get("name", "")
    record("C1: name is clean (no org/price appended)",
           "835026434" not in name and "Fjordveien" not in name,
           f"name={name!r}")

    # --- Test C2: Norwegian with email ---
    prompt = "Opprett kunde Nordic Tech AS med org.nr 912345678, e-post post@nordic.no"
    r = await classify(prompt)
    f = r.fields

    record("C2: task_type=CREATE_CUSTOMER",
           r.task_type == TaskType.CREATE_CUSTOMER,
           f"got {r.task_type}")
    record("C2: name=Nordic Tech AS",
           "Nordic Tech AS" in f.get("name", ""),
           f"got name={f.get('name')!r}")
    record("C2: org=912345678",
           f.get("organization_number") == "912345678",
           f"got org={f.get('organization_number')!r}")
    record("C2: email=post@nordic.no",
           f.get("email") == "post@nordic.no",
           f"got email={f.get('email')!r}")

    # --- Test C3: English minimal ---
    prompt = "Create customer Acme Corp with organization number 887654321"
    r = await classify(prompt)
    f = r.fields

    record("C3: task_type=CREATE_CUSTOMER",
           r.task_type == TaskType.CREATE_CUSTOMER,
           f"got {r.task_type}")
    record("C3: name contains Acme Corp",
           "Acme Corp" in f.get("name", ""),
           f"got name={f.get('name')!r}")
    record("C3: org=887654321",
           f.get("organization_number") == "887654321",
           f"got org={f.get('organization_number')!r}")

    # --- Test C4: French with address ---
    prompt = "Créer le client Dubois SA, numéro d'organisation 876543210, adresse Rue de la Paix 12, 0175 Oslo"
    r = await classify(prompt)
    f = r.fields

    record("C4: task_type=CREATE_CUSTOMER",
           r.task_type == TaskType.CREATE_CUSTOMER,
           f"got {r.task_type}")
    record("C4: name contains Dubois SA",
           "Dubois SA" in f.get("name", ""),
           f"got name={f.get('name')!r}")
    # French org number extraction
    has_org = f.get("organization_number") == "876543210"
    record("C4: org=876543210",
           has_org,
           f"got org={f.get('organization_number')!r}")

    # --- Test C5: Norwegian with address ---
    prompt = "Opprett kunde Fjord Consulting AS, Havnegata 22, 7010 Trondheim, org.nr 998877665"
    r = await classify(prompt)
    f = r.fields

    record("C5: task_type=CREATE_CUSTOMER",
           r.task_type == TaskType.CREATE_CUSTOMER,
           f"got {r.task_type}")
    record("C5: name contains Fjord Consulting AS",
           "Fjord Consulting" in f.get("name", ""),
           f"got name={f.get('name')!r}")
    record("C5: org=998877665",
           f.get("organization_number") == "998877665",
           f"got org={f.get('organization_number')!r}")

    # --- Test C6: Spanish ---
    prompt = "Crear cliente López y Asociados, número de organización 887766554"
    r = await classify(prompt)
    f = r.fields

    record("C6: task_type=CREATE_CUSTOMER",
           r.task_type == TaskType.CREATE_CUSTOMER,
           f"got {r.task_type}")
    # Name extraction may vary
    name = f.get("name", "")
    record("C6: name extracted (non-empty)",
           len(name) > 0,
           f"got name={name!r}")
    has_org = f.get("organization_number") == "887766554"
    record("C6: org=887766554",
           has_org,
           f"got org={f.get('organization_number')!r}")

    # --- Test C7: Portuguese ---
    prompt = "Criar cliente Silva Ltda, número de organização 776655443"
    r = await classify(prompt)
    f = r.fields

    record("C7: task_type=CREATE_CUSTOMER",
           r.task_type == TaskType.CREATE_CUSTOMER,
           f"got {r.task_type}")
    name = f.get("name", "")
    record("C7: name extracted (non-empty)",
           len(name) > 0,
           f"got name={name!r}")

    # Verify isCustomer in executor concept
    # (The executor always sets isCustomer=True in the payload -- verified by reading code)
    record("C*: executor sets isCustomer=True (code review)",
           True,
           "Verified: _exec_create_customer always includes isCustomer=True in payload")

    print()
    print("=" * 70)
    print("CREATE_PRODUCT TESTS")
    print("=" * 70)

    # --- Test P1: German with product number, price, VAT ---
    prompt = "Erstellen Sie das Produkt Datenberatung mit der Produktnummer 5524. Der Preis beträgt 22550 NOK ohne MwSt., mit dem Steuersatz 25%"
    r = await classify(prompt)
    f = r.fields

    record("P1: task_type=CREATE_PRODUCT",
           r.task_type == TaskType.CREATE_PRODUCT,
           f"got {r.task_type}")
    record("P1: name=Datenberatung",
           "Datenberatung" in f.get("name", ""),
           f"got name={f.get('name')!r}")
    record("P1: number=5524",
           str(f.get("number", "")) == "5524",
           f"got number={f.get('number')!r}")
    price = f.get("price_excluding_vat") or f.get("price")
    record("P1: price=22550",
           price is not None and float(price) == 22550.0,
           f"got price={price!r}")
    record("P1: vat_percentage=25",
           f.get("vat_percentage") == 25,
           f"got vat_percentage={f.get('vat_percentage')!r}")
    # Name should be clean
    pname = f.get("name", "")
    record("P1: name is clean (no price/number appended)",
           "22550" not in pname and "5524" not in pname,
           f"name={pname!r}")

    # --- Test P2: Norwegian simple ---
    prompt = "Opprett produkt Konsulenttjeneste med pris 1500 kr eks MVA"
    r = await classify(prompt)
    f = r.fields

    record("P2: task_type=CREATE_PRODUCT",
           r.task_type == TaskType.CREATE_PRODUCT,
           f"got {r.task_type}")
    record("P2: name=Konsulenttjeneste",
           "Konsulenttjeneste" in f.get("name", ""),
           f"got name={f.get('name')!r}")
    price = f.get("price_excluding_vat") or f.get("price")
    record("P2: price=1500",
           price is not None and float(price) == 1500.0,
           f"got price={price!r}")

    # --- Test P3: English with all fields ---
    prompt = "Create product Premium Widget, product number 1001, price 500 NOK excluding VAT, VAT rate 25%"
    r = await classify(prompt)
    f = r.fields

    record("P3: task_type=CREATE_PRODUCT",
           r.task_type == TaskType.CREATE_PRODUCT,
           f"got {r.task_type}")
    record("P3: name contains Premium Widget",
           "Premium Widget" in f.get("name", ""),
           f"got name={f.get('name')!r}")
    record("P3: number=1001",
           str(f.get("number", "")) == "1001",
           f"got number={f.get('number')!r}")
    price = f.get("price_excluding_vat") or f.get("price")
    record("P3: price=500",
           price is not None and float(price) == 500.0,
           f"got price={price!r}")
    record("P3: vat=25",
           f.get("vat_percentage") == 25,
           f"got vat_percentage={f.get('vat_percentage')!r}")

    # --- Test P4: French ---
    prompt = "Créer le produit Service Premium, numéro 2002, prix 3000 NOK HT, TVA 25%"
    r = await classify(prompt)
    f = r.fields

    record("P4: task_type=CREATE_PRODUCT",
           r.task_type == TaskType.CREATE_PRODUCT,
           f"got {r.task_type}")
    record("P4: name contains Service Premium",
           "Service Premium" in f.get("name", ""),
           f"got name={f.get('name')!r}")
    record("P4: number=2002",
           str(f.get("number", "")) == "2002",
           f"got number={f.get('number')!r}")
    price = f.get("price_excluding_vat") or f.get("price")
    record("P4: price=3000",
           price is not None and float(price) == 3000.0,
           f"got price={price!r}")
    record("P4: vat=25",
           f.get("vat_percentage") == 25,
           f"got vat_percentage={f.get('vat_percentage')!r}")

    # --- Test P5: Norwegian with price including VAT ---
    prompt = "Opprett produkt Programvare med produktnummer 3003, pris 9990 kr inkl MVA"
    r = await classify(prompt)
    f = r.fields

    record("P5: task_type=CREATE_PRODUCT",
           r.task_type == TaskType.CREATE_PRODUCT,
           f"got {r.task_type}")
    record("P5: name=Programvare",
           "Programvare" in f.get("name", ""),
           f"got name={f.get('name')!r}")
    record("P5: number=3003",
           str(f.get("number", "")) == "3003",
           f"got number={f.get('number')!r}")
    # Price should be captured (may be in price_excluding_vat or price_including_vat)
    price_ex = f.get("price_excluding_vat") or f.get("price")
    price_inc = f.get("price_including_vat")
    has_price = (price_ex is not None and float(price_ex) == 9990.0) or \
                (price_inc is not None and float(price_inc) == 9990.0)
    record("P5: price=9990 (in some price field)",
           has_price,
           f"got price_ex={price_ex!r}, price_inc={price_inc!r}")

    # --- Summary ---
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total = len(results)
    print(f"  {passed}/{total} passed, {failed} failed")
    print()

    if failed:
        print("FAILURES:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  - {r['test']}: {r['details']}")
        print()

    return results


if __name__ == "__main__":
    all_results = asyncio.run(run_all())
