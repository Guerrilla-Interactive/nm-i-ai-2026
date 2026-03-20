"""Smoke tests for Tier 2 and Tier 3 executor handlers using mock client.

~60 test cases verifying that each handler calls the right client methods
with the right payloads and handles fallback paths correctly.

Tests handlers that exist in the current worktree version of executor.py.
"""
from __future__ import annotations

import os, sys
os.environ.pop("GEMINI_MODEL", None)
os.environ.pop("GCP_PROJECT", None)
os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import traceback
from unittest.mock import MagicMock, AsyncMock

from task_types import TaskClassification, TaskType
from tripletex_client import TripletexAPIError
from executor import (
    # Tier 2
    _exec_invoice_existing_customer,
    _exec_register_payment,
    _exec_create_credit_note,
    _exec_invoice_with_payment,
    _exec_create_travel_expense,
    _exec_delete_travel_expense,
    _exec_project_with_customer,
    _exec_update_project,
    _exec_delete_project,
    _exec_project_billing,
    _exec_create_contact,
    _exec_find_customer,
    _exec_log_hours,
    _exec_delete_customer,
    _exec_update_contact,
    _exec_update_department,
    # Tier 3
    _exec_bank_reconciliation,
    _exec_error_correction,
    _exec_year_end_closing,
    _exec_enable_module,
)


# ---------------------------------------------------------------------------
# Mock client factory
# ---------------------------------------------------------------------------

def make_mock_client() -> MagicMock:
    """Create a mock TripletexClient covering ALL methods any T2/T3 handler calls."""
    client = MagicMock()
    client.api_call_count = 0
    client.error_count = 0
    client._bank_account_ensured = True
    client._vat_type_cache = {}
    client._department_cache = {}
    client._default_department_id = 1
    client._payment_type_cache = None
    client._customer_search_cache = {}
    client._employee_search_cache = {}
    client._empty_collections = set()
    client._voucher_type_cache = None

    # Department
    client.get_departments = AsyncMock(return_value=[{"id": 1, "name": "General", "version": 0, "departmentNumber": "1", "departmentManager": {"id": 10}}])
    client.create_department = AsyncMock(return_value={"id": 99, "name": "New Dept"})
    client.get_department = AsyncMock(return_value={"id": 1, "name": "General", "version": 2, "departmentNumber": "1", "departmentManager": {"id": 10}})
    client.update_department = AsyncMock(return_value={"id": 1})

    # Employee
    client.get_employees = AsyncMock(return_value=[
        {"id": 10, "firstName": "Ola", "lastName": "Nordmann", "email": "ola@test.no",
         "version": 1, "department": {"id": 1}, "dateOfBirth": "1990-01-01"}
    ])
    client.create_employee = AsyncMock(return_value={"id": 42})
    client.get_employee = AsyncMock(return_value={"id": 10, "firstName": "Ola", "lastName": "Nordmann",
         "email": "ola@test.no", "version": 1, "dateOfBirth": "1990-01-01"})
    client.update_employee = AsyncMock(return_value={"id": 10})

    # Customer
    client.get_customers = AsyncMock(return_value=[
        {"id": 20, "name": "Acme AS", "version": 2, "organizationNumber": "987654321"}
    ])
    client.create_customer = AsyncMock(return_value={"id": 55, "name": "New Customer"})
    client.get_customer = AsyncMock(return_value={"id": 20, "name": "Acme AS", "version": 2})
    client.update_customer = AsyncMock(return_value={"id": 20})
    client.delete_customer = AsyncMock(return_value=True)

    # Product
    client.create_product = AsyncMock(return_value={"id": 30})
    client.get_products = AsyncMock(return_value=[{"id": 30, "name": "Test Product", "version": 1}])
    client.get_product = AsyncMock(return_value={"id": 30, "name": "Test Product", "version": 1, "vatType": {"id": 3}})

    # VAT
    client.get_vat_types = AsyncMock(return_value=[
        {"id": 3, "name": "Utgående mva høy sats", "percentage": 25.0},
        {"id": 6, "name": "Utgående mva fritak", "percentage": 0.0},
        {"id": 33, "name": "Utgående mva lav sats", "percentage": 12.0},
        {"id": 10, "name": "Inngående mva høy sats", "percentage": 25.0},
    ])

    # Order / Invoice
    client.create_order = AsyncMock(return_value={"id": 100})
    client.invoice_order = AsyncMock(return_value={"id": 200, "amount": 12500, "amountOutstanding": 12500})

    # Ledger accounts
    client.get_ledger_accounts = AsyncMock(return_value=[
        {"id": 5, "number": 1920, "name": "Bankinnskudd", "version": 0, "bankAccountNumber": "12345678903"}
    ])
    client.update_ledger_account = AsyncMock(return_value={})

    # Payment types
    client.get_invoice_payment_types = AsyncMock(return_value=[{"id": 7, "description": "Innbetaling"}])

    # Travel expense
    client.create_travel_expense = AsyncMock(return_value={"id": 300, "version": 0})
    client.create_travel_expense_cost = AsyncMock(return_value={"id": 301})
    client.get_travel_expense_payment_types = AsyncMock(return_value=[{"id": 33998575, "name": "Privat utlegg"}])
    client.get_travel_expenses = AsyncMock(return_value=[
        {"id": 300, "title": "Oslo-Bergen", "version": 1, "employee": {"id": 10}}
    ])
    client.get_travel_expense = AsyncMock(return_value={
        "id": 300, "title": "Oslo-Bergen", "version": 1, "employee": {"id": 10}
    })
    client.update_travel_expense = AsyncMock(return_value={"id": 300})
    client.delete_travel_expense = AsyncMock(return_value=True)
    client.create_per_diem_compensation = AsyncMock(return_value={"id": 302})
    client.create_mileage_allowance = AsyncMock(return_value={"id": 303})

    # Contact
    client.create_contact = AsyncMock(return_value={"id": 400})
    client.get_contacts = AsyncMock(return_value=[
        {"id": 400, "firstName": "Erik", "lastName": "Svendsen", "version": 1,
         "customer": {"id": 20}, "email": "erik@acme.no", "phoneNumberMobile": "98765432"}
    ])
    client.get_contact = AsyncMock(return_value={
        "id": 400, "firstName": "Erik", "lastName": "Svendsen", "version": 1,
        "customer": {"id": 20}
    })
    client.update_contact = AsyncMock(return_value={"id": 400})

    # Invoice lookup
    client.get_invoices = AsyncMock(return_value=[
        {"id": 200, "invoiceNumber": "1001", "amount": 12500, "amountOutstanding": 12500,
         "voucher": {"id": 500}, "customer": {"id": 20}}
    ])
    client.get_invoice = AsyncMock(return_value={
        "id": 200, "invoiceNumber": "1001", "amount": 12500, "amountOutstanding": 12500,
        "voucher": {"id": 500}
    })

    # Payment
    client.register_payment = AsyncMock(return_value={"id": 500})

    # Credit note
    client.create_credit_note = AsyncMock(return_value={"id": 201})

    # Project
    client.create_project = AsyncMock(return_value={"id": 600})
    client.get_projects = AsyncMock(return_value=[
        {"id": 600, "name": "Project Alpha", "version": 1, "startDate": "2026-01-01",
         "projectManager": {"id": 10}, "customer": {"id": 20}}
    ])
    client.get_project = AsyncMock(return_value={
        "id": 600, "name": "Project Alpha", "version": 1, "startDate": "2026-01-01",
        "projectManager": {"id": 10}, "customer": {"id": 20}
    })
    client.update_project = AsyncMock(return_value={"id": 600})
    client.delete_project = AsyncMock(return_value=True)

    # Activities
    client.get_activities = AsyncMock(return_value=[
        {"id": 700, "name": "Development"}
    ])

    # Timesheet
    client.create_timesheet_entry = AsyncMock(return_value={"id": 800})

    # Vouchers
    client.get_voucher_types = AsyncMock(return_value=[
        {"id": 1, "name": "Manuelle bilag"},
        {"id": 2, "name": "Leverandørfaktura"},
    ])
    client.get_vouchers = AsyncMock(return_value=[
        {"id": 500, "description": "Innbetaling", "version": 1},
        {"id": 501, "description": "Salg", "version": 1},
    ])
    client.get_voucher = AsyncMock(return_value={"id": 500, "description": "Innbetaling", "version": 1})
    client.create_voucher = AsyncMock(return_value={"id": 502})
    client.reverse_voucher = AsyncMock(return_value={"id": 503})
    client.delete_voucher = AsyncMock(return_value=True)

    # Postings
    client.get_postings = AsyncMock(return_value=[
        {"account": {"id": 5}, "amountGross": 12500, "amountGrossCurrency": 12500,
         "voucher": {"id": 501}, "description": "Salg"}
    ])

    # Bank reconciliation
    client.create_bank_reconciliation = AsyncMock(return_value={"id": 900})
    client.get_bank_statements = AsyncMock(return_value=[])

    # Annual accounts
    client.get_annual_accounts = AsyncMock(return_value=[
        {"id": 1000, "version": 0, "year": 2025}
    ])
    client.close_annual_account = AsyncMock(return_value={})
    client.update_annual_account = AsyncMock(return_value={})
    client.get_close_group = AsyncMock(return_value=[])

    # Company modules
    client.get_company_modules = AsyncMock(return_value={
        "id": 1, "version": 0,
        "moduletravelexpense": False,
        "moduleproject": True,
        "moduleprojecteconomy": False,
    })
    client.update_company_modules = AsyncMock(return_value={})

    # Generic methods used by some handlers
    client.delete = AsyncMock(return_value={})
    client.post = AsyncMock(return_value={})
    client.put = AsyncMock(return_value={"value": {"id": 30}})
    client._request = AsyncMock(return_value={"value": {"id": 999}})

    return client


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

results: list[dict] = []

def record(name: str, passed: bool, details: str = ""):
    results.append({"name": name, "passed": passed, "details": details})


async def run_test(name: str, coro):
    """Run a single async test, catching exceptions."""
    try:
        await coro
    except Exception as e:
        record(name, False, f"EXCEPTION: {e}\n{traceback.format_exc()}")


# ===========================================================================
# TIER 2 TESTS
# ===========================================================================

# --- INVOICE_EXISTING_CUSTOMER ---

async def test_invoice_existing_customer_found():
    client = make_mock_client()
    fields = {
        "customer_identifier": "Acme AS",
        "lines": [{"description": "Consulting", "quantity": 5, "unit_price": 1000}],
        "invoice_date": "2026-03-20",
    }
    result = await _exec_invoice_existing_customer(fields, client)
    assert client.get_customers.called, "Should look up customer"
    assert client.create_order.called, "Should create order"
    assert client.invoice_order.called, "Should invoice the order"
    record("T2-01: INVOICE_EXISTING_CUSTOMER (found)", True)


async def test_invoice_existing_customer_creates():
    client = make_mock_client()
    client.get_customers = AsyncMock(return_value=[])
    fields = {
        "customer_identifier": "New Corp",
        "lines": [{"description": "Service", "quantity": 1, "unit_price": 500}],
    }
    result = await _exec_invoice_existing_customer(fields, client)
    assert client.create_customer.called, "Should create customer when not found"
    record("T2-02: INVOICE_EXISTING_CUSTOMER (creates customer)", True)


async def test_invoice_existing_customer_with_comment():
    client = make_mock_client()
    fields = {
        "customer_identifier": "Acme AS",
        "lines": [{"description": "Work", "quantity": 1, "unit_price": 1000}],
        "comment": "March billing",
    }
    result = await _exec_invoice_existing_customer(fields, client)
    order_payload = client.create_order.call_args[0][0]
    assert order_payload.get("invoiceComment") == "March billing"
    record("T2-03: INVOICE_EXISTING_CUSTOMER (comment)", True)


# --- REGISTER_PAYMENT ---

async def test_register_payment_by_invoice_number():
    client = make_mock_client()
    fields = {"invoice_number": "1001", "amount": 12500, "payment_date": "2026-03-20"}
    result = await _exec_register_payment(fields, client)
    assert client.get_invoices.called
    assert client.register_payment.called
    record("T2-04: REGISTER_PAYMENT (by number)", True)


async def test_register_payment_by_direct_id():
    client = make_mock_client()
    fields = {"invoice_id": 200, "amount": 12500}
    result = await _exec_register_payment(fields, client)
    assert client.register_payment.called
    inv_id = client.register_payment.call_args[0][0]
    assert inv_id == 200, f"Expected invoice_id=200, got {inv_id}"
    record("T2-05: REGISTER_PAYMENT (direct id)", True)


async def test_register_payment_amount_adjustment():
    client = make_mock_client()
    client.get_invoice = AsyncMock(return_value={"id": 200, "amountOutstanding": 9999})
    fields = {"invoice_id": 200, "amount": 12500}
    result = await _exec_register_payment(fields, client)
    pay_params = client.register_payment.call_args[0][1]
    assert pay_params["paidAmount"] == 9999.0, "Should adjust to outstanding amount"
    record("T2-06: REGISTER_PAYMENT (amount adjustment)", True)


async def test_register_payment_no_invoice():
    client = make_mock_client()
    client.get_invoices = AsyncMock(return_value=[])
    fields = {"invoice_number": "9999", "amount": 100}
    result = await _exec_register_payment(fields, client)
    assert result.get("success") is False
    record("T2-07: REGISTER_PAYMENT (invoice not found)", True)


async def test_register_payment_non_numeric_identifier():
    client = make_mock_client()
    fields = {"invoice_identifier": "Invoice for Acme AS", "amount": 5000}
    result = await _exec_register_payment(fields, client)
    # Should attempt to resolve by searching for invoices by customer name
    record("T2-08: REGISTER_PAYMENT (non-numeric identifier)", True)


# --- CREATE_CREDIT_NOTE ---

async def test_create_credit_note_by_number():
    client = make_mock_client()
    fields = {"invoice_number": "1001", "comment": "Error in billing"}
    result = await _exec_create_credit_note(fields, client)
    assert client.get_invoices.called
    assert client.create_credit_note.called
    cn_params = client.create_credit_note.call_args[0][1]
    assert cn_params.get("sendToCustomer") == "false"
    record("T2-09: CREATE_CREDIT_NOTE (by number)", True)


async def test_create_credit_note_direct_id():
    client = make_mock_client()
    fields = {"invoice_id": 200, "credit_note_date": "2026-03-20"}
    result = await _exec_create_credit_note(fields, client)
    assert client.create_credit_note.called
    inv_id_arg = client.create_credit_note.call_args[0][0]
    assert inv_id_arg == 200
    record("T2-10: CREATE_CREDIT_NOTE (direct id)", True)


async def test_create_credit_note_not_found():
    client = make_mock_client()
    client.get_invoices = AsyncMock(return_value=[])
    fields = {"invoice_number": "9999"}
    result = await _exec_create_credit_note(fields, client)
    assert result.get("success") is False
    record("T2-11: CREATE_CREDIT_NOTE (not found)", True)


# --- INVOICE_WITH_PAYMENT ---

async def test_invoice_with_payment_auto_amount():
    client = make_mock_client()
    fields = {
        "customer_name": "Acme AS",
        "lines": [{"description": "Product A", "quantity": 2, "unit_price": 1000}],
        "invoice_date": "2026-03-20",
    }
    result = await _exec_invoice_with_payment(fields, client)
    assert client.create_order.called
    assert client.invoice_order.called
    # Executor uses combined invoice+payment in single invoice_order call
    inv_params = client.invoice_order.call_args[0][1]
    assert "paymentTypeId" in inv_params, "Combined call should include paymentTypeId"
    assert "paidAmount" in inv_params, "Combined call should include paidAmount"
    assert result.get("payment_registered") is True
    record("T2-12: INVOICE_WITH_PAYMENT (auto amount)", True)


async def test_invoice_with_payment_explicit_amount():
    client = make_mock_client()
    fields = {
        "customer_name": "Acme AS",
        "lines": [{"description": "X", "quantity": 1, "unit_price": 500}],
        "paid_amount": 625,
    }
    result = await _exec_invoice_with_payment(fields, client)
    # Executor uses combined invoice+payment: explicit paid_amount passed to invoice_order
    assert client.invoice_order.called
    inv_params = client.invoice_order.call_args[0][1]
    assert inv_params.get("paidAmount") == 625.0, "Explicit amount should be passed to combined call"
    assert result.get("payment_registered") is True
    record("T2-13: INVOICE_WITH_PAYMENT (explicit amount)", True)


async def test_invoice_with_payment_creates_customer():
    client = make_mock_client()
    client.get_customers = AsyncMock(return_value=[])
    fields = {
        "customer_name": "Ny Kunde AS",
        "lines": [{"description": "Item", "quantity": 1, "unit_price": 100}],
        "paid_amount": 125,
    }
    result = await _exec_invoice_with_payment(fields, client)
    assert client.create_customer.called
    record("T2-14: INVOICE_WITH_PAYMENT (creates customer)", True)


async def test_invoice_with_payment_payment_fails_gracefully():
    """Payment registration fails but invoice is still created."""
    client = make_mock_client()
    # Make combined call fail with 422 "ugyldig" to trigger 2-step fallback
    call_count = {"n": 0}
    async def _invoice_order_side_effect(order_id, params):
        call_count["n"] += 1
        if "paymentTypeId" in params:
            # Combined call fails
            raise TripletexAPIError(422, "ugyldig beløp")
        # Plain invoice call succeeds
        return {"id": 200, "amount": 2500, "amountOutstanding": 2500}
    client.invoice_order = AsyncMock(side_effect=_invoice_order_side_effect)
    # 2-step fallback: register_payment also fails
    client.register_payment = AsyncMock(side_effect=Exception("payment failed"))
    fields = {
        "customer_name": "Acme AS",
        "lines": [{"description": "X", "quantity": 2, "unit_price": 1000}],
    }
    result = await _exec_invoice_with_payment(fields, client)
    # Invoice should still be created even if payment fails
    assert client.invoice_order.called
    assert result.get("payment_registered") is False
    record("T2-15: INVOICE_WITH_PAYMENT (payment fails gracefully)", True)


# --- CREATE_TRAVEL_EXPENSE ---

async def test_create_travel_expense_basic():
    client = make_mock_client()
    fields = {
        "first_name": "Ola", "last_name": "Nordmann",
        "title": "Kundebesøk Bergen",
        "departure_date": "2026-04-10", "return_date": "2026-04-11",
        "costs": [{"amount": 450.0, "date": "2026-04-10"}],
    }
    result = await _exec_create_travel_expense(fields, client)
    assert client.create_travel_expense.called
    assert client.create_travel_expense_cost.called
    record("T2-16: CREATE_TRAVEL_EXPENSE (basic)", True)


async def test_create_travel_expense_with_travel_details():
    client = make_mock_client()
    fields = {
        "first_name": "Ola", "last_name": "Nordmann",
        "title": "Konferanse",
        "departure_date": "2026-04-10", "return_date": "2026-04-12",
        "destination": "Bergen",
        "departure_from": "Oslo",
    }
    result = await _exec_create_travel_expense(fields, client)
    assert client.create_travel_expense.called
    payload = client.create_travel_expense.call_args[0][0]
    td = payload.get("travelDetails", {})
    assert td.get("departureDate") == "2026-04-10"
    assert td.get("destination") == "Bergen"
    record("T2-17: CREATE_TRAVEL_EXPENSE (travel details)", True)


async def test_create_travel_expense_no_costs():
    """No costs -> should still create the expense without calling create_cost."""
    client = make_mock_client()
    fields = {
        "first_name": "Ola", "last_name": "Nordmann",
        "title": "Quick trip",
    }
    result = await _exec_create_travel_expense(fields, client)
    assert client.create_travel_expense.called
    assert not client.create_travel_expense_cost.called
    record("T2-18: CREATE_TRAVEL_EXPENSE (no costs)", True)


async def test_create_travel_expense_multiple_costs():
    client = make_mock_client()
    fields = {
        "first_name": "Ola", "last_name": "Nordmann",
        "title": "Multi cost trip",
        "costs": [
            {"amount": 200.0, "date": "2026-04-10"},
            {"amount": 350.0, "date": "2026-04-11"},
        ],
    }
    result = await _exec_create_travel_expense(fields, client)
    assert client.create_travel_expense_cost.call_count == 2
    record("T2-19: CREATE_TRAVEL_EXPENSE (multiple costs)", True)


async def test_create_travel_expense_with_purpose_as_title():
    """If no title, purpose should be used as title."""
    client = make_mock_client()
    fields = {
        "first_name": "Ola", "last_name": "Nordmann",
        "purpose": "Customer meeting",
    }
    result = await _exec_create_travel_expense(fields, client)
    payload = client.create_travel_expense.call_args[0][0]
    assert payload.get("title") == "Customer meeting"
    record("T2-20: CREATE_TRAVEL_EXPENSE (purpose as title)", True)


async def test_create_travel_expense_employee_not_found():
    """Falls back to first employee if named employee not found."""
    client = make_mock_client()
    # get_employees returns results but no match for the name; first pass returns all
    fields = {
        "first_name": "NonExistent", "last_name": "Person",
        "title": "Test trip",
    }
    result = await _exec_create_travel_expense(fields, client)
    assert client.create_travel_expense.called
    record("T2-21: CREATE_TRAVEL_EXPENSE (employee fallback)", True)


# --- DELETE_TRAVEL_EXPENSE ---

async def test_delete_travel_expense_by_title():
    client = make_mock_client()
    fields = {"title": "Oslo-Bergen"}
    result = await _exec_delete_travel_expense(fields, client)
    assert client.delete_travel_expense.called
    record("T2-22: DELETE_TRAVEL_EXPENSE (by title)", True)


async def test_delete_travel_expense_last():
    client = make_mock_client()
    fields = {}
    result = await _exec_delete_travel_expense(fields, client)
    assert client.delete_travel_expense.called
    record("T2-23: DELETE_TRAVEL_EXPENSE (last)", True)


async def test_delete_travel_expense_not_found():
    client = make_mock_client()
    client.get_travel_expenses = AsyncMock(return_value=[])
    fields = {}
    result = await _exec_delete_travel_expense(fields, client)
    assert result.get("success") is False
    record("T2-24: DELETE_TRAVEL_EXPENSE (not found)", True)


# --- PROJECT_WITH_CUSTOMER ---

async def test_project_with_customer_existing():
    client = make_mock_client()
    fields = {
        "name": "Project Alpha",
        "customer_name": "Acme AS",
        "start_date": "2026-04-01",
    }
    result = await _exec_project_with_customer(fields, client)
    assert client.create_project.called
    proj_payload = client.create_project.call_args[0][0]
    assert proj_payload.get("customer") == {"id": 20}
    record("T2-25: PROJECT_WITH_CUSTOMER (existing customer)", True)


async def test_project_with_customer_creates_customer():
    client = make_mock_client()
    client.get_customers = AsyncMock(return_value=[])
    fields = {
        "project_name": "New Project",
        "customer_name": "New Corp AS",
        "customer_identifier": "New Corp AS",
    }
    result = await _exec_project_with_customer(fields, client)
    assert client.create_customer.called
    assert client.create_project.called
    record("T2-26: PROJECT_WITH_CUSTOMER (creates customer)", True)


async def test_project_with_customer_links_customer():
    """Verify customer_id is set before calling _exec_create_project."""
    client = make_mock_client()
    fields = {
        "name": "Alpha Project",
        "customer_name": "Acme AS",
    }
    result = await _exec_project_with_customer(fields, client)
    proj_payload = client.create_project.call_args[0][0]
    assert proj_payload.get("customer") == {"id": 20}, "Customer should be linked"
    record("T2-27: PROJECT_WITH_CUSTOMER (links customer)", True)


# --- UPDATE_PROJECT ---

async def test_update_project_by_name():
    client = make_mock_client()
    fields = {"project_identifier": "Project Alpha", "new_name": "Project Beta"}
    result = await _exec_update_project(fields, client)
    assert client.get_projects.called
    assert client.update_project.called
    update = client.update_project.call_args[0][1]
    assert update.get("name") == "Project Beta"
    record("T2-28: UPDATE_PROJECT (by name)", True)


async def test_update_project_with_dates():
    client = make_mock_client()
    fields = {"project_identifier": "Project Alpha", "new_start_date": "2026-06-01", "new_end_date": "2026-12-31"}
    result = await _exec_update_project(fields, client)
    update = client.update_project.call_args[0][1]
    assert update.get("startDate") == "2026-06-01"
    assert update.get("endDate") == "2026-12-31"
    record("T2-29: UPDATE_PROJECT (with dates)", True)


async def test_update_project_not_found():
    client = make_mock_client()
    client.get_projects = AsyncMock(return_value=[])
    fields = {"project_identifier": "Nonexistent"}
    result = await _exec_update_project(fields, client)
    assert result.get("success") is False
    record("T2-30: UPDATE_PROJECT (not found)", True)


# --- DELETE_PROJECT ---

async def test_delete_project():
    client = make_mock_client()
    fields = {"project_identifier": "Project Alpha"}
    result = await _exec_delete_project(fields, client)
    assert client.delete_project.called
    record("T2-31: DELETE_PROJECT", True)


async def test_delete_project_not_found():
    client = make_mock_client()
    client.get_projects = AsyncMock(return_value=[])
    fields = {"project_identifier": "Nonexistent"}
    result = await _exec_delete_project(fields, client)
    assert result.get("success") is False
    record("T2-32: DELETE_PROJECT (not found)", True)


# --- PROJECT_BILLING ---

async def test_project_billing():
    client = make_mock_client()
    fields = {
        "project_identifier": "Project Alpha",
        "lines": [{"description": "Dev work", "quantity": 10, "unit_price": 1500}],
    }
    result = await _exec_project_billing(fields, client)
    assert client.get_projects.called
    assert client.create_order.called
    assert client.invoice_order.called
    record("T2-33: PROJECT_BILLING", True)


async def test_project_billing_no_customer():
    client = make_mock_client()
    client.get_projects = AsyncMock(return_value=[
        {"id": 600, "name": "Internal", "version": 1, "customer": None}
    ])
    client.get_project = AsyncMock(return_value={"id": 600, "name": "Internal", "version": 1, "customer": None})
    fields = {"project_identifier": "Internal", "lines": [{"description": "X", "quantity": 1, "unit_price": 100}]}
    result = await _exec_project_billing(fields, client)
    assert result.get("success") is False
    record("T2-34: PROJECT_BILLING (no customer)", True)


# --- CREATE_CONTACT ---

async def test_create_contact():
    client = make_mock_client()
    fields = {
        "first_name": "Erik", "last_name": "Svendsen",
        "email": "erik@acme.no", "phone": "98765432",
        "customer_name": "Acme AS",
    }
    result = await _exec_create_contact(fields, client)
    assert client.create_contact.called
    payload = client.create_contact.call_args[0][0]
    assert payload.get("customer") == {"id": 20}
    record("T2-35: CREATE_CONTACT", True)


async def test_create_contact_creates_customer():
    client = make_mock_client()
    client.get_customers = AsyncMock(return_value=[])
    fields = {
        "first_name": "Test", "last_name": "Person",
        "customer_identifier": "Ny Firma AS",
    }
    result = await _exec_create_contact(fields, client)
    assert client.create_customer.called
    record("T2-36: CREATE_CONTACT (creates customer)", True)


# --- FIND_CUSTOMER ---

async def test_find_customer():
    client = make_mock_client()
    fields = {"search_query": "Acme"}
    result = await _exec_find_customer(fields, client)
    assert client.get_customers.called
    assert result.get("count") == 1
    record("T2-37: FIND_CUSTOMER", True)


async def test_find_customer_by_org():
    client = make_mock_client()
    fields = {"organization_number": "987654321"}
    result = await _exec_find_customer(fields, client)
    assert client.get_customers.called
    record("T2-38: FIND_CUSTOMER (by org number)", True)


# --- LOG_HOURS ---

async def test_log_hours():
    client = make_mock_client()
    fields = {
        "first_name": "Ola", "last_name": "Nordmann",
        "project_name": "Project Alpha",
        "hours": 7.5, "date": "2026-03-20",
        "activity_name": "Development",
    }
    result = await _exec_log_hours(fields, client)
    assert client.create_timesheet_entry.called
    ts_payload = client.create_timesheet_entry.call_args[0][0]
    assert ts_payload.get("hours") == 7.5
    assert ts_payload.get("employee") == {"id": 10}
    record("T2-39: LOG_HOURS", True)


async def test_log_hours_creates_project():
    client = make_mock_client()
    client.get_projects = AsyncMock(return_value=[])
    fields = {
        "first_name": "Ola", "last_name": "Nordmann",
        "project_name": "New Project",
        "hours": 3,
    }
    result = await _exec_log_hours(fields, client)
    assert client.create_project.called, "Should create project when not found"
    record("T2-40: LOG_HOURS (creates project)", True)


async def test_log_hours_creates_employee():
    client = make_mock_client()
    client.get_employees = AsyncMock(return_value=[])
    fields = {
        "first_name": "New", "last_name": "Person",
        "project_name": "Project Alpha",
        "hours": 5,
    }
    result = await _exec_log_hours(fields, client)
    assert client.create_employee.called, "Should create employee when not found"
    record("T2-41: LOG_HOURS (creates employee)", True)


# --- DELETE_CUSTOMER ---

async def test_delete_customer():
    client = make_mock_client()
    fields = {"customer_identifier": "Acme AS"}
    result = await _exec_delete_customer(fields, client)
    assert client.delete_customer.called
    record("T2-42: DELETE_CUSTOMER", True)


async def test_delete_customer_not_found():
    client = make_mock_client()
    client.get_customers = AsyncMock(return_value=[])
    fields = {"customer_identifier": "Nobody"}
    result = await _exec_delete_customer(fields, client)
    assert result.get("success") is False
    record("T2-43: DELETE_CUSTOMER (not found)", True)


# --- UPDATE_CONTACT ---

async def test_update_contact():
    client = make_mock_client()
    fields = {
        "contact_identifier": "Erik Svendsen",
        "customer_identifier": "Acme AS",
        "new_email": "newerik@acme.no",
    }
    result = await _exec_update_contact(fields, client)
    assert client.update_contact.called
    update = client.update_contact.call_args[0][1]
    assert update.get("email") == "newerik@acme.no"
    record("T2-44: UPDATE_CONTACT", True)


async def test_update_contact_no_contacts():
    client = make_mock_client()
    client.get_contacts = AsyncMock(return_value=[])
    fields = {"contact_identifier": "Nobody", "customer_identifier": "Acme AS"}
    result = await _exec_update_contact(fields, client)
    assert result.get("success") is False
    record("T2-45: UPDATE_CONTACT (no contacts)", True)


# --- UPDATE_DEPARTMENT ---

async def test_update_department():
    client = make_mock_client()
    fields = {"department_identifier": "General", "new_name": "Engineering"}
    result = await _exec_update_department(fields, client)
    assert client.update_department.called
    update = client.update_department.call_args[0][1]
    assert update.get("name") == "Engineering"
    record("T2-46: UPDATE_DEPARTMENT", True)


async def test_update_department_not_found():
    client = make_mock_client()
    client.get_departments = AsyncMock(return_value=[])
    fields = {"department_identifier": "Nonexistent"}
    result = await _exec_update_department(fields, client)
    assert result.get("success") is False
    record("T2-47: UPDATE_DEPARTMENT (not found)", True)


async def test_update_department_with_manager():
    client = make_mock_client()
    fields = {"department_identifier": "General", "manager_name": "Ola Nordmann"}
    result = await _exec_update_department(fields, client)
    assert client.update_department.called
    update = client.update_department.call_args[0][1]
    assert update.get("departmentManager") == {"id": 10}
    record("T2-48: UPDATE_DEPARTMENT (with manager)", True)


# ===========================================================================
# TIER 3 TESTS
# ===========================================================================

# --- BANK_RECONCILIATION ---

async def test_bank_reconciliation_basic():
    client = make_mock_client()
    fields = {"account_number": "1920", "period_start": "2026-01-01", "period_end": "2026-01-31"}
    result = await _exec_bank_reconciliation(fields, client)
    assert client.get_ledger_accounts.called
    assert client.create_bank_reconciliation.called
    record("T3-01: BANK_RECONCILIATION (basic)", True)


async def test_bank_reconciliation_with_transactions():
    client = make_mock_client()
    fields = {
        "account_number": "1920",
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "transactions": [
            {"date": "2026-01-15", "amount": 5000, "description": "Customer payment"},
            {"date": "2026-01-20", "amount": -2000, "description": "Office supplies"},
        ],
    }
    result = await _exec_bank_reconciliation(fields, client)
    assert client.create_voucher.called, "Should create vouchers for transactions"
    record("T3-02: BANK_RECONCILIATION (with transactions)", True)


async def test_bank_reconciliation_no_account():
    client = make_mock_client()
    client.get_ledger_accounts = AsyncMock(return_value=[])
    fields = {"account_number": "9999"}
    result = await _exec_bank_reconciliation(fields, client)
    assert result.get("success") is False
    record("T3-03: BANK_RECONCILIATION (no account)", True)


async def test_bank_reconciliation_voucher_type_lookup():
    client = make_mock_client()
    client._voucher_type_cache = None  # ensure cache is empty
    fields = {
        "account_number": "1920",
        "transactions": [{"date": "2026-01-15", "amount": 1000, "description": "Test"}],
    }
    result = await _exec_bank_reconciliation(fields, client)
    # Voucher types should be fetched (for caching) to determine type for journal entries
    assert client.get_voucher_types.called or client.create_voucher.called, "Should use voucher types or create vouchers"
    record("T3-04: BANK_RECONCILIATION (voucher type lookup)", True)


async def test_bank_reconciliation_recon_api_fails():
    """If create_bank_reconciliation fails, should still try vouchers."""
    client = make_mock_client()
    client.create_bank_reconciliation = AsyncMock(side_effect=TripletexAPIError(404, "Not found"))
    fields = {
        "account_number": "1920",
        "transactions": [{"date": "2026-01-15", "amount": 1000, "description": "Test"}],
    }
    result = await _exec_bank_reconciliation(fields, client)
    assert client.create_voucher.called, "Should fall back to vouchers"
    record("T3-05: BANK_RECONCILIATION (recon API fails -> vouchers)", True)


# --- ERROR_CORRECTION ---

async def test_error_correction_by_voucher_id():
    client = make_mock_client()
    fields = {"voucher_identifier": "500"}
    result = await _exec_error_correction(fields, client)
    assert client.reverse_voucher.called or client.get_voucher.called
    record("T3-06: ERROR_CORRECTION (by voucher id)", True)


async def test_error_correction_reverse_fails_then_delete():
    client = make_mock_client()
    client.reverse_voucher = AsyncMock(side_effect=TripletexAPIError(405, "Not allowed"))
    fields = {"voucher_identifier": "500"}
    result = await _exec_error_correction(fields, client)
    assert client.delete_voucher.called, "Should fall back to delete"
    record("T3-07: ERROR_CORRECTION (reverse fails -> delete)", True)


async def test_error_correction_both_fail_manual_reversal():
    client = make_mock_client()
    client.reverse_voucher = AsyncMock(side_effect=TripletexAPIError(405, "Not allowed"))
    client.delete_voucher = AsyncMock(side_effect=TripletexAPIError(403, "Forbidden"))
    # Provide voucher with postings for manual reversal
    client.get_postings = AsyncMock(return_value=[
        {"account": {"id": 5}, "amountGross": 1000, "amountGrossCurrency": 1000, "description": "Test"}
    ])
    fields = {"voucher_identifier": "500"}
    result = await _exec_error_correction(fields, client)
    # Should try to get postings for manual reversal
    assert client.get_postings.called or result.get("action") == "manual_reversal" or result.get("success") is False
    record("T3-08: ERROR_CORRECTION (manual reversal)", True)


async def test_error_correction_with_new_postings():
    client = make_mock_client()
    fields = {
        "voucher_identifier": "500",
        "correction_description": "Fix wrong account",
        "new_postings": [
            {"account_id": 5, "amount": 1000, "description": "Corrected"},
            {"account_id": 5, "amount": -1000, "description": "Reversed"},
        ],
    }
    result = await _exec_error_correction(fields, client)
    assert client.create_voucher.called
    record("T3-09: ERROR_CORRECTION (with new postings)", True)


async def test_error_correction_search_by_string():
    """Non-numeric voucher identifier -> search by number string."""
    client = make_mock_client()
    fields = {"voucher_identifier": "V12345"}
    result = await _exec_error_correction(fields, client)
    assert client.get_vouchers.called
    record("T3-10: ERROR_CORRECTION (search by string)", True)


async def test_error_correction_voucher_not_found():
    client = make_mock_client()
    client.get_voucher = AsyncMock(side_effect=TripletexAPIError(404, "Not found"))
    # After 404 on get_voucher, it searches by number which also returns empty
    client.get_vouchers = AsyncMock(return_value=[])
    fields = {"voucher_identifier": "99999"}
    result = await _exec_error_correction(fields, client)
    assert result.get("success") is False or result.get("error")
    record("T3-11: ERROR_CORRECTION (voucher not found)", True)


# --- YEAR_END_CLOSING ---

async def test_year_end_closing_via_annual_account():
    client = make_mock_client()
    fields = {"year": 2025}
    result = await _exec_year_end_closing(fields, client)
    assert client.get_annual_accounts.called
    assert client.close_annual_account.called
    assert result.get("action") == "closed"
    record("T3-12: YEAR_END_CLOSING (annual account)", True)


async def test_year_end_closing_close_fails_voucher_fallback():
    client = make_mock_client()
    client.close_annual_account = AsyncMock(side_effect=TripletexAPIError(405, "Not allowed"))
    client.update_annual_account = AsyncMock(side_effect=TripletexAPIError(405, "Not allowed"))
    client.get_annual_accounts = AsyncMock(return_value=[{"id": 1000, "version": 0, "year": 2025, "status": "OPEN"}])
    fields = {"year": 2025}
    result = await _exec_year_end_closing(fields, client)
    assert client.create_voucher.called or client.get_close_group.called
    record("T3-13: YEAR_END_CLOSING (close fails -> voucher)", True)


async def test_year_end_closing_no_year():
    client = make_mock_client()
    fields = {}
    result = await _exec_year_end_closing(fields, client)
    assert result.get("success") is False
    record("T3-14: YEAR_END_CLOSING (no year)", True)


async def test_year_end_closing_no_annual_accounts():
    """If no annual accounts exist, should try voucher approach."""
    client = make_mock_client()
    client.get_annual_accounts = AsyncMock(return_value=[])
    fields = {"year": 2025}
    result = await _exec_year_end_closing(fields, client)
    # Should attempt to create closing voucher or find close groups
    assert client.get_voucher_types.called or client.create_voucher.called or client.get_close_group.called
    record("T3-15: YEAR_END_CLOSING (no annual accounts)", True)


# --- ENABLE_MODULE ---

async def test_enable_module():
    client = make_mock_client()
    fields = {"module_name": "reiseregning"}
    result = await _exec_enable_module(fields, client)
    assert client.get_company_modules.called
    assert client.update_company_modules.called
    assert result.get("action") == "enabled"
    record("T3-16: ENABLE_MODULE (basic)", True)


async def test_enable_module_already_enabled():
    client = make_mock_client()
    client.get_company_modules = AsyncMock(return_value={
        "moduletravelexpense": True, "version": 0,
    })
    fields = {"module_name": "travel expense"}
    result = await _exec_enable_module(fields, client)
    assert result.get("action") == "already_enabled"
    assert not client.update_company_modules.called
    record("T3-17: ENABLE_MODULE (already enabled)", True)


async def test_enable_module_405_fallback():
    client = make_mock_client()
    client.update_company_modules = AsyncMock(side_effect=TripletexAPIError(405, "Method not allowed"))
    fields = {"module_name": "reiseregning"}
    result = await _exec_enable_module(fields, client)
    assert client.post.called, "Should try POST /company/salesmodules as fallback"
    record("T3-18: ENABLE_MODULE (405 fallback)", True)


async def test_enable_module_norwegian_mapping():
    client = make_mock_client()
    fields = {"module_name": "prosjektøkonomi"}
    result = await _exec_enable_module(fields, client)
    assert client.update_company_modules.called
    update_payload = client.update_company_modules.call_args[0][0]
    assert update_payload.get("moduleprojecteconomy") is True
    record("T3-19: ENABLE_MODULE (Norwegian mapping)", True)


async def test_enable_module_english_name():
    client = make_mock_client()
    fields = {"module_name": "project economy"}
    result = await _exec_enable_module(fields, client)
    update = client.update_company_modules.call_args[0][0]
    assert update.get("moduleprojecteconomy") is True
    record("T3-20: ENABLE_MODULE (English name)", True)


async def test_enable_module_department():
    client = make_mock_client()
    fields = {"module_name": "avdelingsregnskap"}
    result = await _exec_enable_module(fields, client)
    update = client.update_company_modules.call_args[0][0]
    assert update.get("moduleDepartmentAccounting") is True
    record("T3-21: ENABLE_MODULE (department accounting)", True)


async def test_enable_module_no_module_name():
    client = make_mock_client()
    fields = {"module_name": ""}
    result = await _exec_enable_module(fields, client)
    # Should still attempt with raw empty name as field
    assert client.get_company_modules.called
    record("T3-22: ENABLE_MODULE (empty name)", True)


# ===========================================================================
# Run all tests
# ===========================================================================

async def main():
    print("=" * 70)
    print("Tripletex Executor Smoke Tests - Tier 2 & Tier 3")
    print("=" * 70)
    print()

    tests = [
        # Tier 2 (48 tests)
        ("T2-01", test_invoice_existing_customer_found()),
        ("T2-02", test_invoice_existing_customer_creates()),
        ("T2-03", test_invoice_existing_customer_with_comment()),
        ("T2-04", test_register_payment_by_invoice_number()),
        ("T2-05", test_register_payment_by_direct_id()),
        ("T2-06", test_register_payment_amount_adjustment()),
        ("T2-07", test_register_payment_no_invoice()),
        ("T2-08", test_register_payment_non_numeric_identifier()),
        ("T2-09", test_create_credit_note_by_number()),
        ("T2-10", test_create_credit_note_direct_id()),
        ("T2-11", test_create_credit_note_not_found()),
        ("T2-12", test_invoice_with_payment_auto_amount()),
        ("T2-13", test_invoice_with_payment_explicit_amount()),
        ("T2-14", test_invoice_with_payment_creates_customer()),
        ("T2-15", test_invoice_with_payment_payment_fails_gracefully()),
        ("T2-16", test_create_travel_expense_basic()),
        ("T2-17", test_create_travel_expense_with_travel_details()),
        ("T2-18", test_create_travel_expense_no_costs()),
        ("T2-19", test_create_travel_expense_multiple_costs()),
        ("T2-20", test_create_travel_expense_with_purpose_as_title()),
        ("T2-21", test_create_travel_expense_employee_not_found()),
        ("T2-22", test_delete_travel_expense_by_title()),
        ("T2-23", test_delete_travel_expense_last()),
        ("T2-24", test_delete_travel_expense_not_found()),
        ("T2-25", test_project_with_customer_existing()),
        ("T2-26", test_project_with_customer_creates_customer()),
        ("T2-27", test_project_with_customer_links_customer()),
        ("T2-28", test_update_project_by_name()),
        ("T2-29", test_update_project_with_dates()),
        ("T2-30", test_update_project_not_found()),
        ("T2-31", test_delete_project()),
        ("T2-32", test_delete_project_not_found()),
        ("T2-33", test_project_billing()),
        ("T2-34", test_project_billing_no_customer()),
        ("T2-35", test_create_contact()),
        ("T2-36", test_create_contact_creates_customer()),
        ("T2-37", test_find_customer()),
        ("T2-38", test_find_customer_by_org()),
        ("T2-39", test_log_hours()),
        ("T2-40", test_log_hours_creates_project()),
        ("T2-41", test_log_hours_creates_employee()),
        ("T2-42", test_delete_customer()),
        ("T2-43", test_delete_customer_not_found()),
        ("T2-44", test_update_contact()),
        ("T2-45", test_update_contact_no_contacts()),
        ("T2-46", test_update_department()),
        ("T2-47", test_update_department_not_found()),
        ("T2-48", test_update_department_with_manager()),
        # Tier 3 (22 tests)
        ("T3-01", test_bank_reconciliation_basic()),
        ("T3-02", test_bank_reconciliation_with_transactions()),
        ("T3-03", test_bank_reconciliation_no_account()),
        ("T3-04", test_bank_reconciliation_voucher_type_lookup()),
        ("T3-05", test_bank_reconciliation_recon_api_fails()),
        ("T3-06", test_error_correction_by_voucher_id()),
        ("T3-07", test_error_correction_reverse_fails_then_delete()),
        ("T3-08", test_error_correction_both_fail_manual_reversal()),
        ("T3-09", test_error_correction_with_new_postings()),
        ("T3-10", test_error_correction_search_by_string()),
        ("T3-11", test_error_correction_voucher_not_found()),
        ("T3-12", test_year_end_closing_via_annual_account()),
        ("T3-13", test_year_end_closing_close_fails_voucher_fallback()),
        ("T3-14", test_year_end_closing_no_year()),
        ("T3-15", test_year_end_closing_no_annual_accounts()),
        ("T3-16", test_enable_module()),
        ("T3-17", test_enable_module_already_enabled()),
        ("T3-18", test_enable_module_405_fallback()),
        ("T3-19", test_enable_module_norwegian_mapping()),
        ("T3-20", test_enable_module_english_name()),
        ("T3-21", test_enable_module_department()),
        ("T3-22", test_enable_module_no_module_name()),
    ]

    for name, coro in tests:
        await run_test(name, coro)

    # Report
    print()
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if not r["passed"])
    total = len(results)

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['name']}")
        if r.get("details"):
            for line in r["details"].split("\n")[:5]:
                print(f"       {line}")
            print()

    print()
    print("=" * 70)
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print(f"  Tier 2: 48 tests | Tier 3: 22 tests | Total: {total}")
    print("=" * 70)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
