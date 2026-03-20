from __future__ import annotations

"""Async Tripletex v2 API client.

Auth: Basic Auth with username "0" and password = session_token.
All Tripletex API calls go through the proxy URL provided in each request.

CRITICAL: Every unnecessary API call and every 4xx error hurts the
efficiency bonus (up to 2× score multiplier). Track both.
"""

import asyncio
import json
import logging

import httpx


def _log(severity: str, message: str, **extra):
    entry = {"severity": severity, "message": message, **extra}
    print(json.dumps(entry), flush=True)


class TripletexAPIError(Exception):
    """Raised on non-retryable Tripletex API errors."""

    def __init__(self, status_code: int, detail: str, url: str = ""):
        self.status_code = status_code
        self.detail = detail
        self.url = url
        super().__init__(f"Tripletex {status_code}: {detail} ({url})")


class TripletexClient:
    """Async wrapper around the Tripletex v2 REST API.

    - Basic Auth: ("0", session_token)
    - 30s timeout per request
    - Auto-extract values from response wrapper
    - Track api_call_count and error_count for efficiency scoring
    - Log every request/response for debugging
    - Single retry on 5xx with 1s backoff
    """

    def __init__(self, base_url: str, session_token: str):
        self.base_url = base_url.rstrip("/")
        self.session_token = session_token
        self._client = httpx.AsyncClient(
            auth=("0", session_token),
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        # Efficiency tracking
        self.api_call_count = 0
        self.error_count = 0

        # Per-request caches (auto-reset per /solve — each creates a new client)
        self._bank_account_ensured: bool = False
        self._bank_account_data: dict | None = None  # cached ledger account 1920 data
        self._vat_type_cache: dict[float, int] = {}  # vat_pct -> vatType ID
        self._department_cache: dict[str, int] = {}   # dept_name -> dept ID
        self._default_department_id: int | None = None # first/default dept ID
        self._payment_type_cache: list | None = None   # invoice payment types
        self._customer_search_cache: dict[str, dict | None] = {}  # name -> customer or None
        self._employee_search_cache: dict[str, dict | None] = {}  # name -> employee or None
        self._empty_collections: set[str] = set()  # entity types known to be empty (e.g. "customers", "employees")

    async def close(self):
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal request handler
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an API request. Retries once on 5xx. Never retries 4xx."""
        url = f"{self.base_url}{path}"
        self.api_call_count += 1
        call_num = self.api_call_count
        _log("INFO", f"API #{call_num}: {method} {path}",
             api_call_number=call_num)

        response = await self._client.request(method, url, **kwargs)

        # 5xx — retry once after 1s
        if response.status_code >= 500:
            _log("WARNING", f"5xx error, retrying", status=response.status_code, path=path)
            await asyncio.sleep(1)
            self.api_call_count += 1
            response = await self._client.request(method, url, **kwargs)

        if response.status_code >= 400:
            self.error_count += 1
            detail = response.text[:500]
            _log("ERROR", "API error", status=response.status_code, path=path,
                 detail=detail, total_calls=self.api_call_count, total_errors=self.error_count)
            raise TripletexAPIError(response.status_code, detail, url)

        # DELETE often returns 204 with no body
        if response.status_code == 204 or not response.content:
            return {}

        data = response.json()
        _log("DEBUG", f"API #{call_num} response OK", status=response.status_code, path=path)
        return data

    def _extract_value(self, data: dict) -> dict:
        """Extract the 'value' key from single-entity responses."""
        return data.get("value", data)

    def _extract_values(self, data: dict) -> list:
        """Extract the 'values' key from list responses."""
        return data.get("values", [])

    # ------------------------------------------------------------------
    # Generic methods
    # ------------------------------------------------------------------

    async def get(self, path: str, params: dict | None = None) -> dict:
        """Generic GET."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, data: dict | None = None) -> dict:
        """Generic POST."""
        return await self._request("POST", path, json=data)

    async def put(self, path: str, data: dict | None = None, params: dict | None = None) -> dict:
        """Generic PUT (with optional query params for action endpoints)."""
        kwargs = {}
        if data is not None:
            kwargs["json"] = data
        if params is not None:
            kwargs["params"] = params
        return await self._request("PUT", path, **kwargs)

    async def delete(self, path: str) -> dict:
        """Generic DELETE."""
        return await self._request("DELETE", path)

    # ------------------------------------------------------------------
    # Employee
    # ------------------------------------------------------------------

    async def create_employee(self, data: dict) -> dict:
        resp = await self._request("POST", "/employee", json=data)
        return self._extract_value(resp)

    async def get_employees(self, params: dict | None = None) -> list:
        """GET /employee — search employees.

        IMPORTANT: Only firstName and email query params work for filtering.
        lastName, name, departmentId, id, employeeNumber do NOT work.
        Use includeContacts=true to include contact-flagged employees.
        Always request fields=* to get version numbers for PUT.
        """
        p = dict(params or {})
        p.setdefault("fields", "*")
        resp = await self._request("GET", "/employee", params=p)
        return self._extract_values(resp)

    async def get_employee(self, id: int) -> dict:
        resp = await self._request("GET", f"/employee/{id}", params={"fields": "*"})
        return self._extract_value(resp)

    async def update_employee(self, id: int, data: dict) -> dict:
        resp = await self._request("PUT", f"/employee/{id}", json=data)
        return self._extract_value(resp)

    async def delete_employee(self, id: int) -> bool:
        await self._request("DELETE", f"/employee/{id}")
        return True

    # ------------------------------------------------------------------
    # Customer
    # ------------------------------------------------------------------

    async def create_customer(self, data: dict) -> dict:
        resp = await self._request("POST", "/customer", json=data)
        return self._extract_value(resp)

    async def get_customers(self, params: dict | None = None) -> list:
        p = dict(params or {})
        p.setdefault("fields", "*")
        resp = await self._request("GET", "/customer", params=p)
        return self._extract_values(resp)

    async def get_customer(self, id: int) -> dict:
        resp = await self._request("GET", f"/customer/{id}", params={"fields": "*"})
        return self._extract_value(resp)

    async def update_customer(self, id: int, data: dict) -> dict:
        resp = await self._request("PUT", f"/customer/{id}", json=data)
        return self._extract_value(resp)

    async def delete_customer(self, id: int) -> bool:
        await self._request("DELETE", f"/customer/{id}")
        return True

    # ------------------------------------------------------------------
    # Product
    # ------------------------------------------------------------------

    async def create_product(self, data: dict) -> dict:
        resp = await self._request("POST", "/product", json=data)
        return self._extract_value(resp)

    async def get_products(self, params: dict | None = None) -> list:
        resp = await self._request("GET", "/product", params=params)
        return self._extract_values(resp)

    async def get_product(self, id: int) -> dict:
        resp = await self._request("GET", f"/product/{id}")
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # VAT Type
    # ------------------------------------------------------------------

    async def get_vat_types(self, params: dict | None = None) -> list:
        """GET /ledger/vatType — list available VAT types."""
        resp = await self._request("GET", "/ledger/vatType", params=params)
        return self._extract_values(resp)

    # ------------------------------------------------------------------
    # Order + Order Lines
    # ------------------------------------------------------------------

    async def create_order(self, data: dict) -> dict:
        resp = await self._request("POST", "/order", json=data)
        return self._extract_value(resp)

    async def create_order_line(self, data: dict) -> dict:
        """POST /order/orderline — add a line to an existing order."""
        resp = await self._request("POST", "/order/orderline", json=data)
        return self._extract_value(resp)

    async def get_orders(self, params: dict | None = None) -> list:
        resp = await self._request("GET", "/order", params=params)
        return self._extract_values(resp)

    async def get_order(self, id: int) -> dict:
        resp = await self._request("GET", f"/order/{id}")
        return self._extract_value(resp)

    async def invoice_order(self, order_id: int, params: dict | None = None) -> dict:
        """PUT /order/{id}/:invoice — converts order to invoice.

        Query params only, no body. Key params:
        invoiceDate (required), sendToCustomer, paymentTypeId, paidAmount.
        """
        resp = await self._request("PUT", f"/order/{order_id}/:invoice", params=params or {})
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Invoice
    # ------------------------------------------------------------------

    async def get_invoices(self, params: dict | None = None) -> list:
        resp = await self._request("GET", "/invoice", params=params)
        return self._extract_values(resp)

    async def get_invoice(self, id: int) -> dict:
        resp = await self._request("GET", f"/invoice/{id}")
        return self._extract_value(resp)

    async def register_payment(self, invoice_id: int, params: dict) -> dict:
        """PUT /invoice/{id}/:payment — query params only.

        Required: paymentDate, paymentTypeId, paidAmount.
        """
        resp = await self._request("PUT", f"/invoice/{invoice_id}/:payment", params=params)
        return self._extract_value(resp)

    async def create_credit_note(self, invoice_id: int, params: dict | None = None) -> dict:
        """PUT /invoice/{id}/:createCreditNote — query params only.

        Required: date. Optional: comment, sendToCustomer.
        """
        resp = await self._request("PUT", f"/invoice/{invoice_id}/:createCreditNote", params=params or {})
        return self._extract_value(resp)

    async def get_invoice_payment_types(self) -> list:
        """GET /invoice/paymentType — list available incoming payment types."""
        resp = await self._request("GET", "/invoice/paymentType")
        return self._extract_values(resp)

    # ------------------------------------------------------------------
    # Department
    # ------------------------------------------------------------------

    async def create_department(self, data: dict) -> dict:
        resp = await self._request("POST", "/department", json=data)
        return self._extract_value(resp)

    async def get_departments(self, params: dict | None = None) -> list:
        resp = await self._request("GET", "/department", params=params)
        return self._extract_values(resp)

    async def get_department(self, id: int) -> dict:
        resp = await self._request("GET", f"/department/{id}")
        return self._extract_value(resp)

    async def update_department(self, id: int, data: dict) -> dict:
        resp = await self._request("PUT", f"/department/{id}", json=data)
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Project
    # ------------------------------------------------------------------

    async def create_project(self, data: dict) -> dict:
        resp = await self._request("POST", "/project", json=data)
        return self._extract_value(resp)

    async def get_projects(self, params: dict | None = None) -> list:
        resp = await self._request("GET", "/project", params=params)
        return self._extract_values(resp)

    async def get_project(self, id: int) -> dict:
        resp = await self._request("GET", f"/project/{id}", params={"fields": "*"})
        return self._extract_value(resp)

    async def update_project(self, id: int, data: dict) -> dict:
        resp = await self._request("PUT", f"/project/{id}", json=data)
        return self._extract_value(resp)

    async def delete_project(self, id: int) -> bool:
        await self._request("DELETE", f"/project/{id}")
        return True

    # ------------------------------------------------------------------
    # Travel Expense
    # ------------------------------------------------------------------

    async def create_travel_expense(self, data: dict) -> dict:
        """POST /travelExpense — minimum: employee ref + title."""
        resp = await self._request("POST", "/travelExpense", json=data)
        return self._extract_value(resp)

    async def create_travel_expense_cost(self, data: dict) -> dict:
        """POST /travelExpense/cost — add a cost line to a travel expense.

        Required: travelExpense ref, paymentType ref, amountCurrencyIncVat.
        """
        resp = await self._request("POST", "/travelExpense/cost", json=data)
        return self._extract_value(resp)

    async def get_travel_expenses(self, params: dict | None = None) -> list:
        p = dict(params or {})
        p.setdefault("fields", "*")
        resp = await self._request("GET", "/travelExpense", params=p)
        return self._extract_values(resp)

    async def get_travel_expense(self, id: int) -> dict:
        resp = await self._request("GET", f"/travelExpense/{id}", params={"fields": "*"})
        return self._extract_value(resp)

    async def update_travel_expense(self, id: int, data: dict) -> dict:
        resp = await self._request("PUT", f"/travelExpense/{id}", json=data)
        return self._extract_value(resp)

    async def delete_travel_expense(self, id: int) -> bool:
        await self._request("DELETE", f"/travelExpense/{id}")
        return True

    async def get_travel_expense_payment_types(self) -> list:
        """GET /travelExpense/paymentType — e.g. 'Privat utlegg' (id=33998575)."""
        resp = await self._request("GET", "/travelExpense/paymentType")
        return self._extract_values(resp)

    async def get_travel_expense_cost_categories(self) -> list:
        """GET /travelExpense/costCategory — e.g. 'Bredbånd', 'Kontorrekvisita'."""
        resp = await self._request("GET", "/travelExpense/costCategory")
        return self._extract_values(resp)

    async def create_per_diem_compensation(self, data: dict) -> dict:
        """POST /travelExpense/perDiemCompensation — add per diem to a travel expense."""
        resp = await self._request("POST", "/travelExpense/perDiemCompensation", json=data)
        return self._extract_value(resp)

    async def get_rate_categories(self, params: dict | None = None) -> list:
        """GET /travelExpense/rateCategory — rate categories for per diem and mileage."""
        p = dict(params or {})
        p.setdefault("count", 100)
        resp = await self._request("GET", "/travelExpense/rateCategory", params=p)
        return self._extract_values(resp)

    async def create_mileage_allowance(self, data: dict) -> dict:
        """POST /travelExpense/mileageAllowance — add mileage allowance to travel expense."""
        resp = await self._request("POST", "/travelExpense/mileageAllowance", json=data)
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Ledger Account (for bank account setup before invoicing)
    # ------------------------------------------------------------------

    async def get_ledger_accounts(self, params: dict | None = None) -> list:
        """GET /ledger/account — find accounts (e.g. ?number=1920 for bank)."""
        resp = await self._request("GET", "/ledger/account", params=params)
        return self._extract_values(resp)

    async def update_ledger_account(self, id: int, data: dict) -> dict:
        """PUT /ledger/account/{id} — update account (e.g. set bankAccountNumber)."""
        resp = await self._request("PUT", f"/ledger/account/{id}", json=data)
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Contact
    # ------------------------------------------------------------------

    async def create_contact(self, data: dict) -> dict:
        resp = await self._request("POST", "/contact", json=data)
        return self._extract_value(resp)

    async def get_contacts(self, params: dict | None = None) -> list:
        resp = await self._request("GET", "/contact", params=params)
        return self._extract_values(resp)

    async def get_contact(self, id: int) -> dict:
        resp = await self._request("GET", f"/contact/{id}")
        return self._extract_value(resp)

    async def update_contact(self, id: int, data: dict) -> dict:
        resp = await self._request("PUT", f"/contact/{id}", json=data)
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Accounting Dimensions (Tier 3 — free dimensions / regnskapsdimensjon)
    # ------------------------------------------------------------------

    async def get_dimension_names(self, params: dict | None = None) -> list:
        """GET /ledger/accountingDimensionName — list dimension names."""
        resp = await self._request("GET", "/ledger/accountingDimensionName", params=params)
        return self._extract_values(resp)

    async def create_dimension_name(self, data: dict) -> dict:
        """POST /ledger/accountingDimensionName — create a free dimension."""
        resp = await self._request("POST", "/ledger/accountingDimensionName", json=data)
        return self._extract_value(resp)

    async def search_dimension_values(self, params: dict | None = None) -> list:
        """GET /ledger/accountingDimensionValue/search — search dimension values."""
        resp = await self._request("GET", "/ledger/accountingDimensionValue/search", params=params)
        return self._extract_values(resp)

    async def create_dimension_value(self, data: dict) -> dict:
        """POST /ledger/accountingDimensionValue — create a value for a dimension."""
        resp = await self._request("POST", "/ledger/accountingDimensionValue", json=data)
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Ledger Voucher (Tier 3)
    # ------------------------------------------------------------------

    async def create_voucher(self, data: dict, send_to_ledger: bool = False) -> dict:
        resp = await self._request("POST", "/ledger/voucher",
                                   json=data,
                                   params={"sendToLedger": str(send_to_ledger).lower()})
        return self._extract_value(resp)

    async def get_vouchers(self, params: dict | None = None) -> list:
        """GET /ledger/voucher — list vouchers."""
        p = dict(params or {})
        p.setdefault("fields", "*")
        resp = await self._request("GET", "/ledger/voucher", params=p)
        return self._extract_values(resp)

    async def get_voucher(self, id: int) -> dict:
        """GET /ledger/voucher/{id} — get voucher details."""
        resp = await self._request("GET", f"/ledger/voucher/{id}", params={"fields": "*"})
        return self._extract_value(resp)

    async def delete_voucher(self, id: int) -> bool:
        """DELETE /ledger/voucher/{id} — delete a voucher if allowed."""
        await self._request("DELETE", f"/ledger/voucher/{id}")
        return True

    async def reverse_voucher(self, id: int, params: dict | None = None) -> dict:
        """PUT /ledger/voucher/{id}/:reverse — reverse a voucher."""
        resp = await self._request("PUT", f"/ledger/voucher/{id}/:reverse", params=params or {})
        return self._extract_value(resp)

    async def get_postings(self, params: dict | None = None) -> list:
        """GET /ledger/posting — list postings."""
        p = dict(params or {})
        p.setdefault("fields", "*")
        resp = await self._request("GET", "/ledger/posting", params=p)
        return self._extract_values(resp)

    async def get_voucher_types(self, params: dict | None = None) -> list:
        """GET /ledger/voucherType — list voucher types."""
        resp = await self._request("GET", "/ledger/voucherType", params=params)
        return self._extract_values(resp)

    # ------------------------------------------------------------------
    # Incoming Invoice (supplier invoice)
    # ------------------------------------------------------------------

    async def create_incoming_invoice(self, data: dict) -> dict:
        """POST /incomingInvoice — register a supplier/incoming invoice."""
        resp = await self._request("POST", "/incomingInvoice", json=data)
        return self._extract_value(resp)

    async def get_incoming_invoice_vat_types(self, params: dict | None = None) -> list:
        """GET /incomingInvoice/vatType — list incoming invoice VAT types."""
        resp = await self._request("GET", "/incomingInvoice/vatType", params=params or {"count": 100})
        return self._extract_values(resp)

    # ------------------------------------------------------------------
    # Employment (prerequisite for salary)
    # ------------------------------------------------------------------

    async def get_employments(self, params: dict | None = None) -> list:
        """GET /employee/employment — list employments."""
        resp = await self._request("GET", "/employee/employment", params=params)
        return self._extract_values(resp)

    async def create_employment(self, data: dict) -> dict:
        """POST /employee/employment — create an employment record for an employee."""
        resp = await self._request("POST", "/employee/employment", json=data)
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Salary / Payroll (Tier 3)
    # ------------------------------------------------------------------

    async def create_salary_transaction(self, data: dict) -> dict:
        """POST /salary/transaction — create a salary/payroll transaction."""
        resp = await self._request("POST", "/salary/transaction", json=data)
        return self._extract_value(resp)

    async def get_salary_transactions(self, params: dict | None = None) -> list:
        """GET /salary/transaction — list salary transactions."""
        resp = await self._request("GET", "/salary/transaction", params=params)
        return self._extract_values(resp)

    async def get_salary_types(self, params: dict | None = None) -> list:
        """GET /salary/type — list salary types (Fastlønn, Bonus, etc.)."""
        p = dict(params or {})
        p.setdefault("count", 100)
        resp = await self._request("GET", "/salary/type", params=p)
        return self._extract_values(resp)

    async def get_payslips(self, params: dict | None = None) -> list:
        """GET /salary/payslip — list payslips."""
        resp = await self._request("GET", "/salary/payslip", params=params)
        return self._extract_values(resp)

    async def get_payslip(self, id: int) -> dict:
        """GET /salary/payslip/{id}."""
        resp = await self._request("GET", f"/salary/payslip/{id}", params={"fields": "*"})
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Annual Account / Year-End (Tier 3)
    # ------------------------------------------------------------------

    async def get_annual_accounts(self, params: dict | None = None) -> list:
        """GET /ledger/annualAccount — list annual account records."""
        resp = await self._request("GET", "/ledger/annualAccount", params=params)
        return self._extract_values(resp)

    async def get_annual_account(self, id: int) -> dict:
        """GET /ledger/annualAccount/{id}."""
        resp = await self._request("GET", f"/ledger/annualAccount/{id}", params={"fields": "*"})
        return self._extract_value(resp)

    async def update_annual_account(self, id: int, data: dict) -> dict:
        """PUT /ledger/annualAccount/{id} — close/update annual account."""
        resp = await self._request("PUT", f"/ledger/annualAccount/{id}", json=data)
        return self._extract_value(resp)

    async def close_annual_account(self, id: int, params: dict | None = None) -> dict:
        """PUT /ledger/annualAccount/{id}/:close — close the annual account."""
        resp = await self._request("PUT", f"/ledger/annualAccount/{id}/:close", params=params or {})
        return self._extract_value(resp)

    async def get_company_info(self, params: dict | None = None) -> dict:
        """GET /company — get company info including fiscal year settings."""
        resp = await self._request("GET", "/company", params=params or {"fields": "*"})
        return self._extract_value(resp)

    async def get_company_by_id(self, company_id: int) -> dict:
        """GET /company/{id} — get company by ID."""
        resp = await self._request("GET", f"/company/{company_id}", params={"fields": "*"})
        return self._extract_value(resp)

    async def get_close_group(self, params: dict | None = None) -> list:
        """GET /ledger/closeGroup — list close groups for year-end."""
        resp = await self._request("GET", "/ledger/closeGroup", params=params)
        return self._extract_values(resp)

    # ------------------------------------------------------------------
    # Activity / Timesheet (Tier 2+)
    # ------------------------------------------------------------------

    async def get_activities(self, params: dict | None = None) -> list:
        resp = await self._request("GET", "/activity", params=params)
        return self._extract_values(resp)

    async def create_activity(self, data: dict) -> dict:
        resp = await self._request("POST", "/activity", json=data)
        return self._extract_value(resp)

    async def create_timesheet_entry(self, data: dict) -> dict:
        resp = await self._request("POST", "/timesheet/entry", json=data)
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Supplier (Tier 2)
    # ------------------------------------------------------------------

    async def create_supplier(self, data: dict) -> dict:
        resp = await self._request("POST", "/supplier", json=data)
        return self._extract_value(resp)

    async def get_suppliers(self, params: dict | None = None) -> list:
        p = dict(params or {})
        p.setdefault("fields", "*")
        resp = await self._request("GET", "/supplier", params=p)
        return self._extract_values(resp)

    async def get_supplier(self, id: int) -> dict:
        resp = await self._request("GET", f"/supplier/{id}", params={"fields": "*"})
        return self._extract_value(resp)

    async def update_supplier(self, id: int, data: dict) -> dict:
        resp = await self._request("PUT", f"/supplier/{id}", json=data)
        return self._extract_value(resp)

    async def delete_supplier(self, id: int) -> bool:
        await self._request("DELETE", f"/supplier/{id}")
        return True

    # ------------------------------------------------------------------
    # Company Modules
    # ------------------------------------------------------------------

    async def get_company_modules(self) -> dict:
        """GET /company/modules — returns module flags (boolean fields).

        Response contains fields like moduleproject, moduletravelexpense,
        moduleDepartmentAccounting, completeMonthlyHourLists, etc.
        """
        resp = await self._request("GET", "/company/modules", params={"fields": "*"})
        return self._extract_value(resp)

    async def update_company_modules(self, data: dict) -> dict:
        """PUT /company/modules — enable/disable module flags.

        NOTE: May return 405 in some sandbox environments.
        Requires version field for optimistic locking.
        """
        resp = await self._request("PUT", "/company/modules", json=data)
        return self._extract_value(resp)

    # ------------------------------------------------------------------
    # Bank Reconciliation (Tier 3)
    # ------------------------------------------------------------------

    async def get_bank_reconciliation(self, params: dict | None = None) -> list:
        """GET /bank/reconciliation — list bank reconciliation entries."""
        resp = await self._request("GET", "/bank/reconciliation", params=params)
        return self._extract_values(resp)

    async def create_bank_reconciliation(self, data: dict) -> dict:
        """POST /bank/reconciliation — create a bank reconciliation.

        Required: account (ref), type, date.
        """
        resp = await self._request("POST", "/bank/reconciliation", json=data)
        return self._extract_value(resp)

    async def update_bank_reconciliation(self, id: int, data: dict) -> dict:
        """PUT /bank/reconciliation/{id} — update a bank reconciliation."""
        resp = await self._request("PUT", f"/bank/reconciliation/{id}", json=data)
        return self._extract_value(resp)

    async def get_bank_statements(self, params: dict | None = None) -> list:
        """GET /bank/statement — list bank statements."""
        resp = await self._request("GET", "/bank/statement", params=params)
        return self._extract_values(resp)

    async def import_bank_statement(self, data: dict) -> dict:
        """POST /bank/statement/import — import a bank statement."""
        resp = await self._request("POST", "/bank/statement/import", json=data)
        return self._extract_value(resp)

    async def get_bank_statement_transactions(self, params: dict | None = None) -> list:
        """GET /bank/statement/transaction — list bank statement transactions."""
        resp = await self._request("GET", "/bank/statement/transaction", params=params)
        return self._extract_values(resp)

    async def create_bank_reconciliation_match(self, data: dict) -> dict:
        """POST /bank/reconciliation/match — match bank txns to ledger postings."""
        resp = await self._request("POST", "/bank/reconciliation/match", json=data)
        return self._extract_value(resp)

    async def get_bank_reconciliation_matches(self, params: dict | None = None) -> list:
        """GET /bank/reconciliation/match — list matches."""
        resp = await self._request("GET", "/bank/reconciliation/match", params=params)
        return self._extract_values(resp)

    async def create_bank_reconciliation_payment(self, data: dict) -> dict:
        """POST /bank/reconciliation/paymentType — create payment type for reconciliation."""
        resp = await self._request("POST", "/bank/reconciliation/paymentType", json=data)
        return self._extract_value(resp)

    async def get_bank_reconciliation_payment_types(self, params: dict | None = None) -> list:
        """GET /bank/reconciliation/paymentType — list payment types for reconciliation."""
        resp = await self._request("GET", "/bank/reconciliation/paymentType", params=params)
        return self._extract_values(resp)
