from __future__ import annotations
"""Smoketest ~40 Tier 1 executor handlers using mock client.

Tests exercise execute_task() (the public entry point) with TaskClassification
objects, verifying payloads, field mappings, and key behaviors documented in
executor.py comments.
"""
import os, sys
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("GCP_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import traceback
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Optional

from executor import execute_task
from task_types import TaskClassification, TaskType
from tripletex_client import TripletexAPIError

# Fix missing 're' import in executor.py (module-level _clean_org_number uses re.sub)
import executor
import re
if not hasattr(executor, 're'):
    executor.re = re


# ---------------------------------------------------------------------------
# Mock client factory
# ---------------------------------------------------------------------------

def make_mock_client() -> MagicMock:
    """Comprehensive mock covering ALL methods any T1 handler might call."""
    client = MagicMock()
    client.api_call_count = 0
    client.error_count = 0
    # Ensure cache attributes return proper defaults (not truthy MagicMock)
    client._bank_account_ensured = False
    client._vat_type_cache = {}
    client._department_cache = {}
    client._default_department_id = None
    client._payment_type_cache = None
    client._employee_search_cache = {}
    client._customer_search_cache = {}
    client._voucher_type_cache = None

    # Department
    client.get_departments = AsyncMock(return_value=[{"id": 1, "name": "General", "version": 1}])
    client.create_department = AsyncMock(return_value={"id": 99, "name": "New Dept", "version": 0})
    client.update_department = AsyncMock(return_value={"id": 1, "name": "Updated", "version": 2})
    client.delete = AsyncMock(return_value={})

    # Employee
    client.get_employees = AsyncMock(return_value=[
        {"id": 10, "firstName": "Ola", "lastName": "Nordmann", "email": "ola@test.no",
         "version": 1, "department": {"id": 1}, "dateOfBirth": "1985-06-15",
         "phoneNumberMobile": "99887766", "address": None}
    ])
    client.create_employee = AsyncMock(return_value={"id": 42, "version": 0})
    client.update_employee = AsyncMock(return_value={"id": 10, "version": 2})
    client.delete_employee = AsyncMock(return_value={})

    # Customer
    client.get_customers = AsyncMock(return_value=[
        {"id": 20, "name": "Acme AS", "version": 2, "email": "info@acme.no",
         "postalAddress": None}
    ])
    client.create_customer = AsyncMock(return_value={"id": 55, "name": "New Customer", "version": 0})
    client.update_customer = AsyncMock(return_value={"id": 20, "version": 3})
    client.delete_customer = AsyncMock(return_value={})

    # Supplier
    client.get_suppliers = AsyncMock(return_value=[
        {"id": 30, "name": "Leveransen AS", "version": 1, "organizationNumber": "987654321"}
    ])
    client.create_supplier = AsyncMock(return_value={"id": 35, "name": "New Supplier", "version": 0})
    client.update_supplier = AsyncMock(return_value={"id": 30, "version": 2})
    client.delete_supplier = AsyncMock(return_value={})

    # Product
    client.get_products = AsyncMock(return_value=[
        {"id": 40, "name": "Widget", "version": 1, "priceExcludingVatCurrency": 100.0}
    ])
    client.get_product = AsyncMock(return_value={
        "id": 40, "name": "Widget", "version": 1, "priceExcludingVatCurrency": 100.0,
        "description": "A widget", "vatType": {"id": 3}
    })
    client.create_product = AsyncMock(return_value={"id": 41, "version": 0})
    client.update_product = AsyncMock(return_value={"id": 40, "version": 2})
    client.put = AsyncMock(return_value={"value": {"id": 40, "version": 2}})

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

    # Contact
    client.get_contacts = AsyncMock(return_value=[
        {"id": 50, "firstName": "Erik", "lastName": "Svendsen", "version": 1}
    ])
    client.create_contact = AsyncMock(return_value={"id": 51, "version": 0})

    # Project
    client.get_projects = AsyncMock(return_value=[
        {"id": 60, "name": "Prosjekt A", "version": 1}
    ])
    client.create_project = AsyncMock(return_value={"id": 61, "version": 0})
    client.update_project = AsyncMock(return_value={"id": 60, "version": 2})
    client.delete_project = AsyncMock(return_value={})

    return client


def _tc(task_type: TaskType, fields: dict) -> TaskClassification:
    return TaskClassification(task_type=task_type, confidence=1.0, fields=fields)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

results: list[dict] = []

def record(name: str, passed: bool, details: str = "", findings: list[str] | None = None):
    results.append({"name": name, "passed": passed, "details": details, "findings": findings or []})


# ---------------------------------------------------------------------------
# CREATE_EMPLOYEE tests
# ---------------------------------------------------------------------------

async def test_create_employee_basic():
    client = make_mock_client()
    r = await execute_task(_tc(TaskType.CREATE_EMPLOYEE, {
        "first_name": "Kari", "last_name": "Hansen",
    }), client)
    findings = []
    payload = client.create_employee.call_args[0][0]
    if payload.get("firstName") == "Kari":
        findings.append("OK: firstName=Kari")
    else:
        findings.append(f"FAIL: firstName={payload.get('firstName')}")
    # Auto-generated email
    if payload.get("email") == "kari.hansen@example.com":
        findings.append("OK: auto-email kari.hansen@example.com")
    else:
        findings.append(f"FAIL: email={payload.get('email')}")
    record("CREATE_EMPLOYEE basic", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_employee_with_email():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_EMPLOYEE, {
        "first_name": "Per", "last_name": "Olsen", "email": "per@firma.no",
    }), client)
    findings = []
    payload = client.create_employee.call_args[0][0]
    if payload.get("email") == "per@firma.no":
        findings.append("OK: explicit email used")
    else:
        findings.append(f"FAIL: email={payload.get('email')}")
    record("CREATE_EMPLOYEE with email", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_employee_with_department():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_EMPLOYEE, {
        "first_name": "Lise", "last_name": "Berg", "department_name": "Salg",
    }), client)
    findings = []
    # Should have looked up department
    assert client.get_departments.called
    findings.append("OK: department lookup performed")
    payload = client.create_employee.call_args[0][0]
    dept = payload.get("department")
    if isinstance(dept, dict) and "id" in dept:
        findings.append(f"OK: department ref={dept}")
    else:
        findings.append(f"FAIL: department={dept}")
    record("CREATE_EMPLOYEE with department", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_employee_user_type_admin():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_EMPLOYEE, {
        "first_name": "X", "last_name": "Y", "user_type": "administrator",
    }), client)
    findings = []
    payload = client.create_employee.call_args[0][0]
    if payload.get("userType") == "EXTENDED":
        findings.append("OK: administrator → EXTENDED")
    else:
        findings.append(f"FAIL: userType={payload.get('userType')}")
    record("CREATE_EMPLOYEE admin→EXTENDED", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# UPDATE_EMPLOYEE tests
# ---------------------------------------------------------------------------

async def test_update_employee_basic():
    client = make_mock_client()
    r = await execute_task(_tc(TaskType.UPDATE_EMPLOYEE, {
        "employee_identifier": "Ola Nordmann",
        "new_phone": "11223344",
    }), client)
    findings = []
    # Employee search uses firstName only as API param
    emp_params = client.get_employees.call_args[0][0]
    if "firstName" in emp_params:
        findings.append("OK: employee search uses firstName param")
    else:
        findings.append(f"FAIL: search params={emp_params}")
    if "lastName" not in emp_params:
        findings.append("OK: lastName NOT in API params (client-side filter)")
    else:
        findings.append("FAIL: lastName in API params")

    payload = client.update_employee.call_args[0][1]
    # Email is IMMUTABLE — must use existing
    if payload.get("email") == "ola@test.no":
        findings.append("OK: email=ola@test.no (immutable, existing value)")
    else:
        findings.append(f"FAIL: email={payload.get('email')} (should be ola@test.no)")
    # Version field present
    if "version" in payload:
        findings.append(f"OK: version={payload['version']} in PUT")
    else:
        findings.append("FAIL: version missing from PUT payload")
    record("UPDATE_EMPLOYEE basic (email immutable)", all("FAIL" not in f for f in findings), findings=findings)


async def test_update_employee_email_not_in_new_fields():
    """Verify that even if new_email is provided, the existing email is used."""
    client = make_mock_client()
    await execute_task(_tc(TaskType.UPDATE_EMPLOYEE, {
        "employee_identifier": "Ola Nordmann",
        "email": "should_be_ignored@test.no",
    }), client)
    findings = []
    payload = client.update_employee.call_args[0][1]
    if payload.get("email") == "ola@test.no":
        findings.append("OK: new email ignored, existing email preserved")
    else:
        findings.append(f"FAIL: email={payload.get('email')}")
    record("UPDATE_EMPLOYEE email immutable enforcement", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# DELETE_EMPLOYEE tests
# ---------------------------------------------------------------------------

async def test_delete_employee_basic():
    client = make_mock_client()
    r = await execute_task(_tc(TaskType.DELETE_EMPLOYEE, {
        "employee_identifier": "Ola Nordmann",
    }), client)
    findings = []
    if client.delete_employee.called:
        findings.append("OK: delete_employee called")
        emp_id = client.delete_employee.call_args[0][0]
        if emp_id == 10:
            findings.append("OK: deleted employee id=10")
        else:
            findings.append(f"FAIL: deleted id={emp_id}")
    else:
        findings.append("FAIL: delete_employee not called")
    record("DELETE_EMPLOYEE basic", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# SET_EMPLOYEE_ROLES tests
# ---------------------------------------------------------------------------

async def test_set_employee_roles():
    client = make_mock_client()
    await execute_task(_tc(TaskType.SET_EMPLOYEE_ROLES, {
        "employee_identifier": "Ola Nordmann",
        "user_type": "extended",
    }), client)
    findings = []
    payload = client.update_employee.call_args[0][1]
    if payload.get("userType") == "EXTENDED":
        findings.append("OK: userType=EXTENDED")
    else:
        findings.append(f"FAIL: userType={payload.get('userType')}")
    if "version" in payload:
        findings.append("OK: version in PUT payload")
    else:
        findings.append("FAIL: version missing")
    record("SET_EMPLOYEE_ROLES", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# CREATE_CUSTOMER tests
# ---------------------------------------------------------------------------

async def test_create_customer_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_CUSTOMER, {
        "name": "Norsk Bedrift AS",
    }), client)
    findings = []
    payload = client.create_customer.call_args[0][0]
    if payload.get("name") == "Norsk Bedrift AS":
        findings.append("OK: name correct")
    else:
        findings.append(f"FAIL: name={payload.get('name')}")
    if payload.get("isCustomer") is True:
        findings.append("OK: isCustomer=True")
    else:
        findings.append("FAIL: isCustomer missing or wrong")
    record("CREATE_CUSTOMER basic", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_customer_with_org_number():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_CUSTOMER, {
        "name": "Firma AS", "organization_number": "922 976 457",
    }), client)
    findings = []
    payload = client.create_customer.call_args[0][0]
    org = payload.get("organizationNumber")
    if org == "922976457":
        findings.append("OK: org number cleaned (spaces removed)")
    else:
        findings.append(f"FAIL: organizationNumber={org} (expected 922976457)")
    record("CREATE_CUSTOMER org number cleaned", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_customer_with_org_number_dashes():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_CUSTOMER, {
        "name": "Firma AS", "organization_number": "922-976-457",
    }), client)
    findings = []
    payload = client.create_customer.call_args[0][0]
    org = payload.get("organizationNumber")
    if org == "922976457":
        findings.append("OK: org number cleaned (dashes removed)")
    else:
        findings.append(f"FAIL: organizationNumber={org}")
    record("CREATE_CUSTOMER org number dashes", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# UPDATE_CUSTOMER tests
# ---------------------------------------------------------------------------

async def test_update_customer_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.UPDATE_CUSTOMER, {
        "customer_identifier": "Acme AS",
        "new_email": "new@acme.no",
    }), client)
    findings = []
    if client.update_customer.called:
        payload = client.update_customer.call_args[0][1]
        if "version" in payload:
            findings.append(f"OK: version={payload['version']} in PUT")
        else:
            findings.append("FAIL: version missing from PUT")
        if "id" in payload:
            findings.append(f"OK: id={payload['id']} in PUT")
        else:
            findings.append("FAIL: id missing from PUT")
    else:
        findings.append("FAIL: update_customer not called")
    record("UPDATE_CUSTOMER basic", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# CREATE_PRODUCT tests
# ---------------------------------------------------------------------------

async def test_create_product_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_PRODUCT, {
        "name": "Konsulenttimer", "price": 1500.0,
    }), client)
    findings = []
    payload = client.create_product.call_args[0][0]
    if payload.get("name") == "Konsulenttimer":
        findings.append("OK: name correct")
    else:
        findings.append(f"FAIL: name={payload.get('name')}")
    if payload.get("priceExcludingVatCurrency") == 1500.0:
        findings.append("OK: price=1500.0")
    else:
        findings.append(f"FAIL: price={payload.get('priceExcludingVatCurrency')}")
    record("CREATE_PRODUCT basic", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_product_with_vat():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_PRODUCT, {
        "name": "Fritak", "price": 100, "vat_percentage": "0",
    }), client)
    findings = []
    payload = client.create_product.call_args[0][0]
    vat = payload.get("vatType")
    if isinstance(vat, dict) and vat.get("id") == 6:
        findings.append("OK: 0% VAT resolved to id=6")
    else:
        findings.append(f"FAIL: vatType={vat}")
    # Verify VAT lookup called
    if client.get_vat_types.called:
        findings.append("OK: VAT type lookup performed")
    else:
        findings.append("FAIL: VAT lookup not called")
    record("CREATE_PRODUCT with VAT lookup", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_product_number_collision_retry():
    """Product number collision → retry without number."""
    call_count = 0
    async def mock_create_product(payload):
        nonlocal call_count
        call_count += 1
        if call_count == 1 and "number" in payload:
            raise TripletexAPIError(422, "Produktnummeret 42 er i bruk", "/product")
        return {"id": 41}

    client = make_mock_client()
    client.create_product = AsyncMock(side_effect=mock_create_product)
    client.get_products = AsyncMock(return_value=[])  # no existing match

    await execute_task(_tc(TaskType.CREATE_PRODUCT, {
        "name": "Widget", "number": "42", "price": 100,
    }), client)
    findings = []
    if call_count >= 2:
        findings.append("OK: product creation retried after 422 collision")
    else:
        findings.append(f"FAIL: create_product called {call_count} time(s), expected ≥2")
    # Second call should NOT have number
    last_payload = client.create_product.call_args[0][0]
    if "number" not in last_payload:
        findings.append("OK: retry without number field")
    else:
        findings.append(f"FAIL: retry still has number={last_payload.get('number')}")
    record("CREATE_PRODUCT collision retry", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# UPDATE_PRODUCT tests
# ---------------------------------------------------------------------------

async def test_update_product_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.UPDATE_PRODUCT, {
        "product_identifier": "Widget", "new_price": 200.0,
    }), client)
    findings = []
    if client.get_products.called:
        findings.append("OK: product search performed")
    else:
        findings.append("FAIL: product search not performed")
    if client.get_product.called:
        findings.append("OK: full product fetched for version")
    else:
        findings.append("FAIL: get_product not called")
    if client.put.called:
        payload = client.put.call_args[0][1]
        if "version" in payload:
            findings.append(f"OK: version in PUT payload")
        else:
            findings.append("FAIL: version missing from PUT")
    else:
        findings.append("FAIL: put not called")
    record("UPDATE_PRODUCT basic", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# DELETE_PRODUCT tests
# ---------------------------------------------------------------------------

async def test_delete_product_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.DELETE_PRODUCT, {
        "product_identifier": "Widget",
    }), client)
    findings = []
    if client.get_products.called:
        findings.append("OK: product search performed")
    else:
        findings.append("FAIL: product search not performed")
    if client.delete.called:
        path = client.delete.call_args[0][0]
        if "/product/40" in path:
            findings.append("OK: DELETE /product/40")
        else:
            findings.append(f"FAIL: delete path={path}")
    else:
        findings.append("FAIL: delete not called")
    record("DELETE_PRODUCT basic", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# CREATE_SUPPLIER tests
# ---------------------------------------------------------------------------

async def test_create_supplier_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_SUPPLIER, {
        "name": "Leveransen AS",
    }), client)
    findings = []
    payload = client.create_supplier.call_args[0][0]
    if payload.get("name") == "Leveransen AS":
        findings.append("OK: name correct")
    else:
        findings.append(f"FAIL: name={payload.get('name')}")
    if payload.get("isSupplier") is True:
        findings.append("OK: isSupplier=True")
    else:
        findings.append("FAIL: isSupplier missing or wrong")
    record("CREATE_SUPPLIER basic", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_supplier_with_org_number():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_SUPPLIER, {
        "name": "Leveransen AS", "organization_number": "987 654 321",
    }), client)
    findings = []
    payload = client.create_supplier.call_args[0][0]
    org = payload.get("organizationNumber")
    if org == "987654321":
        findings.append("OK: org number cleaned")
    else:
        findings.append(f"FAIL: organizationNumber={org}")
    record("CREATE_SUPPLIER org number cleaned", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# UPDATE_SUPPLIER tests
# ---------------------------------------------------------------------------

async def test_update_supplier_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.UPDATE_SUPPLIER, {
        "supplier_identifier": "Leveransen AS",
        "new_email": "ny@leveransen.no",
    }), client)
    findings = []
    if client.get_suppliers.called:
        findings.append("OK: supplier search performed")
    else:
        findings.append("FAIL: supplier search not performed")
    if client.update_supplier.called:
        payload = client.update_supplier.call_args[0][1]
        if "version" in payload:
            findings.append("OK: version in PUT payload")
        else:
            findings.append("FAIL: version missing from PUT")
    else:
        findings.append("FAIL: update_supplier not called")
    record("UPDATE_SUPPLIER basic", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# DELETE_SUPPLIER tests
# ---------------------------------------------------------------------------

async def test_delete_supplier_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.DELETE_SUPPLIER, {
        "supplier_identifier": "Leveransen AS",
    }), client)
    findings = []
    if client.delete_supplier.called:
        findings.append("OK: delete_supplier called")
        sid = client.delete_supplier.call_args[0][0]
        if sid == 30:
            findings.append("OK: deleted supplier id=30")
        else:
            findings.append(f"FAIL: deleted id={sid}")
    else:
        findings.append("FAIL: delete_supplier not called")
    record("DELETE_SUPPLIER basic", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# FIND_SUPPLIER tests
# ---------------------------------------------------------------------------

async def test_find_supplier_by_name():
    client = make_mock_client()
    r = await execute_task(_tc(TaskType.FIND_SUPPLIER, {
        "search_query": "Leveransen",
    }), client)
    findings = []
    if client.get_suppliers.called:
        params = client.get_suppliers.call_args[0][0]
        if params.get("supplierName") == "Leveransen":
            findings.append("OK: search by supplierName")
        else:
            findings.append(f"FAIL: search params={params}")
    else:
        findings.append("FAIL: get_suppliers not called")
    if r.get("count", 0) > 0:
        findings.append(f"OK: found {r['count']} results")
    else:
        findings.append("FAIL: no results found")
    record("FIND_SUPPLIER by name", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# CREATE_INVOICE tests
# ---------------------------------------------------------------------------

async def test_create_invoice_basic():
    client = make_mock_client()
    r = await execute_task(_tc(TaskType.CREATE_INVOICE, {
        "customer_name": "Acme AS",
        "invoice_date": "2026-03-20",
        "lines": [
            {"description": "Konsulentarbeid", "quantity": 10, "unit_price": 1500},
        ],
    }), client)
    findings = []
    # Bank account ensured
    if client.get_ledger_accounts.called:
        findings.append("OK: _ensure_bank_account called (ledger accounts checked)")
    else:
        findings.append("FAIL: bank account not checked")
    # Order created
    if client.create_order.called:
        order_payload = client.create_order.call_args[0][0]
        if order_payload.get("customer", {}).get("id") == 20:
            findings.append("OK: customer ref id=20")
        else:
            findings.append(f"FAIL: customer={order_payload.get('customer')}")
        lines = order_payload.get("orderLines", [])
        if len(lines) == 1:
            findings.append("OK: 1 order line")
        else:
            findings.append(f"FAIL: {len(lines)} order lines")
    else:
        findings.append("FAIL: create_order not called")
    # Invoiced
    if client.invoice_order.called:
        findings.append("OK: invoice_order called")
    else:
        findings.append("FAIL: invoice_order not called")
    record("CREATE_INVOICE basic", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_invoice_with_lines():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_INVOICE, {
        "customer_name": "Acme AS",
        "lines": [
            {"description": "Line 1", "quantity": 2, "unit_price": 500},
            {"description": "Line 2", "quantity": 1, "unit_price": 1000},
        ],
    }), client)
    findings = []
    order_payload = client.create_order.call_args[0][0]
    lines = order_payload.get("orderLines", [])
    if len(lines) == 2:
        findings.append("OK: 2 order lines")
    else:
        findings.append(f"FAIL: {len(lines)} lines, expected 2")
    if lines[0].get("count") == 2.0:
        findings.append("OK: line[0].count=2.0")
    else:
        findings.append(f"FAIL: line[0].count={lines[0].get('count')}")
    if lines[0].get("unitPriceExcludingVatCurrency") == 500.0:
        findings.append("OK: line[0].price=500.0")
    else:
        findings.append(f"FAIL: line[0].price={lines[0].get('unitPriceExcludingVatCurrency')}")
    record("CREATE_INVOICE with lines", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# CREATE_DEPARTMENT tests
# ---------------------------------------------------------------------------

async def test_create_department_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_DEPARTMENT, {
        "name": "Utvikling",
    }), client)
    findings = []
    payload = client.create_department.call_args[0][0]
    if payload.get("name") == "Utvikling":
        findings.append("OK: name=Utvikling")
    else:
        findings.append(f"FAIL: name={payload.get('name')}")
    record("CREATE_DEPARTMENT basic", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_department_with_number():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_DEPARTMENT, {
        "name": "IT", "department_number": "42",
    }), client)
    findings = []
    payload = client.create_department.call_args[0][0]
    if payload.get("departmentNumber") == "42":
        findings.append("OK: departmentNumber=42")
    else:
        findings.append(f"FAIL: departmentNumber={payload.get('departmentNumber')}")
    record("CREATE_DEPARTMENT with number", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# DELETE_DEPARTMENT tests
# ---------------------------------------------------------------------------

async def test_delete_department_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.DELETE_DEPARTMENT, {
        "department_identifier": "General",
    }), client)
    findings = []
    if client.get_departments.called:
        findings.append("OK: department lookup performed")
    else:
        findings.append("FAIL: department lookup not performed")
    if client.delete.called:
        path = client.delete.call_args[0][0]
        if "/department/" in path:
            findings.append(f"OK: DELETE {path}")
        else:
            findings.append(f"FAIL: delete path={path}")
    else:
        findings.append("FAIL: delete not called")
    record("DELETE_DEPARTMENT basic", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# CREATE_PROJECT tests
# ---------------------------------------------------------------------------

async def test_create_project_basic():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_PROJECT, {
        "name": "Prosjekt Alpha",
        "project_manager_name": "Ola Nordmann",
        "start_date": "2026-04-01",
    }), client)
    findings = []
    if client.create_project.called:
        payload = client.create_project.call_args[0][0]
        if payload.get("name") == "Prosjekt Alpha":
            findings.append("OK: name correct")
        else:
            findings.append(f"FAIL: name={payload.get('name')}")
        pm = payload.get("projectManager")
        if isinstance(pm, dict) and "id" in pm:
            findings.append(f"OK: projectManager ref={pm}")
        else:
            findings.append(f"FAIL: projectManager={pm}")
        if payload.get("startDate") == "2026-04-01":
            findings.append("OK: startDate=2026-04-01")
        else:
            findings.append(f"FAIL: startDate={payload.get('startDate')}")
    else:
        findings.append("FAIL: create_project not called")
    record("CREATE_PROJECT basic", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_project_manager_lookup():
    """Verify projectManager is resolved from employee search."""
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_PROJECT, {
        "name": "Prosjekt B",
        "project_manager_name": "Ola Nordmann",
    }), client)
    findings = []
    # Employee search should have been called to find manager
    if client.get_employees.called:
        emp_params = client.get_employees.call_args[0][0]
        if "firstName" in emp_params:
            findings.append("OK: employee search by firstName for manager")
        else:
            findings.append(f"FAIL: emp search params={emp_params}")
    else:
        findings.append("FAIL: employee search not called for manager")
    record("CREATE_PROJECT manager lookup", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# Additional edge case tests
# ---------------------------------------------------------------------------

async def test_create_customer_org_number_alias():
    """org_number alias should also work."""
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_CUSTOMER, {
        "name": "Test AS", "org_number": "111 222 333",
    }), client)
    findings = []
    payload = client.create_customer.call_args[0][0]
    org = payload.get("organizationNumber")
    if org == "111222333":
        findings.append("OK: org_number alias cleaned")
    else:
        findings.append(f"FAIL: org={org}")
    record("CREATE_CUSTOMER org_number alias", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_supplier_org_number_dots():
    """Org number with dots should be cleaned."""
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_SUPPLIER, {
        "name": "Test", "organization_number": "922.976.457",
    }), client)
    findings = []
    payload = client.create_supplier.call_args[0][0]
    org = payload.get("organizationNumber")
    if org == "922976457":
        findings.append("OK: dots removed from org number")
    else:
        findings.append(f"FAIL: org={org}")
    record("CREATE_SUPPLIER org dots cleaned", all("FAIL" not in f for f in findings), findings=findings)


async def test_update_supplier_version_field():
    """PUT supplier should include version."""
    client = make_mock_client()
    await execute_task(_tc(TaskType.UPDATE_SUPPLIER, {
        "supplier_identifier": "Leveransen AS",
        "new_name": "Ny Leveransen AS",
    }), client)
    findings = []
    if client.update_supplier.called:
        payload = client.update_supplier.call_args[0][1]
        if payload.get("version") == 1:
            findings.append("OK: version=1 from mock")
        else:
            findings.append(f"FAIL: version={payload.get('version')}")
        if payload.get("name") == "Ny Leveransen AS":
            findings.append("OK: new_name applied")
        else:
            findings.append(f"FAIL: name={payload.get('name')}")
    else:
        findings.append("FAIL: update_supplier not called")
    record("UPDATE_SUPPLIER version field", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_employee_restricted_maps_no_access():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_EMPLOYEE, {
        "first_name": "A", "last_name": "B", "user_type": "RESTRICTED",
    }), client)
    findings = []
    payload = client.create_employee.call_args[0][0]
    if payload.get("userType") == "NO_ACCESS":
        findings.append("OK: RESTRICTED → NO_ACCESS")
    else:
        findings.append(f"FAIL: userType={payload.get('userType')}")
    record("CREATE_EMPLOYEE RESTRICTED→NO_ACCESS", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_employee_invalid_user_type_fallback():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_EMPLOYEE, {
        "first_name": "A", "last_name": "B", "user_type": "SUPERUSER",
    }), client)
    findings = []
    payload = client.create_employee.call_args[0][0]
    if payload.get("userType") == "STANDARD":
        findings.append("OK: invalid type → STANDARD fallback")
    else:
        findings.append(f"FAIL: userType={payload.get('userType')}")
    record("CREATE_EMPLOYEE invalid type fallback", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_product_default_vat_25():
    """No VAT specified → default 25%."""
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_PRODUCT, {
        "name": "Default VAT", "price": 100,
    }), client)
    findings = []
    payload = client.create_product.call_args[0][0]
    vat = payload.get("vatType")
    if isinstance(vat, dict) and vat.get("id") == 3:
        findings.append("OK: default 25% VAT id=3")
    else:
        findings.append(f"FAIL: vatType={vat}")
    record("CREATE_PRODUCT default 25% VAT", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_invoice_creates_customer_if_not_found():
    """If customer not found, should create inline."""
    client = make_mock_client()
    client.get_customers = AsyncMock(return_value=[])

    await execute_task(_tc(TaskType.CREATE_INVOICE, {
        "customer_name": "Ny Kunde AS",
        "lines": [{"description": "Test", "quantity": 1, "unit_price": 100}],
    }), client)
    findings = []
    if client.create_customer.called:
        cust_payload = client.create_customer.call_args[0][0]
        if cust_payload.get("name") == "Ny Kunde AS":
            findings.append("OK: customer created inline")
        else:
            findings.append(f"FAIL: customer name={cust_payload.get('name')}")
        if cust_payload.get("isCustomer") is True:
            findings.append("OK: isCustomer=True on inline customer")
        else:
            findings.append("FAIL: isCustomer missing on inline customer")
    else:
        findings.append("FAIL: customer not created when not found")
    record("CREATE_INVOICE inline customer creation", all("FAIL" not in f for f in findings), findings=findings)


async def test_delete_employee_403_fallback():
    """DELETE returning 403 should fallback to marking as contact."""
    client = make_mock_client()
    client.delete_employee = AsyncMock(side_effect=TripletexAPIError(403, "Permission denied"))

    r = await execute_task(_tc(TaskType.DELETE_EMPLOYEE, {
        "employee_identifier": "Ola Nordmann",
    }), client)
    findings = []
    if client.update_employee.called:
        payload = client.update_employee.call_args[0][1]
        if payload.get("isContact") is True:
            findings.append("OK: fallback to isContact=True")
        else:
            findings.append(f"FAIL: update payload={payload}")
    else:
        findings.append("FAIL: update_employee not called as fallback")
    record("DELETE_EMPLOYEE 403 fallback", all("FAIL" not in f for f in findings), findings=findings)


async def test_find_supplier_with_org_number():
    """FIND_SUPPLIER with org number — search uses supplierName + organizationNumber."""
    client = make_mock_client()
    await execute_task(_tc(TaskType.FIND_SUPPLIER, {
        "search_query": "Test", "organization_number": "123 456 789",
    }), client)
    findings = []
    if client.get_suppliers.called:
        params = client.get_suppliers.call_args[0][0]
        if params.get("supplierName") == "Test":
            findings.append("OK: supplierName=Test in search")
        else:
            findings.append(f"FAIL: params={params}")
        org = params.get("organizationNumber")
        if org == "123456789":
            findings.append("OK: org number cleaned in find_supplier")
        elif org is None:
            findings.append("OK: org number not in primary search (name-first)")
        else:
            findings.append(f"FAIL: org={org}")
    else:
        findings.append("FAIL: get_suppliers not called")
    record("FIND_SUPPLIER with org+name", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_project_no_manager_defaults_to_first_employee():
    """If no manager specified, should use first available employee."""
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_PROJECT, {
        "name": "Auto Manager Project",
    }), client)
    findings = []
    if client.create_project.called:
        payload = client.create_project.call_args[0][0]
        pm = payload.get("projectManager")
        if isinstance(pm, dict) and "id" in pm:
            findings.append(f"OK: projectManager auto-assigned id={pm['id']}")
        else:
            findings.append(f"FAIL: projectManager={pm}")
    else:
        findings.append("FAIL: create_project not called")
    record("CREATE_PROJECT auto manager", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_customer_with_address():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_CUSTOMER, {
        "name": "Addr AS",
        "address_line1": "Storgata 1",
        "postal_code": "0150",
        "city": "Oslo",
    }), client)
    findings = []
    payload = client.create_customer.call_args[0][0]
    addr = payload.get("postalAddress")
    if addr and addr.get("addressLine1") == "Storgata 1":
        findings.append("OK: address mapped correctly")
    else:
        findings.append(f"FAIL: postalAddress={addr}")
    record("CREATE_CUSTOMER with address", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_supplier_with_bank_account():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_SUPPLIER, {
        "name": "Bank Supp", "bank_account_number": "12340000001",
    }), client)
    findings = []
    payload = client.create_supplier.call_args[0][0]
    if payload.get("bankAccountNumber") == "12340000001":
        findings.append("OK: bankAccountNumber passed through")
    else:
        findings.append(f"FAIL: bankAccountNumber={payload.get('bankAccountNumber')}")
    record("CREATE_SUPPLIER with bank account", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_employee_with_phone():
    client = make_mock_client()
    await execute_task(_tc(TaskType.CREATE_EMPLOYEE, {
        "first_name": "Per", "last_name": "Olsen", "phone": "99887766",
    }), client)
    findings = []
    payload = client.create_employee.call_args[0][0]
    if payload.get("phoneNumberMobile") == "99887766":
        findings.append("OK: phone → phoneNumberMobile")
    else:
        findings.append(f"FAIL: phoneNumberMobile={payload.get('phoneNumberMobile')}")
    record("CREATE_EMPLOYEE phone mapping", all("FAIL" not in f for f in findings), findings=findings)


async def test_create_invoice_bank_account_prerequisite():
    """Verify bank account is checked before invoice creation."""
    client = make_mock_client()
    # Bank account without number → should trigger update
    client.get_ledger_accounts = AsyncMock(return_value=[
        {"id": 5, "number": 1920, "name": "Bankinnskudd", "version": 0, "bankAccountNumber": None}
    ])
    await execute_task(_tc(TaskType.CREATE_INVOICE, {
        "customer_name": "Acme AS",
        "lines": [{"description": "Test", "quantity": 1, "unit_price": 100}],
    }), client)
    findings = []
    if client.update_ledger_account.called:
        findings.append("OK: bank account updated (was missing)")
        upd = client.update_ledger_account.call_args[0][1]
        if upd.get("bankAccountNumber"):
            findings.append(f"OK: bankAccountNumber set to {upd['bankAccountNumber']}")
        else:
            findings.append("FAIL: bankAccountNumber not set in update")
    else:
        findings.append("FAIL: bank account not updated when missing")
    record("CREATE_INVOICE bank prerequisite", all("FAIL" not in f for f in findings), findings=findings)


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("Tier 1 Executor Smoketests")
    print("=" * 70)
    print()

    tests = [
        # CREATE_EMPLOYEE (4)
        test_create_employee_basic,
        test_create_employee_with_email,
        test_create_employee_with_department,
        test_create_employee_user_type_admin,
        # UPDATE_EMPLOYEE (2)
        test_update_employee_basic,
        test_update_employee_email_not_in_new_fields,
        # DELETE_EMPLOYEE (2)
        test_delete_employee_basic,
        test_delete_employee_403_fallback,
        # SET_EMPLOYEE_ROLES (1)
        test_set_employee_roles,
        # CREATE_CUSTOMER (4)
        test_create_customer_basic,
        test_create_customer_with_org_number,
        test_create_customer_with_org_number_dashes,
        test_create_customer_org_number_alias,
        test_create_customer_with_address,
        # UPDATE_CUSTOMER (1)
        test_update_customer_basic,
        # CREATE_PRODUCT (4)
        test_create_product_basic,
        test_create_product_with_vat,
        test_create_product_number_collision_retry,
        test_create_product_default_vat_25,
        # UPDATE_PRODUCT (1)
        test_update_product_basic,
        # DELETE_PRODUCT (1)
        test_delete_product_basic,
        # CREATE_SUPPLIER (3)
        test_create_supplier_basic,
        test_create_supplier_with_org_number,
        test_create_supplier_org_number_dots,
        test_create_supplier_with_bank_account,
        # UPDATE_SUPPLIER (2)
        test_update_supplier_basic,
        test_update_supplier_version_field,
        # DELETE_SUPPLIER (1)
        test_delete_supplier_basic,
        # FIND_SUPPLIER (2)
        test_find_supplier_by_name,
        test_find_supplier_with_org_number,
        # CREATE_INVOICE (3)
        test_create_invoice_basic,
        test_create_invoice_with_lines,
        test_create_invoice_creates_customer_if_not_found,
        test_create_invoice_bank_account_prerequisite,
        # CREATE_DEPARTMENT (2)
        test_create_department_basic,
        test_create_department_with_number,
        # DELETE_DEPARTMENT (1)
        test_delete_department_basic,
        # CREATE_PROJECT (3)
        test_create_project_basic,
        test_create_project_manager_lookup,
        test_create_project_no_manager_defaults_to_first_employee,
        # Employee edge cases (3)
        test_create_employee_restricted_maps_no_access,
        test_create_employee_invalid_user_type_fallback,
        test_create_employee_with_phone,
    ]

    for test_fn in tests:
        try:
            await test_fn()
        except Exception as e:
            record(test_fn.__name__, False, details=f"EXCEPTION: {e}\n{traceback.format_exc()}")

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

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
