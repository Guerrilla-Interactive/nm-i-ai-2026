"""Test executor payload construction WITHOUT making real API calls.

We mock the TripletexClient so every API method records what was called
and returns minimal valid responses. Then we inspect the payloads.
"""
from __future__ import annotations

import asyncio
import sys
import traceback
from unittest.mock import AsyncMock, MagicMock
from typing import Any

# --- Make imports work ---
sys.path.insert(0, "/Users/pelle/Documents/github/nm-i-ai-2026/tripletex/app")

from task_types import TaskClassification, TaskType
from executor import (
    _exec_create_employee,
    _exec_create_customer,
    _exec_create_product,
    _exec_create_invoice,
    _exec_invoice_with_payment,
    _exec_project_with_customer,
    _exec_create_travel_expense,
    _exec_create_contact,
    _exec_create_department,
    _exec_register_payment,
    _build_order_lines,
    _clean,
    _ref,
    _build_address,
    _today,
)


# ---------------------------------------------------------------------------
# Mock client factory
# ---------------------------------------------------------------------------

def make_mock_client() -> MagicMock:
    """Create a mock TripletexClient that records calls and returns sane defaults."""
    client = MagicMock()
    client.api_call_count = 0
    client.error_count = 0

    # Department
    client.get_departments = AsyncMock(return_value=[{"id": 1, "name": "General"}])
    client.create_department = AsyncMock(return_value={"id": 99, "name": "New Dept"})

    # Employee
    client.get_employees = AsyncMock(return_value=[
        {"id": 10, "firstName": "Ola", "lastName": "Nordmann", "email": "ola@test.no",
         "version": 1, "department": {"id": 1}}
    ])
    client.create_employee = AsyncMock(return_value={"id": 42})

    # Customer
    client.get_customers = AsyncMock(return_value=[
        {"id": 20, "name": "Acme AS", "version": 2}
    ])
    client.create_customer = AsyncMock(return_value={"id": 55, "name": "New Customer"})

    # Product
    client.create_product = AsyncMock(return_value={"id": 30})

    # VAT
    client.get_vat_types = AsyncMock(return_value=[
        {"id": 3, "name": "Utgående mva høy sats", "percentage": 25.0},
        {"id": 6, "name": "Utgående mva fritak", "percentage": 0.0},
        {"id": 33, "name": "Utgående mva lav sats", "percentage": 12.0},
    ])

    # Order / Invoice
    client.create_order = AsyncMock(return_value={"id": 100})
    client.invoice_order = AsyncMock(return_value={"id": 200})

    # Bank account
    client.get_ledger_accounts = AsyncMock(return_value=[
        {"id": 5, "number": 1920, "name": "Bankinnskudd", "version": 0, "bankAccountNumber": "12345678903"}
    ])
    client.update_ledger_account = AsyncMock(return_value={})

    # Payment types
    client.get_invoice_payment_types = AsyncMock(return_value=[{"id": 7, "name": "Innbetaling"}])

    # Travel expense
    client.create_travel_expense = AsyncMock(return_value={"id": 300})
    client.create_travel_expense_cost = AsyncMock(return_value={"id": 301})
    client.get_travel_expense_payment_types = AsyncMock(return_value=[{"id": 33998575, "name": "Privat utlegg"}])

    # Contact
    client.create_contact = AsyncMock(return_value={"id": 400})

    # Invoice lookup
    client.get_invoices = AsyncMock(return_value=[{"id": 200, "invoiceNumber": "1001"}])

    # Payment
    client.register_payment = AsyncMock(return_value={"id": 500})

    # Project
    client.create_project = AsyncMock(return_value={"id": 600})

    return client


# ---------------------------------------------------------------------------
# Test results collector
# ---------------------------------------------------------------------------

results: list[dict] = []

def record(name: str, passed: bool, details: str = "", findings: list[str] | None = None):
    results.append({"name": name, "passed": passed, "details": details, "findings": findings or []})


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

def test_helpers():
    # _clean removes None values
    assert _clean({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}
    record("_clean removes None", True)

    # _ref
    assert _ref(5) == {"id": 5}
    assert _ref(None) is None
    assert _ref("10") == {"id": 10}  # coerced to int
    record("_ref produces correct refs", True)

    # _build_address
    addr = _build_address({"address_line1": "Gate 1", "postal_code": "0150", "city": "Oslo"})
    assert addr == {"addressLine1": "Gate 1", "postalCode": "0150", "city": "Oslo"}
    assert _build_address({}) is None
    record("_build_address maps fields correctly", True)

    # _today returns ISO date
    today = _today()
    assert len(today) == 10 and today[4] == "-"
    record("_today returns ISO date", True)


# ---------------------------------------------------------------------------
# 1. _exec_create_employee
# ---------------------------------------------------------------------------

async def test_create_employee():
    client = make_mock_client()
    fields = {
        "first_name": "Kari",
        "last_name": "Hansen",
        "email": "kari@example.com",
        "user_type": "administrator",  # should map to EXTENDED
        "department_name": "Salg",
        "phone": "99887766",
        "date_of_birth": "1990-05-15",
    }
    await _exec_create_employee(fields, client)
    payload = client.create_employee.call_args[0][0]

    findings = []

    # No startDate field
    if "startDate" in payload:
        findings.append("FAIL: startDate present in payload (should NOT be)")
    else:
        findings.append("OK: No startDate field in payload")

    # userType mapping
    if payload.get("userType") == "EXTENDED":
        findings.append("OK: 'administrator' mapped to 'EXTENDED'")
    else:
        findings.append(f"FAIL: userType is '{payload.get('userType')}', expected 'EXTENDED'")

    # Required fields present
    for f in ["firstName", "lastName", "email", "userType", "department"]:
        if f in payload:
            findings.append(f"OK: '{f}' present")
        else:
            findings.append(f"FAIL: '{f}' missing from payload")

    # department is a ref
    dept = payload.get("department")
    if isinstance(dept, dict) and "id" in dept and isinstance(dept["id"], int):
        findings.append("OK: department is {\"id\": int}")
    else:
        findings.append(f"FAIL: department format wrong: {dept}")

    # phone mapped correctly
    if payload.get("phoneNumberMobile") == "99887766":
        findings.append("OK: phone mapped to phoneNumberMobile")
    else:
        findings.append(f"FAIL: phoneNumberMobile is '{payload.get('phoneNumberMobile')}'")

    # Test auto-generated email when not provided
    client2 = make_mock_client()
    fields2 = {"first_name": "Per", "last_name": "Olsen"}
    await _exec_create_employee(fields2, client2)
    payload2 = client2.create_employee.call_args[0][0]
    if payload2.get("email") == "per.olsen@example.com":
        findings.append("OK: Auto-generated email 'per.olsen@example.com'")
    else:
        findings.append(f"FAIL: Auto email is '{payload2.get('email')}'")

    # Test user_type mapping: ADMIN -> EXTENDED
    client3 = make_mock_client()
    fields3 = {"first_name": "X", "last_name": "Y", "user_type": "ADMIN"}
    await _exec_create_employee(fields3, client3)
    p3 = client3.create_employee.call_args[0][0]
    if p3["userType"] == "EXTENDED":
        findings.append("OK: 'ADMIN' mapped to 'EXTENDED'")
    else:
        findings.append(f"FAIL: 'ADMIN' mapped to '{p3['userType']}'")

    # Test user_type mapping: RESTRICTED -> NO_ACCESS
    client4 = make_mock_client()
    fields4 = {"first_name": "X", "last_name": "Y", "user_type": "RESTRICTED"}
    await _exec_create_employee(fields4, client4)
    p4 = client4.create_employee.call_args[0][0]
    if p4["userType"] == "NO_ACCESS":
        findings.append("OK: 'RESTRICTED' mapped to 'NO_ACCESS'")
    else:
        findings.append(f"FAIL: 'RESTRICTED' mapped to '{p4['userType']}'")

    # Test invalid user_type falls back to STANDARD
    client5 = make_mock_client()
    fields5 = {"first_name": "X", "last_name": "Y", "user_type": "SUPERUSER"}
    await _exec_create_employee(fields5, client5)
    p5 = client5.create_employee.call_args[0][0]
    if p5["userType"] == "STANDARD":
        findings.append("OK: Invalid type 'SUPERUSER' falls back to 'STANDARD'")
    else:
        findings.append(f"FAIL: Invalid type mapped to '{p5['userType']}'")

    all_ok = all("FAIL" not in f for f in findings)
    record("1. _exec_create_employee", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# 2. _exec_create_customer
# ---------------------------------------------------------------------------

async def test_create_customer():
    client = make_mock_client()
    fields = {
        "name": "Norsk Bedrift AS",
        "organization_number": "987654321",
        "email": "post@norskbedrift.no",
        "phone": "22334455",
        "address_line1": "Storgata 1",
        "postal_code": "0155",
        "city": "Oslo",
        "website": "https://norskbedrift.no",
        "is_private_individual": False,
    }
    await _exec_create_customer(fields, client)
    payload = client.create_customer.call_args[0][0]

    findings = []

    # Check org number field name
    if "organizationNumber" in payload:
        findings.append(f"OK: organizationNumber = '{payload['organizationNumber']}'")
    else:
        findings.append("FAIL: organizationNumber missing")

    # Address is postalAddress
    if "postalAddress" in payload:
        addr = payload["postalAddress"]
        if addr.get("addressLine1") == "Storgata 1":
            findings.append("OK: postalAddress.addressLine1 correct")
        else:
            findings.append(f"FAIL: postalAddress.addressLine1 = '{addr.get('addressLine1')}'")
    else:
        findings.append("FAIL: postalAddress missing")

    # isCustomer=true should be present (marks entity as customer vs supplier)
    if payload.get("isCustomer") is True:
        findings.append("OK: isCustomer = True (distinguishes from supplier)")
    else:
        findings.append("FAIL: isCustomer missing or not True")

    # Required field: name
    if payload.get("name") == "Norsk Bedrift AS":
        findings.append("OK: name present and correct")
    else:
        findings.append(f"FAIL: name = '{payload.get('name')}'")

    # Check no invalid/unknown fields
    valid_fields = {
        "name", "organizationNumber", "email", "invoiceEmail", "phoneNumber",
        "phoneNumberMobile", "isCustomer", "isPrivateIndividual", "invoiceSendMethod",
        "invoicesDueIn", "invoicesDueInType", "postalAddress", "description",
        "website", "language", "currency",
    }
    unknown = set(payload.keys()) - valid_fields
    if unknown:
        findings.append(f"WARN: Unknown fields in payload: {unknown}")
    else:
        findings.append("OK: No unknown fields in payload")

    # phone -> phoneNumber mapping
    if payload.get("phoneNumber") == "22334455":
        findings.append("OK: phone mapped to phoneNumber")
    else:
        findings.append(f"FAIL: phoneNumber = '{payload.get('phoneNumber')}'")

    # Test with org_number alias
    client2 = make_mock_client()
    fields2 = {"name": "Test", "org_number": "111222333"}
    await _exec_create_customer(fields2, client2)
    p2 = client2.create_customer.call_args[0][0]
    if p2.get("organizationNumber") == "111222333":
        findings.append("OK: org_number alias works")
    else:
        findings.append(f"FAIL: org_number alias gave '{p2.get('organizationNumber')}'")

    all_ok = all("FAIL" not in f for f in findings)
    record("2. _exec_create_customer", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# 3. _exec_create_product
# ---------------------------------------------------------------------------

async def test_create_product():
    client = make_mock_client()
    fields = {
        "name": "Konsulenttimer",
        "price": 1500.0,
        "description": "Konsulentarbeid per time",
        "vat_percentage": "25",
    }
    await _exec_create_product(fields, client)
    payload = client.create_product.call_args[0][0]

    findings = []

    # VAT type resolved
    vat = payload.get("vatType")
    if isinstance(vat, dict) and "id" in vat:
        findings.append(f"OK: vatType = {vat}")
        if isinstance(vat["id"], int):
            findings.append("OK: vatType.id is int")
        else:
            findings.append(f"FAIL: vatType.id type is {type(vat['id'])}")
    else:
        findings.append(f"FAIL: vatType format wrong: {vat}")

    # VAT type lookup was called with outgoing
    vat_call = client.get_vat_types.call_args
    if vat_call and vat_call[0][0].get("typeOfVat") == "outgoing":
        findings.append("OK: VAT lookup uses typeOfVat=outgoing")
    else:
        findings.append(f"FAIL: VAT lookup params: {vat_call}")

    # Price field: priceExcludingVatCurrency
    if "priceExcludingVatCurrency" in payload:
        findings.append(f"OK: priceExcludingVatCurrency = {payload['priceExcludingVatCurrency']}")
    else:
        findings.append("FAIL: priceExcludingVatCurrency missing")

    # Name present
    if payload.get("name") == "Konsulenttimer":
        findings.append("OK: name correct")
    else:
        findings.append(f"FAIL: name = '{payload.get('name')}'")

    # Test with 0% VAT
    client2 = make_mock_client()
    client2.get_vat_types = AsyncMock(return_value=[
        {"id": 6, "name": "Utgående mva fritak", "percentage": 0.0},
    ])
    fields2 = {"name": "Fritak-produkt", "price": 100, "vat_percentage": "0"}
    await _exec_create_product(fields2, client2)
    p2 = client2.create_product.call_args[0][0]
    if p2.get("vatType", {}).get("id") == 6:
        findings.append("OK: 0% VAT resolves to id=6")
    else:
        findings.append(f"FAIL: 0% VAT resolved to {p2.get('vatType')}")

    # Test with no VAT specified (defaults to 25%)
    client3 = make_mock_client()
    fields3 = {"name": "Default VAT product", "price": 200}
    await _exec_create_product(fields3, client3)
    p3 = client3.create_product.call_args[0][0]
    if p3.get("vatType", {}).get("id") == 3:
        findings.append("OK: No VAT specified defaults to 25% (id=3)")
    else:
        findings.append(f"FAIL: Default VAT resolved to {p3.get('vatType')}")

    # Check valid fields only
    valid_fields = {
        "name", "number", "description", "priceExcludingVatCurrency",
        "priceIncludingVatCurrency", "costExcludingVatCurrency",
        "vatType", "currency", "productUnit", "department",
    }
    unknown = set(payload.keys()) - valid_fields
    if unknown:
        findings.append(f"WARN: Unknown fields: {unknown}")
    else:
        findings.append("OK: No unknown fields")

    all_ok = all("FAIL" not in f for f in findings)
    record("3. _exec_create_product", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# 4. _exec_create_invoice
# ---------------------------------------------------------------------------

async def test_create_invoice():
    client = make_mock_client()
    fields = {
        "customer_name": "Acme AS",
        "invoice_date": "2026-03-20",
        "lines": [
            {"description": "Konsulentarbeid", "quantity": 10, "unit_price": 1500},
            {"product_name": "Support", "quantity": 1, "unit_price": 500},
        ],
        "comment": "Faktura mars 2026",
    }
    await _exec_create_invoice(fields, client)

    # Check order creation payload
    order_payload = client.create_order.call_args[0][0]

    findings = []

    # Customer ref
    cust = order_payload.get("customer")
    if isinstance(cust, dict) and cust.get("id") == 20:
        findings.append("OK: customer ref = {\"id\": 20}")
    else:
        findings.append(f"FAIL: customer ref = {cust}")

    # orderDate
    if order_payload.get("orderDate") == "2026-03-20":
        findings.append("OK: orderDate correct")
    else:
        findings.append(f"FAIL: orderDate = '{order_payload.get('orderDate')}'")

    # deliveryDate
    if order_payload.get("deliveryDate") == "2026-03-20":
        findings.append("OK: deliveryDate set")
    else:
        findings.append(f"FAIL: deliveryDate = '{order_payload.get('deliveryDate')}'")

    # orderLines
    lines = order_payload.get("orderLines", [])
    if len(lines) == 2:
        findings.append("OK: 2 orderLines")
    else:
        findings.append(f"FAIL: {len(lines)} orderLines, expected 2")

    # First line structure
    line0 = lines[0] if lines else {}
    if line0.get("count") == 10.0:
        findings.append("OK: line[0].count = 10.0 (float)")
    else:
        findings.append(f"FAIL: line[0].count = {line0.get('count')}")

    if line0.get("unitPriceExcludingVatCurrency") == 1500.0:
        findings.append("OK: line[0].unitPriceExcludingVatCurrency = 1500.0")
    else:
        findings.append(f"FAIL: line[0].price = {line0.get('unitPriceExcludingVatCurrency')}")

    if line0.get("description") == "Konsulentarbeid":
        findings.append("OK: line[0].description correct")
    else:
        findings.append(f"FAIL: line[0].description = '{line0.get('description')}'")

    # invoiceComment
    if order_payload.get("invoiceComment") == "Faktura mars 2026":
        findings.append("OK: invoiceComment present")
    else:
        findings.append(f"FAIL: invoiceComment = '{order_payload.get('invoiceComment')}'")

    # Invoice call
    invoice_params = client.invoice_order.call_args[0][1] if client.invoice_order.call_args else {}
    if invoice_params.get("invoiceDate") == "2026-03-20":
        findings.append("OK: invoice invoiceDate correct")
    else:
        findings.append(f"FAIL: invoice params = {invoice_params}")

    # Order -> invoice flow: order_id passed to invoice_order
    order_id_arg = client.invoice_order.call_args[0][0]
    if order_id_arg == 100:
        findings.append("OK: invoice_order called with order_id=100")
    else:
        findings.append(f"FAIL: invoice_order called with order_id={order_id_arg}")

    # Bank account ensured before invoice
    assert client.get_ledger_accounts.called
    findings.append("OK: Bank account check performed before invoice")

    all_ok = all("FAIL" not in f for f in findings)
    record("4. _exec_create_invoice", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# 5. _exec_invoice_with_payment
# ---------------------------------------------------------------------------

async def test_invoice_with_payment():
    client = make_mock_client()
    fields = {
        "customer_name": "Acme AS",
        "lines": [
            {"description": "Produkt A", "quantity": 2, "unit_price": 1000},
        ],
        "invoice_date": "2026-03-20",
        # No paid_amount specified — should auto-calculate
    }
    await _exec_invoice_with_payment(fields, client)

    findings = []

    # Check that paid_amount was auto-calculated: 2 * 1000 * 1.25 = 2500
    invoice_params = client.invoice_order.call_args[0][1]
    paid = invoice_params.get("paidAmount")
    if paid == "2500.0":
        findings.append("OK: Auto-calculated paidAmount = 2500.0 (2*1000 * 1.25 VAT)")
    else:
        findings.append(f"FAIL: paidAmount = '{paid}', expected '2500.0'")

    # paymentTypeId should be string
    pt = invoice_params.get("paymentTypeId")
    if pt == "7":
        findings.append("OK: paymentTypeId = '7' (string)")
    else:
        findings.append(f"FAIL: paymentTypeId = '{pt}'")

    # Test with explicit paid_amount
    client2 = make_mock_client()
    fields2 = {
        "customer_name": "Acme AS",
        "lines": [{"description": "X", "quantity": 1, "unit_price": 500}],
        "paid_amount": 625,  # 500 * 1.25
    }
    await _exec_invoice_with_payment(fields2, client2)
    ip2 = client2.invoice_order.call_args[0][1]
    if ip2.get("paidAmount") == "625.0":
        findings.append("OK: Explicit paid_amount = 625.0 used")
    else:
        findings.append(f"FAIL: Explicit paid_amount = '{ip2.get('paidAmount')}'")

    # Test with price_including_vat (no VAT multiplier should be applied)
    client3 = make_mock_client()
    fields3 = {
        "customer_name": "Acme AS",
        "lines": [{"description": "Y", "quantity": 1, "unit_price_including_vat": 1250}],
    }
    await _exec_invoice_with_payment(fields3, client3)
    ip3 = client3.invoice_order.call_args[0][1]
    pa3 = ip3.get("paidAmount")
    if pa3 == "1250.0":
        findings.append("OK: price_including_vat: no VAT multiplier applied, paidAmount=1250.0")
    else:
        findings.append(f"FAIL: price_including_vat paidAmount = '{pa3}', expected '1250.0'")

    # sendToCustomer should be "false"
    if invoice_params.get("sendToCustomer") == "false":
        findings.append("OK: sendToCustomer = 'false'")
    else:
        findings.append(f"FAIL: sendToCustomer = '{invoice_params.get('sendToCustomer')}'")

    all_ok = all("FAIL" not in f for f in findings)
    record("5. _exec_invoice_with_payment", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# 6. _exec_project_with_customer
# ---------------------------------------------------------------------------

async def test_project_with_customer():
    client = make_mock_client()
    # Customer not found -> will be created
    client.get_customers = AsyncMock(return_value=[])
    client.create_customer = AsyncMock(return_value={"id": 55, "name": "Ny Kunde"})

    fields = {
        "customer_name": "Ny Kunde",
        "name": "Prosjekt Alpha",
        "start_date": "2026-04-01",
        "project_manager_name": "Ola Nordmann",
        "organization_number": "123456789",
    }
    await _exec_project_with_customer(fields, client)

    findings = []

    # Customer was created (since lookup returned empty)
    if client.create_customer.called:
        cust_payload = client.create_customer.call_args[0][0]
        if cust_payload.get("name") == "Ny Kunde":
            findings.append("OK: Customer created with name 'Ny Kunde'")
        else:
            findings.append(f"FAIL: Customer name = '{cust_payload.get('name')}'")
        if cust_payload.get("organizationNumber") == "123456789":
            findings.append("OK: Customer org number passed through")
        else:
            findings.append(f"NOTE: Customer org number = '{cust_payload.get('organizationNumber')}'")
    else:
        findings.append("FAIL: Customer not created when lookup returned empty")

    # Project creation
    if client.create_project.called:
        proj_payload = client.create_project.call_args[0][0]

        if proj_payload.get("name") == "Prosjekt Alpha":
            findings.append("OK: Project name correct")
        else:
            findings.append(f"FAIL: Project name = '{proj_payload.get('name')}'")

        # Customer linked via ref
        cref = proj_payload.get("customer")
        if isinstance(cref, dict) and cref.get("id") == 55:
            findings.append("OK: Project linked to customer id=55")
        else:
            findings.append(f"FAIL: Project customer ref = {cref}")

        # projectManager is a ref
        pm = proj_payload.get("projectManager")
        if isinstance(pm, dict) and "id" in pm:
            findings.append(f"OK: projectManager = {pm}")
        else:
            findings.append(f"FAIL: projectManager = {pm}")

        # startDate
        if proj_payload.get("startDate") == "2026-04-01":
            findings.append("OK: startDate correct")
        else:
            findings.append(f"FAIL: startDate = '{proj_payload.get('startDate')}'")
    else:
        findings.append("FAIL: create_project not called")

    all_ok = all("FAIL" not in f for f in findings)
    record("6. _exec_project_with_customer", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# 7. _exec_create_travel_expense
# ---------------------------------------------------------------------------

async def test_create_travel_expense():
    client = make_mock_client()
    fields = {
        "first_name": "Ola",
        "last_name": "Nordmann",
        "title": "Kundebesøk Bergen",
        "departure_date": "2026-04-10",
        "return_date": "2026-04-11",
        "departure_from": "Oslo",
        "destination": "Bergen",
        "purpose": "Kundemøte",
        "is_day_trip": False,
        "costs": [
            {"amount": 450.0, "date": "2026-04-10"},
        ],
    }
    await _exec_create_travel_expense(fields, client)

    findings = []

    # Main travel expense payload
    te_payload = client.create_travel_expense.call_args[0][0]

    # employee ref
    emp = te_payload.get("employee")
    if isinstance(emp, dict) and emp.get("id") == 10:
        findings.append("OK: employee ref = {\"id\": 10}")
    else:
        findings.append(f"FAIL: employee ref = {emp}")

    # title
    if te_payload.get("title") == "Kundebesøk Bergen":
        findings.append("OK: title correct")
    else:
        findings.append(f"FAIL: title = '{te_payload.get('title')}'")

    # travelDetails present and well-formed
    td = te_payload.get("travelDetails")
    if td:
        findings.append("OK: travelDetails present")
        if td.get("departureDate") == "2026-04-10":
            findings.append("OK: travelDetails.departureDate correct")
        else:
            findings.append(f"FAIL: departureDate = '{td.get('departureDate')}'")
        if td.get("returnDate") == "2026-04-11":
            findings.append("OK: travelDetails.returnDate correct")
        else:
            findings.append(f"FAIL: returnDate = '{td.get('returnDate')}'")
        if td.get("destination") == "Bergen":
            findings.append("OK: travelDetails.destination correct")
        else:
            findings.append(f"FAIL: destination = '{td.get('destination')}'")
        if td.get("departureFrom") == "Oslo":
            findings.append("OK: travelDetails.departureFrom correct")
        else:
            findings.append(f"FAIL: departureFrom = '{td.get('departureFrom')}'")
        if td.get("purpose") == "Kundemøte":
            findings.append("OK: travelDetails.purpose correct")
        else:
            findings.append(f"FAIL: purpose = '{td.get('purpose')}'")
        if td.get("isDayTrip") is False:
            findings.append("OK: travelDetails.isDayTrip = False")
        elif "isDayTrip" not in td:
            findings.append("NOTE: isDayTrip not in travelDetails (cleaned as None?)")
        else:
            findings.append(f"FAIL: isDayTrip = {td.get('isDayTrip')}")
    else:
        findings.append("FAIL: travelDetails missing from payload")

    # Cost line was created
    if client.create_travel_expense_cost.called:
        cost_payload = client.create_travel_expense_cost.call_args[0][0]
        if cost_payload.get("amountCurrencyIncVat") == 450.0:
            findings.append("OK: cost amountCurrencyIncVat = 450.0")
        else:
            findings.append(f"FAIL: cost amount = {cost_payload.get('amountCurrencyIncVat')}")

        te_ref = cost_payload.get("travelExpense")
        if isinstance(te_ref, dict) and te_ref.get("id") == 300:
            findings.append("OK: cost.travelExpense ref = {\"id\": 300}")
        else:
            findings.append(f"FAIL: cost.travelExpense = {te_ref}")

        pt_ref = cost_payload.get("paymentType")
        if isinstance(pt_ref, dict) and "id" in pt_ref:
            findings.append(f"OK: cost.paymentType = {pt_ref}")
        else:
            findings.append(f"FAIL: cost.paymentType = {pt_ref}")
    else:
        findings.append("FAIL: create_travel_expense_cost not called")

    all_ok = all("FAIL" not in f for f in findings)
    record("7. _exec_create_travel_expense", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# 8. _exec_create_contact
# ---------------------------------------------------------------------------

async def test_create_contact():
    client = make_mock_client()
    fields = {
        "first_name": "Erik",
        "last_name": "Svendsen",
        "email": "erik@acme.no",
        "phone": "98765432",
        "customer_name": "Acme AS",
    }
    await _exec_create_contact(fields, client)
    payload = client.create_contact.call_args[0][0]

    findings = []

    # Customer lookup happened
    if client.get_customers.called:
        findings.append("OK: Customer lookup performed")
    else:
        findings.append("FAIL: Customer lookup not performed")

    # customer ref in payload
    cref = payload.get("customer")
    if isinstance(cref, dict) and cref.get("id") == 20:
        findings.append("OK: customer ref = {\"id\": 20}")
    else:
        findings.append(f"FAIL: customer ref = {cref}")

    # Fields
    for key, expected in [("firstName", "Erik"), ("lastName", "Svendsen"), ("email", "erik@acme.no")]:
        if payload.get(key) == expected:
            findings.append(f"OK: {key} = '{expected}'")
        else:
            findings.append(f"FAIL: {key} = '{payload.get(key)}'")

    # phone -> phoneNumberMobile
    if payload.get("phoneNumberMobile") == "98765432":
        findings.append("OK: phone mapped to phoneNumberMobile")
    else:
        findings.append(f"FAIL: phoneNumberMobile = '{payload.get('phoneNumberMobile')}'")

    # Test with customer not found -> creates customer
    client2 = make_mock_client()
    client2.get_customers = AsyncMock(return_value=[])
    client2.create_customer = AsyncMock(return_value={"id": 77})
    fields2 = {
        "first_name": "Test",
        "last_name": "Person",
        "customer_identifier": "Ny Firma AS",
    }
    await _exec_create_contact(fields2, client2)
    if client2.create_customer.called:
        findings.append("OK: Customer created when not found")
        cp = client2.create_customer.call_args[0][0]
        if cp.get("name") == "Ny Firma AS":
            findings.append("OK: Created customer name correct")
        else:
            findings.append(f"FAIL: Created customer name = '{cp.get('name')}'")
    else:
        findings.append("FAIL: Customer not created when lookup returned empty")

    # Contact payload uses the new customer id
    contact_payload2 = client2.create_contact.call_args[0][0]
    if contact_payload2.get("customer", {}).get("id") == 77:
        findings.append("OK: Contact linked to newly created customer id=77")
    else:
        findings.append(f"FAIL: Contact customer = {contact_payload2.get('customer')}")

    all_ok = all("FAIL" not in f for f in findings)
    record("8. _exec_create_contact", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# 9. _exec_create_department
# ---------------------------------------------------------------------------

async def test_create_department():
    client = make_mock_client()
    fields = {
        "name": "Utvikling",
        "department_number": "42",
        "manager_id": 10,
    }
    await _exec_create_department(fields, client)
    payload = client.create_department.call_args[0][0]

    findings = []

    if payload.get("name") == "Utvikling":
        findings.append("OK: name = 'Utvikling'")
    else:
        findings.append(f"FAIL: name = '{payload.get('name')}'")

    if payload.get("departmentNumber") == "42":
        findings.append("OK: departmentNumber = '42'")
    else:
        findings.append(f"FAIL: departmentNumber = '{payload.get('departmentNumber')}'")

    mgr = payload.get("departmentManager")
    if isinstance(mgr, dict) and mgr.get("id") == 10:
        findings.append("OK: departmentManager = {\"id\": 10}")
    else:
        findings.append(f"FAIL: departmentManager = {mgr}")

    # Minimal payload — only these 3 fields expected
    valid_fields = {"name", "departmentNumber", "departmentManager"}
    unknown = set(payload.keys()) - valid_fields
    if unknown:
        findings.append(f"WARN: Extra fields: {unknown}")
    else:
        findings.append("OK: Payload is minimal (3 fields only)")

    # Test with minimal fields (just name)
    client2 = make_mock_client()
    fields2 = {"name": "HR"}
    await _exec_create_department(fields2, client2)
    p2 = client2.create_department.call_args[0][0]
    if set(p2.keys()) == {"name"}:
        findings.append("OK: Minimal payload has only 'name'")
    else:
        findings.append(f"NOTE: Minimal payload keys = {set(p2.keys())}")

    all_ok = all("FAIL" not in f for f in findings)
    record("9. _exec_create_department", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# 10. _exec_register_payment
# ---------------------------------------------------------------------------

async def test_register_payment():
    client = make_mock_client()
    fields = {
        "invoice_number": "1001",
        "amount": 12500,
        "payment_date": "2026-03-20",
    }
    await _exec_register_payment(fields, client)

    findings = []

    # Invoice lookup
    if client.get_invoices.called:
        inv_params = client.get_invoices.call_args[0][0]
        if inv_params.get("invoiceNumber") == "1001":
            findings.append("OK: Invoice lookup by invoiceNumber='1001'")
        else:
            findings.append(f"FAIL: Invoice lookup params = {inv_params}")
    else:
        findings.append("FAIL: get_invoices not called")

    # Payment registration
    if client.register_payment.called:
        inv_id = client.register_payment.call_args[0][0]
        pay_params = client.register_payment.call_args[0][1]

        if inv_id == 200:
            findings.append("OK: register_payment called with invoice_id=200")
        else:
            findings.append(f"FAIL: register_payment invoice_id = {inv_id}")

        if pay_params.get("paymentDate") == "2026-03-20":
            findings.append("OK: paymentDate correct")
        else:
            findings.append(f"FAIL: paymentDate = '{pay_params.get('paymentDate')}'")

        if pay_params.get("paidAmount") == 12500.0:
            findings.append("OK: paidAmount = 12500.0 (float)")
        else:
            findings.append(f"FAIL: paidAmount = {pay_params.get('paidAmount')}")

        pt = pay_params.get("paymentTypeId")
        if pt == 7:
            findings.append("OK: paymentTypeId = 7 (int)")
        else:
            findings.append(f"FAIL: paymentTypeId = {pt} (type: {type(pt)})")

        # Data types check
        if isinstance(pay_params.get("paidAmount"), float):
            findings.append("OK: paidAmount is float")
        else:
            findings.append(f"FAIL: paidAmount type = {type(pay_params.get('paidAmount'))}")

        if isinstance(pay_params.get("paymentTypeId"), int):
            findings.append("OK: paymentTypeId is int")
        else:
            findings.append(f"FAIL: paymentTypeId type = {type(pay_params.get('paymentTypeId'))}")
    else:
        findings.append("FAIL: register_payment not called")

    # Payment type lookup
    if client.get_invoice_payment_types.called:
        findings.append("OK: Payment types looked up dynamically")
    else:
        findings.append("FAIL: Payment types not looked up")

    # Test with direct invoice_id
    client2 = make_mock_client()
    fields2 = {"invoice_id": 999, "amount": 5000, "payment_type_id": 3}
    await _exec_register_payment(fields2, client2)
    if client2.register_payment.called:
        inv_id2 = client2.register_payment.call_args[0][0]
        if inv_id2 == 999:
            findings.append("OK: Direct invoice_id=999 used (no lookup)")
        else:
            findings.append(f"FAIL: Direct invoice_id = {inv_id2}")
    else:
        findings.append("FAIL: register_payment not called with direct invoice_id")

    all_ok = all("FAIL" not in f for f in findings)
    record("10. _exec_register_payment", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------

def test_build_order_lines_edge_cases():
    findings = []

    # Empty lines
    lines = _build_order_lines({})
    if lines == []:
        findings.append("OK: Empty fields -> empty order lines")
    else:
        findings.append(f"FAIL: Empty fields -> {lines}")

    # Line with no price -> defaults to 0.0
    lines = _build_order_lines({"lines": [{"description": "Free item"}]})
    if lines[0].get("unitPriceExcludingVatCurrency") == 0.0:
        findings.append("OK: Missing price defaults to 0.0")
    else:
        findings.append(f"FAIL: Missing price = {lines[0].get('unitPriceExcludingVatCurrency')}")

    # Line with quantity alias 'count'
    lines = _build_order_lines({"lines": [{"description": "X", "count": 5, "unit_price": 100}]})
    if lines[0].get("count") == 5.0:
        findings.append("OK: 'count' alias works for quantity")
    else:
        findings.append(f"FAIL: count = {lines[0].get('count')}")

    # Line with product_id
    lines = _build_order_lines({"lines": [{"product_id": 30, "quantity": 1, "unit_price": 200}]})
    prod = lines[0].get("product")
    if isinstance(prod, dict) and prod.get("id") == 30:
        findings.append("OK: product_id creates {\"id\": 30} ref")
    else:
        findings.append(f"FAIL: product ref = {prod}")

    # Line with discount
    lines = _build_order_lines({"lines": [{"description": "D", "unit_price": 100, "discount": 10}]})
    if lines[0].get("discount") == 10.0:
        findings.append("OK: discount = 10.0 (float)")
    else:
        findings.append(f"FAIL: discount = {lines[0].get('discount')}")

    # Line with unit_price_including_vat
    lines = _build_order_lines({"lines": [{"description": "Inc", "unit_price_including_vat": 1250}]})
    if "unitPriceIncludingVatCurrency" in lines[0] and "unitPriceExcludingVatCurrency" not in lines[0]:
        findings.append("OK: unit_price_including_vat maps to unitPriceIncludingVatCurrency")
    else:
        findings.append(f"FAIL: inc vat line keys = {list(lines[0].keys())}")

    all_ok = all("FAIL" not in f for f in findings)
    record("Edge: _build_order_lines", all_ok, findings=findings)


async def test_edge_cases_none_values():
    """Test that None/missing optional fields are excluded from payloads."""
    findings = []

    # Customer with all Nones for optional
    client = make_mock_client()
    fields = {"name": "Bare Navn"}
    await _exec_create_customer(fields, client)
    payload = client.create_customer.call_args[0][0]
    if set(payload.keys()) == {"name", "isCustomer"}:
        findings.append("OK: Customer with only name -> payload has 'name' + 'isCustomer'")
    else:
        findings.append(f"NOTE: Minimal customer payload keys = {set(payload.keys())}")

    # Department with None manager
    client2 = make_mock_client()
    fields2 = {"name": "Bare Avdeling", "manager_id": None}
    await _exec_create_department(fields2, client2)
    p2 = client2.create_department.call_args[0][0]
    if "departmentManager" not in p2:
        findings.append("OK: None manager_id excluded from department payload")
    else:
        findings.append(f"FAIL: departmentManager present with None: {p2.get('departmentManager')}")

    all_ok = all("FAIL" not in f for f in findings)
    record("Edge: None/missing optional fields", all_ok, findings=findings)


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("Tripletex Executor Payload Tests")
    print("=" * 70)
    print()

    # Sync tests
    test_helpers()
    test_build_order_lines_edge_cases()

    # Async tests
    await test_create_employee()
    await test_create_customer()
    await test_create_product()
    await test_create_invoice()
    await test_invoice_with_payment()
    await test_project_with_customer()
    await test_create_travel_expense()
    await test_create_contact()
    await test_create_department()
    await test_register_payment()
    await test_edge_cases_none_values()

    # Report
    print()
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['name']}")
        if r.get("findings"):
            for f in r["findings"]:
                print(f"       {f}")
        if r.get("details"):
            print(f"       {r['details']}")
        print()

    print("=" * 70)
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print("=" * 70)

    return results


if __name__ == "__main__":
    all_results = asyncio.run(main())
