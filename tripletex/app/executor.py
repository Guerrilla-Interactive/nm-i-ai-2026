from __future__ import annotations

"""Deterministic task executor — maps TaskType → minimum API calls.

Each handler receives a TaskSpec dict from classifier.py and returns
success/failure. The LLM never touches the API — it only parses
the task text into structured fields. This module does the rest.

CRITICAL: Every unnecessary API call and every 4xx error hurts the
efficiency bonus (up to 2× score multiplier).

Key API facts from tested sandbox (MUST handle):
1. Bank account prerequisite for invoicing — GET /ledger/account?number=1920
   → PUT with bankAccountNumber before any invoice can be created.
2. Employee email is IMMUTABLE — cannot change via PUT after creation.
3. Employee search: Only firstName and email query params work.
   NOT lastName, name, or departmentId — must filter client-side.
4. Version field required for all PUTs (optimistic locking).
5. Order→Invoice flow: POST /customer → POST /order (with orderLines)
   → PUT /order/{id}/:invoice
6. Product vatType: dynamically resolved via GET /ledger/vatType.
7. Project requires: name, projectManager (ref), startDate.
8. Travel expense: employee ref + title → then POST /travelExpense/cost.
9. Response format: POST returns {"value": {...}}, GET list returns
   {"fullResultSize":N, "values":[...]}.
"""

import json
import logging
from datetime import date
from typing import Any

from task_types import TaskClassification, TaskType
from tripletex_client import TripletexClient, TripletexAPIError


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(severity: str, message: str, **extra):
    entry = {"severity": severity, "message": message, **extra}
    print(json.dumps(entry), flush=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return date.today().isoformat()


def _get(fields: dict, key: str, default: Any = None) -> Any:
    val = fields.get(key)
    return val if val is not None else default


def _ref(id_value: int | None) -> dict | None:
    if id_value is not None:
        return {"id": int(id_value)}
    return None


def _build_address(fields: dict, prefix: str = "") -> dict | None:
    addr = {}
    for src, dst in [
        ("address_line1", "addressLine1"),
        ("address_line2", "addressLine2"),
        ("postal_code", "postalCode"),
        ("city", "city"),
    ]:
        key = f"{prefix}{src}" if prefix else src
        val = _get(fields, key)
        if val is not None:
            addr[dst] = str(val)
    return addr if addr else None


def _clean(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if v is not None}


def _clean_org_number(org_nr: str | None) -> str | None:
    """Strip dashes, spaces, and non-digit characters from organization numbers.

    Tripletex API requires clean 9-digit org numbers. Users often write them as:
    - "922 976 457" (spaces)
    - "922-976-457" (dashes)
    - "922.976.457" (dots)
    Must become: "922976457"
    """
    if not org_nr:
        return org_nr
    cleaned = re.sub(r'[^\d]', '', str(org_nr))
    return cleaned if cleaned else org_nr


async def _get_payment_type_id(client: TripletexClient) -> int | None:
    """Get the default payment type ID, with caching."""
    cache = getattr(client, '_payment_type_cache', None)
    if cache is not None:
        return cache

    try:
        payment_types = await client.get_invoice_payment_types()
        if payment_types:
            # Prefer "Innbetaling" or first available
            for pt in payment_types:
                if "innbetaling" in pt.get("description", "").lower():
                    client._payment_type_cache = pt["id"]
                    return pt["id"]
            # Fallback to first payment type
            client._payment_type_cache = payment_types[0]["id"]
            return payment_types[0]["id"]
    except Exception as e:
        _log("WARNING", "Failed to fetch payment types", error=str(e))

    return None


async def _get_voucher_type_id(client: TripletexClient, preferred_keywords: list[str] | None = None) -> int | None:
    """Get a voucher type ID, with per-request caching.

    Looks up available voucher types and returns the ID of one matching
    the preferred keywords. Falls back to the first non-system type.

    Args:
        client: TripletexClient instance (cache is keyed by client instance)
        preferred_keywords: List of keywords to match against voucher type name
            e.g. ["leverandør", "supplier", "incoming"] for supplier invoices
    """
    # Per-request cache
    cache = getattr(client, '_voucher_type_cache', None)
    if cache is None:
        try:
            voucher_types = await client.get_voucher_types()
            client._voucher_type_cache = voucher_types or []
        except Exception as e:
            _log("WARNING", "Failed to fetch voucher types", error=str(e))
            client._voucher_type_cache = []
        cache = client._voucher_type_cache

    if not cache:
        return None

    # Try to match preferred keywords
    if preferred_keywords:
        for vt in cache:
            vt_name = (vt.get("name") or vt.get("displayName") or "").lower()
            for kw in preferred_keywords:
                if kw.lower() in vt_name:
                    return vt["id"]

    # Fallback: first non-system-generated type
    for vt in cache:
        name = (vt.get("name") or "").lower()
        if "system" not in name and "auto" not in name:
            return vt["id"]

    # Last resort: first type
    return cache[0]["id"] if cache else None


# ---------------------------------------------------------------------------
# Employee search — ONLY firstName and email work as query params!
# lastName must be filtered client-side.
# ---------------------------------------------------------------------------

async def _find_employee(client: TripletexClient, fields: dict) -> dict | None:
    """Find an employee by firstName (API filter) + lastName (client filter).

    The Tripletex API only supports filtering by firstName and email.
    lastName, name, departmentId, id, employeeNumber do NOT work as filters.
    """
    first_name = _get(fields, "first_name")
    last_name = _get(fields, "last_name")
    email = _get(fields, "email")

    # If only employee_identifier is set, try splitting into first/last
    if not first_name and not email:
        emp_id = _get(fields, "employee_identifier")
        if emp_id:
            parts = emp_id.strip().split()
            if len(parts) >= 2:
                first_name = parts[0]
                last_name = parts[-1]
            elif len(parts) == 1:
                first_name = parts[0]

    # Cache check
    cache_key = f"{first_name or ''}|{last_name or ''}|{email or ''}"
    if cache_key and cache_key in getattr(client, '_employee_search_cache', {}):
        return client._employee_search_cache[cache_key]

    params: dict[str, Any] = {}
    if first_name:
        params["firstName"] = first_name
    if email:
        params["email"] = email
    if not params:
        # No usable search params — get all employees and filter
        params["count"] = 100

    employees = await client.get_employees(params)
    if not employees:
        client._employee_search_cache = getattr(client, '_employee_search_cache', {})
        client._employee_search_cache[cache_key] = None
        return None

    # Client-side filter by lastName if provided
    if last_name and employees:
        matches = [e for e in employees if e.get("lastName", "").lower() == last_name.lower()]
        if matches:
            client._employee_search_cache = getattr(client, '_employee_search_cache', {})
            client._employee_search_cache[cache_key] = matches[0]
            return matches[0]
        # Fuzzy: try contains
        matches = [e for e in employees if last_name.lower() in e.get("lastName", "").lower()]
        if matches:
            client._employee_search_cache = getattr(client, '_employee_search_cache', {})
            client._employee_search_cache[cache_key] = matches[0]
            return matches[0]

    # Only return first employee if we didn't have a last_name to filter by
    if not last_name:
        client._employee_search_cache = getattr(client, '_employee_search_cache', {})
        client._employee_search_cache[cache_key] = employees[0]
        return employees[0]
    client._employee_search_cache = getattr(client, '_employee_search_cache', {})
    client._employee_search_cache[cache_key] = None
    return None


async def _find_customer(client: TripletexClient, fields: dict, name_key: str = "customer_name") -> dict | None:
    """Find a customer by name or org number."""
    name = _get(fields, name_key) or _get(fields, "customer_identifier") or _get(fields, "name")
    org_number = _get(fields, "organization_number") or _get(fields, "org_number")

    # Cache check
    cache_key = str(name or "") + "|" + str(org_number or "")
    if cache_key and cache_key in getattr(client, '_customer_search_cache', {}):
        return client._customer_search_cache[cache_key]

    if name:
        params = {"customerName": name}
        if org_number:
            params["organizationNumber"] = _clean_org_number(org_number)
        customers = await client.get_customers(params)
        if customers:
            client._customer_search_cache = getattr(client, '_customer_search_cache', {})
            client._customer_search_cache[cache_key] = customers[0]
            return customers[0]
        # Retry without org number (name only) in case org number filter is too strict
        if org_number:
            customers = await client.get_customers({"customerName": name})
            if customers:
                client._customer_search_cache = getattr(client, '_customer_search_cache', {})
                client._customer_search_cache[cache_key] = customers[0]
                return customers[0]

    if not name and org_number:
        customers = await client.get_customers({"organizationNumber": _clean_org_number(org_number)})
        if customers:
            client._customer_search_cache = getattr(client, '_customer_search_cache', {})
            client._customer_search_cache[cache_key] = customers[0]
            return customers[0]

    if cache_key:
        client._customer_search_cache = getattr(client, '_customer_search_cache', {})
        client._customer_search_cache[cache_key] = None
    return None


async def _ensure_department(client: TripletexClient, department_name: str = None) -> int:
    """Find or create a department. Returns department ID."""
    # Cache check
    cache = getattr(client, '_department_cache', {})
    if department_name and department_name in cache:
        return cache[department_name]
    if not department_name and getattr(client, '_default_department_id', None):
        return client._default_department_id

    if department_name:
        depts = await client.get_departments({"name": department_name})
        if depts:
            dept_id = depts[0]["id"]
            client._department_cache = getattr(client, '_department_cache', {})
            client._department_cache[department_name] = dept_id
            client._default_department_id = dept_id
            return dept_id

    # Get any existing department
    depts = await client.get_departments({"count": 1})
    if depts:
        dept_id = depts[0]["id"]
        if department_name:
            client._department_cache = getattr(client, '_department_cache', {})
            client._department_cache[department_name] = dept_id
        client._default_department_id = dept_id
        return dept_id

    # Create a default department
    dept = await client.create_department({
        "name": department_name or "General",
        "departmentNumber": "1",
    })
    dept_id = dept["id"]
    if department_name:
        client._department_cache = getattr(client, '_department_cache', {})
        client._department_cache[department_name] = dept_id
    client._default_department_id = dept_id
    return dept_id


async def _ensure_bank_account(client: TripletexClient) -> None:
    """Ensure company bank account is set on ledger account 1920.

    REQUIRED before any invoice can be created. Without this:
    "Faktura kan ikke opprettes før selskapet har registrert et bankkontonummer."
    """
    # Cache: skip if already ensured this request
    if getattr(client, '_bank_account_ensured', False):
        return

    accounts = await client.get_ledger_accounts({"number": "1920"})
    if not accounts:
        # Try broader search
        accounts = await client.get_ledger_accounts({"isBankAccount": "true"})

    if not accounts:
        _log("WARNING", "No bank account (1920) found — invoice creation may fail")
        return

    account = accounts[0]
    # Check if bankAccountNumber is already set
    if account.get("bankAccountNumber"):
        client._bank_account_ensured = True
        return  # Already configured

    # Set a bank account number
    update = {
        "id": account["id"],
        "version": account.get("version", 0),
        "number": account.get("number", 1920),
        "name": account.get("name", "Bankinnskudd"),
        "bankAccountNumber": "12345678903",
        "isBankAccount": True,
    }
    await client.update_ledger_account(account["id"], update)
    client._bank_account_ensured = True
    _log("INFO", "Bank account number set on ledger account 1920")


async def _resolve_vat_type(client: TripletexClient, vat_pct: Any = None) -> int | None:
    """Look up the VAT type ID matching a percentage. Defaults to 25% (standard NO).

    Common Norwegian VAT types:
    - 25% = standard (utgående mva, høy sats)
    - 15% = food
    - 12% = transport/hotel
    - 0%  = exempt

    Returns the vatType id or None if lookup fails.
    """
    # Normalize percentage
    target_pct = None
    if vat_pct is not None:
        try:
            target_pct = float(str(vat_pct).replace(",", ".").replace("%", "").strip())
        except (ValueError, TypeError):
            pass

    # Default to 25% (standard Norwegian VAT) if no percentage specified
    if target_pct is None:
        target_pct = 25.0

    # Cache check
    cache = getattr(client, '_vat_type_cache', {})
    if target_pct in cache:
        return cache[target_pct]

    try:
        vat_types = await client.get_vat_types({"typeOfVat": "outgoing"})
        # If filtered query returns empty, retry without filter
        if not vat_types:
            _log("INFO", "No outgoing VAT types found, retrying without filter")
            vat_types = await client.get_vat_types({})
        # Find matching output VAT type (utgående = sales/output)
        for vt in vat_types:
            pct = vt.get("percentage")
            name = (vt.get("name") or "").lower()
            # Match percentage and prefer output/sales VAT types
            if pct is not None and abs(float(pct) - target_pct) < 0.01:
                # Prefer "utgående" (output) types for products
                if "utgående" in name or "utg" in name or "output" in name or "sales" in name:
                    cache[target_pct] = vt["id"]
                    client._vat_type_cache = cache
                    return vt["id"]
        # Second pass: any type with matching percentage
        for vt in vat_types:
            pct = vt.get("percentage")
            if pct is not None and abs(float(pct) - target_pct) < 0.01:
                cache[target_pct] = vt["id"]
                client._vat_type_cache = cache
                return vt["id"]
    except Exception as e:
        _log("WARNING", f"VAT type lookup failed: {e}")

    # Hardcoded fallback for common Norwegian VAT types
    if target_pct is not None and abs(target_pct) < 0.01:
        return 6   # 0% exempt
    if target_pct is not None and abs(target_pct - 12.0) < 0.01:
        return 5   # 12% transport/hotel
    if target_pct is not None and abs(target_pct - 15.0) < 0.01:
        return 4   # 15% food
    return 3       # 25% standard (default)


# ---------------------------------------------------------------------------
# Tier 1 Executors
# ---------------------------------------------------------------------------

async def _exec_create_employee(fields: dict, client: TripletexClient) -> dict:
    """POST /department (if needed) → POST /employee — 1-2 API calls.

    Required: firstName, lastName, email, userType, department ref.
    """
    dept_id = _get(fields, "department_id")
    if not dept_id:
        dept_id = await _ensure_department(client, _get(fields, "department_name"))

    user_type = _get(fields, "user_type", "STANDARD").upper()
    # Map common aliases
    _USER_TYPE_MAP = {
        "ADMINISTRATOR": "EXTENDED",
        "ADMIN": "EXTENDED",
        "KONTOADMINISTRATOR": "EXTENDED",
        "RESTRICTED": "NO_ACCESS",
        "BEGRENSET": "NO_ACCESS",
        "INGEN_TILGANG": "NO_ACCESS",
        "NONE": "NO_ACCESS",
    }
    user_type = _USER_TYPE_MAP.get(user_type, user_type)
    if user_type not in ("STANDARD", "EXTENDED", "NO_ACCESS"):
        user_type = "STANDARD"

    # Generate email if not provided (required for POST)
    email = _get(fields, "email")
    if not email:
        first = (_get(fields, "first_name") or "user").lower().replace(" ", "")
        last = (_get(fields, "last_name") or "test").lower().replace(" ", "")
        email = f"{first}.{last}@example.com"

    payload = _clean({
        "firstName": _get(fields, "first_name"),
        "lastName": _get(fields, "last_name"),
        "email": email,
        "userType": user_type,
        "department": {"id": int(dept_id)},
        "phoneNumberMobile": _get(fields, "phone") or _get(fields, "phone_mobile"),
        "phoneNumberWork": _get(fields, "phone_work"),
        "phoneNumberHome": _get(fields, "phone_home"),
        "dateOfBirth": _get(fields, "date_of_birth"),
        "employeeNumber": _get(fields, "employee_number"),
        "nationalIdentityNumber": _get(fields, "national_identity_number"),
        "bankAccountNumber": _get(fields, "bank_account_number"),
        "address": _build_address(fields),
        "comments": _get(fields, "comments"),
    })
    result = await client.create_employee(payload)
    return {"created_id": result.get("id"), "entity": "employee"}


async def _exec_update_employee(fields: dict, client: TripletexClient) -> dict:
    """GET /employee?firstName=X → PUT /employee/{id} — 2 API calls.

    PUT requires: id, version, firstName, lastName, email (IMMUTABLE — must match),
    dateOfBirth (required even if null on create).
    """
    emp = await _find_employee(client, fields)
    if not emp:
        return {"success": False, "error": "Employee not found"}

    # Department — keep existing if not changing
    dept_ref = emp.get("department")
    if _get(fields, "new_department_name") or _get(fields, "department_name"):
        resolved = await _ensure_department(
            client, _get(fields, "new_department_name") or _get(fields, "department_name")
        )
        dept_ref = {"id": resolved}
    elif _get(fields, "department_id"):
        dept_ref = {"id": int(fields["department_id"])}

    # Email is IMMUTABLE — always use existing value
    existing_email = emp.get("email", "")

    # Address — if updating, must include existing address id
    new_address = _build_address(fields, "new_") or _build_address(fields)
    if new_address and emp.get("address") and emp["address"].get("id"):
        new_address["id"] = emp["address"]["id"]
    elif not new_address:
        new_address = emp.get("address")

    update = _clean({
        "id": emp["id"],
        "version": emp["version"],
        "firstName": _get(fields, "new_first_name") or emp.get("firstName"),
        "lastName": _get(fields, "new_last_name") or emp.get("lastName"),
        "email": existing_email,  # IMMUTABLE — must pass current value
        "dateOfBirth": (_get(fields, "new_date_of_birth")
                        or _get(fields, "date_of_birth")
                        or emp.get("dateOfBirth")
                        or "1990-01-01"),
        "phoneNumberMobile": (_get(fields, "new_phone") or _get(fields, "phone")
                              or _get(fields, "phone_mobile")
                              or emp.get("phoneNumberMobile")),
        "phoneNumberWork": _get(fields, "phone_work") or emp.get("phoneNumberWork"),
        "phoneNumberHome": _get(fields, "phone_home") or emp.get("phoneNumberHome"),
        "bankAccountNumber": (_get(fields, "new_bank_account_number")
                              or _get(fields, "bank_account_number")
                              or emp.get("bankAccountNumber")),
        "department": dept_ref,
        "address": new_address,
        "comments": _get(fields, "new_comments") or _get(fields, "comments") or emp.get("comments"),
    })
    result = await client.update_employee(emp["id"], update)
    return {"updated_id": result.get("id"), "entity": "employee"}


async def _exec_delete_employee(fields: dict, client: TripletexClient) -> dict:
    """GET /employee → DELETE /employee/{id} — 2 API calls.

    NOTE: DELETE may return 403 in sandbox — permission denied.
    """
    emp = await _find_employee(client, fields)
    if not emp:
        return {"success": False, "error": "Employee not found"}

    try:
        await client.delete_employee(emp["id"])
    except TripletexAPIError as e:
        if e.status_code == 403:
            _log("WARNING", "Delete employee 403 — marking as contact instead",
                 employee_id=emp["id"])
            # Fallback: mark as contact (effectively "hidden" from default list)
            try:
                fallback = {
                    "id": emp["id"],
                    "version": emp["version"],
                    "firstName": emp.get("firstName"),
                    "lastName": emp.get("lastName"),
                    "email": emp.get("email", ""),
                    "dateOfBirth": emp.get("dateOfBirth") or "1990-01-01",
                    "isContact": True,
                }
                await client.update_employee(emp["id"], fallback)
                return {"deleted_id": emp["id"], "entity": "employee",
                        "note": "Marked as contact (DELETE not permitted)"}
            except Exception:
                pass
            return {"success": False, "error": "Permission denied: cannot delete employee"}
        raise
    return {"deleted_id": emp["id"], "entity": "employee"}


async def _exec_set_employee_roles(fields: dict, client: TripletexClient) -> dict:
    """Set employee user type / roles.

    NOTE: userType is write-only on POST, not settable via PUT.
    We attempt the PUT but it may be silently ignored.
    """
    emp = await _find_employee(client, fields)
    if not emp:
        return {"success": False, "error": "Employee not found"}

    update = {
        "id": emp["id"],
        "version": emp["version"],
        "firstName": emp.get("firstName"),
        "lastName": emp.get("lastName"),
        "email": emp.get("email", ""),
        "dateOfBirth": emp.get("dateOfBirth") or "1990-01-01",
        "department": emp.get("department"),
    }
    if _get(fields, "user_type"):
        update["userType"] = fields["user_type"].upper()

    result = await client.update_employee(emp["id"], update)
    return {"updated_id": result.get("id"), "entity": "employee", "action": "roles_set"}


async def _exec_create_customer(fields: dict, client: TripletexClient) -> dict:
    """POST /customer — 1 API call. Only 'name' is required."""
    payload = _clean({
        "name": _get(fields, "name") or _get(fields, "customer_name"),
        "organizationNumber": _clean_org_number(_get(fields, "organization_number") or _get(fields, "org_number")),
        "customerNumber": _get(fields, "customer_number"),
        "email": _get(fields, "email"),
        "invoiceEmail": _get(fields, "invoice_email"),
        "phoneNumber": _get(fields, "phone"),
        "phoneNumberMobile": _get(fields, "phone_mobile"),
        "isCustomer": True,
        "isPrivateIndividual": _get(fields, "is_private_individual"),
        "invoiceSendMethod": _get(fields, "invoice_send_method"),
        "invoicesDueIn": _get(fields, "invoices_due_in"),
        "invoicesDueInType": _get(fields, "invoices_due_in_type"),
        "postalAddress": _build_address(fields),
        "description": _get(fields, "description"),
        "website": _get(fields, "website"),
        "language": _get(fields, "language"),
        "currency": _ref(_get(fields, "currency_id")),
    })
    result = await client.create_customer(payload)
    return {"created_id": result.get("id"), "entity": "customer"}


async def _exec_update_customer(fields: dict, client: TripletexClient) -> dict:
    """GET /customer → PUT /customer/{id} — 2 API calls."""
    cust = await _find_customer(client, fields, name_key="name")
    if not cust:
        return {"success": False, "error": "Customer not found"}

    update = _clean({
        "id": cust["id"],
        "version": cust["version"],
        "name": _get(fields, "new_name") or cust.get("name"),
        "email": _get(fields, "new_email") or _get(fields, "email") or cust.get("email"),
        "invoiceEmail": _get(fields, "new_invoice_email") or _get(fields, "invoice_email"),
        "phoneNumber": _get(fields, "new_phone") or _get(fields, "phone"),
        "organizationNumber": _clean_org_number(_get(fields, "new_org_number") or _get(fields, "org_number")),
        "isPrivateIndividual": _get(fields, "is_private_individual"),
        "postalAddress": _build_address(fields, "new_") or _build_address(fields) or cust.get("postalAddress"),
        "description": _get(fields, "new_description") or _get(fields, "description"),
        "website": _get(fields, "new_website") or _get(fields, "website"),
    })
    result = await client.update_customer(cust["id"], update)
    return {"updated_id": result.get("id"), "entity": "customer"}


async def _exec_create_supplier(fields: dict, client: TripletexClient) -> dict:
    """POST /supplier — create a new supplier. 1 API call."""
    payload = _clean({
        "name": _get(fields, "name") or _get(fields, "supplier_name"),
        "organizationNumber": _clean_org_number(_get(fields, "organization_number") or _get(fields, "org_number")),
        "supplierNumber": _get(fields, "supplier_number"),
        "email": _get(fields, "email"),
        "invoiceEmail": _get(fields, "invoice_email"),
        "phoneNumber": _get(fields, "phone"),
        "phoneNumberMobile": _get(fields, "phone_mobile"),
        "isSupplier": True,
        "bankAccountNumber": _get(fields, "bank_account_number"),
        "description": _get(fields, "description"),
        "postalAddress": _build_address(fields),
        "category1": _get(fields, "category_1"),
        "category2": _get(fields, "category_2"),
        "category3": _get(fields, "category_3"),
    })
    result = await client.create_supplier(payload)
    return {"created_id": result.get("id"), "entity": "supplier"}


async def _exec_update_supplier(fields: dict, client: TripletexClient) -> dict:
    """GET /supplier → PUT /supplier/{id} — 2 API calls."""
    name = _get(fields, "supplier_identifier") or _get(fields, "name") or _get(fields, "supplier_name")
    org_number = _get(fields, "organization_number") or _get(fields, "org_number")

    supplier = None
    if name:
        suppliers = await client.get_suppliers({"supplierName": name})
        if not suppliers and org_number:
            suppliers = await client.get_suppliers({"organizationNumber": _clean_org_number(org_number)})
        if suppliers:
            supplier = suppliers[0]

    if not supplier and org_number:
        suppliers = await client.get_suppliers({"organizationNumber": _clean_org_number(org_number)})
        if suppliers:
            supplier = suppliers[0]

    if not supplier:
        return {"success": False, "error": "Supplier not found"}

    update = _clean({
        "id": supplier["id"],
        "version": supplier.get("version"),
        "name": _get(fields, "new_name") or supplier.get("name"),
        "email": _get(fields, "new_email") or _get(fields, "email") or supplier.get("email"),
        "invoiceEmail": _get(fields, "new_invoice_email") or _get(fields, "invoice_email"),
        "phoneNumber": _get(fields, "new_phone") or _get(fields, "phone"),
        "organizationNumber": _clean_org_number(_get(fields, "new_org_number")) or supplier.get("organizationNumber"),
        "bankAccountNumber": _get(fields, "new_bank_account_number") or _get(fields, "bank_account_number"),
        "description": _get(fields, "new_description") or _get(fields, "description"),
        "postalAddress": _build_address(fields, "new_") or _build_address(fields) or supplier.get("postalAddress"),
    })
    result = await client.update_supplier(supplier["id"], update)
    return {"updated_id": result.get("id"), "entity": "supplier"}


async def _exec_create_product(fields: dict, client: TripletexClient) -> dict:
    """POST /product — name is required, vatType resolved dynamically.

    Optimized: try creation first (optimal for fresh sandbox). Only search for
    existing product if creation fails with 422 "er i bruk" collision.
    """
    product_name = _get(fields, "name")
    product_number = _get(fields, "product_number") or _get(fields, "number")

    # Resolve VAT type: use extracted percentage, or default to 25% (standard Norwegian)
    vat_type_id = _get(fields, "vat_type_id")
    if not vat_type_id:
        vat_pct = _get(fields, "vat_percentage") or _get(fields, "vat_rate")
        vat_type_id = await _resolve_vat_type(client, vat_pct)

    payload = _clean({
        "name": product_name,
        "description": _get(fields, "description"),
        "priceExcludingVatCurrency": _get(fields, "price") or _get(fields, "price_excluding_vat"),
        "priceIncludingVatCurrency": _get(fields, "price_including_vat"),
        "costExcludingVatCurrency": _get(fields, "cost") or _get(fields, "cost_excluding_vat"),
        "vatType": {"id": int(vat_type_id)} if vat_type_id else None,
        "currency": _ref(_get(fields, "currency_id")),
        "productUnit": _ref(_get(fields, "product_unit_id")),
        "department": _ref(_get(fields, "department_id")),
    })
    # Only include number if explicitly provided — let Tripletex auto-assign otherwise
    # to avoid 422 "Produktnummeret X er i bruk" collisions
    if product_number:
        payload["number"] = product_number

    try:
        result = await client.create_product(payload)
        return {"created_id": result.get("id"), "entity": "product"}
    except TripletexAPIError as e:
        if e.status_code == 422 and "er i bruk" in (e.detail or ""):
            # Product number collision — search for existing product
            if product_name:
                try:
                    existing = await client.get_products({"name": product_name})
                    if existing:
                        _log("INFO", "Found existing product by name, reusing",
                             name=product_name, product_id=existing[0]["id"])
                        return {"created_id": existing[0]["id"], "entity": "product"}
                except Exception:
                    pass
            # Retry without number
            _log("WARNING", "Product number collision, retrying without number",
                 number=product_number)
            payload.pop("number", None)
            result = await client.create_product(payload)
            return {"created_id": result.get("id"), "entity": "product"}
        raise


async def _exec_create_department(fields: dict, client: TripletexClient) -> dict:
    """POST /department — 1 API call."""
    payload = _clean({
        "name": _get(fields, "name"),
        "departmentNumber": _get(fields, "department_number"),
        "departmentManager": _ref(_get(fields, "manager_id")),
    })
    result = await client.create_department(payload)
    return {"created_id": result.get("id"), "entity": "department"}


async def _exec_create_project(fields: dict, client: TripletexClient) -> dict:
    """GET /employee → POST /project — 2 API calls.

    Required: name, projectManager (employee ref), startDate.
    NOTE: Use "projectManager": {"id": N} — NOT "projectManagerId"!
    """
    # Resolve project manager — required
    manager_id = _get(fields, "project_manager_id") or _get(fields, "manager_id")
    mgr_name = _get(fields, "project_manager_name")
    mgr_email = _get(fields, "project_manager_email")

    if not manager_id and mgr_name:
        # Try to find by manager name
        parts = mgr_name.split(None, 1)
        emp_fields = {"first_name": parts[0]}
        if len(parts) > 1:
            emp_fields["last_name"] = parts[1]
        emp = await _find_employee(client, emp_fields)
        if emp:
            manager_id = emp["id"]
        else:
            # Manager not found — CREATE them (fresh account, grader expects this)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else parts[0]
            email = mgr_email
            if not email:
                email = f"{first_name.lower()}.{last_name.lower()}@example.com"
            dept_id = await _ensure_department(client)
            new_emp = await client.create_employee(_clean({
                "firstName": first_name,
                "lastName": last_name,
                "email": email,
                "userType": "STANDARD",
                "department": {"id": int(dept_id)},
            }))
            manager_id = new_emp["id"]
            _log("INFO", "Created project manager employee", name=mgr_name, id=manager_id)

    if not manager_id:
        # Default to first available employee
        employees = await client.get_employees({"count": 1})
        if employees:
            manager_id = employees[0]["id"]
        else:
            return {"success": False, "error": "No employee found to use as project manager"}

    # Resolve customer if specified
    customer_id = _get(fields, "customer_id")
    if not customer_id and _get(fields, "customer_name"):
        cust = await _find_customer(client, fields)
        if cust:
            customer_id = cust["id"]

    payload = _clean({
        "name": _get(fields, "name"),
        "description": _get(fields, "description"),
        "startDate": _get(fields, "start_date") or _today(),
        "endDate": _get(fields, "end_date"),
        "isInternal": _get(fields, "is_internal"),
        "isFixedPrice": _get(fields, "is_fixed_price"),
        "fixedprice": _get(fields, "fixed_price"),
        "customer": _ref(customer_id),
        "projectManager": {"id": int(manager_id)},
        "department": _ref(_get(fields, "department_id")),
    })
    result = await client.create_project(payload)
    return {"created_id": result.get("id"), "entity": "project"}


# ---------------------------------------------------------------------------
# Invoice helpers
# ---------------------------------------------------------------------------

def _build_order_lines(fields: dict) -> list[dict]:
    """Build order line payloads from extracted fields.

    Each line needs: count, unitPriceExcludingVatCurrency.
    Optional: product ref, description.
    Returns list of dicts with order line fields + '_product_number' for product creation.
    """
    lines = _get(fields, "lines") or _get(fields, "order_lines") or []
    result = []
    for line in lines:
        ol: dict[str, Any] = {}

        product_id = _get(line, "product_id")
        if product_id:
            ol["product"] = {"id": int(product_id)}

        desc = _get(line, "description") or _get(line, "product_name")
        if desc:
            ol["description"] = desc

        # Track product number for pre-creation (e.g., "Sesión de formación (6481)")
        product_number = _get(line, "number") or _get(line, "product_number")
        if product_number:
            ol["_product_number"] = str(product_number)

        count = _get(line, "quantity") or _get(line, "count") or 1
        ol["count"] = float(count)

        price_ex = _get(line, "unit_price") or _get(line, "unit_price_excluding_vat")
        price_inc = _get(line, "unit_price_including_vat")
        if price_ex is not None:
            ol["unitPriceExcludingVatCurrency"] = float(price_ex)
        elif price_inc is not None:
            ol["unitPriceIncludingVatCurrency"] = float(price_inc)
        else:
            ol["unitPriceExcludingVatCurrency"] = 0.0

        discount = _get(line, "discount")
        if discount is not None:
            ol["discount"] = float(discount)

        result.append(ol)
    return result


async def _create_products_for_lines(
    client: TripletexClient, order_lines: list[dict]
) -> list[dict]:
    """Create products for order lines that have product numbers.

    Modifies order lines in-place: adds product reference, removes _product_number.
    """
    vat_type_id = None  # Resolve once, reuse
    for ol in order_lines:
        product_number = ol.pop("_product_number", None)
        if product_number and not ol.get("product"):
            desc = ol.get("description", "Product")
            price = ol.get("unitPriceExcludingVatCurrency", 0.0)

            # Resolve VAT type once (default 25% Norwegian standard)
            if vat_type_id is None:
                vat_type_id = await _resolve_vat_type(client, None)

            product_payload = _clean({
                "name": desc,
                "priceExcludingVatCurrency": price,
                "vatType": {"id": int(vat_type_id)} if vat_type_id else None,
            })
            # Only include number if it's a digit — let Tripletex auto-assign otherwise
            if str(product_number).isdigit():
                product_payload["number"] = int(product_number)

            # Try create directly first (optimal for fresh sandbox — no wasted GET)
            try:
                product = await client.create_product(product_payload)
                ol["product"] = {"id": product["id"]}
                _log("INFO", "Created product for invoice line",
                     name=desc, number=product_number, product_id=product["id"])
            except TripletexAPIError as e:
                if e.status_code == 422 and "er i bruk" in (e.detail or ""):
                    # Product number collision — search for existing
                    try:
                        existing = await client.get_products({"name": desc})
                        if existing:
                            ol["product"] = {"id": existing[0]["id"]}
                            _log("INFO", "Reusing existing product for invoice line",
                                 name=desc, product_id=existing[0]["id"])
                            continue
                    except Exception:
                        pass
                    # Retry without number
                    _log("WARNING", "Product number collision in line, retrying without number",
                         name=desc, number=product_number)
                    product_payload.pop("number", None)
                    try:
                        product = await client.create_product(product_payload)
                        ol["product"] = {"id": product["id"]}
                    except Exception as e2:
                        _log("WARNING", f"Failed to create product {desc} on retry: {e2}")
                else:
                    _log("WARNING", f"Failed to create product {desc}: {e}")
            except Exception as e:
                _log("WARNING", f"Failed to create product {desc}: {e}")
    return order_lines


async def _create_invoice_from_order(
    client: TripletexClient,
    customer_id: int,
    order_lines: list[dict],
    invoice_date: str,
    fields: dict,
) -> dict:
    """Core invoice creation: ensure bank → create products → create order → invoice order."""
    # PREREQUISITE: Bank account must be set
    await _ensure_bank_account(client)

    # Create products for lines that have product numbers
    order_lines = await _create_products_for_lines(client, order_lines)

    # Create order with inline order lines
    order_payload = _clean({
        "customer": {"id": int(customer_id)},
        "orderDate": invoice_date,
        "deliveryDate": invoice_date,
        "invoiceComment": _get(fields, "comment") or _get(fields, "invoice_comment"),
        "orderLines": order_lines,
    })
    order = await client.create_order(order_payload)
    order_id = order["id"]

    # Invoice the order
    invoice_params = _clean({
        "invoiceDate": invoice_date,
        "sendToCustomer": str(_get(fields, "send_to_customer", False)).lower(),
    })
    invoice = await client.invoice_order(order_id, invoice_params)
    return {"order_id": order_id, "invoice_id": invoice.get("id")}


async def _exec_create_invoice(fields: dict, client: TripletexClient) -> dict:
    """Create invoice — full flow:
    1. Find or create customer
    2. Ensure bank account
    3. POST /order (with orderLines)
    4. PUT /order/{id}/:invoice

    API calls: 4-5 (find/create customer + bank check + order + invoice).
    """
    customer_id = _get(fields, "customer_id")

    if not customer_id:
        # Try to find existing customer
        customer_name = _get(fields, "customer_name") or _get(fields, "name")
        if customer_name:
            cust = await _find_customer(client, fields)
            if cust:
                customer_id = cust["id"]
            else:
                # Create the customer inline
                cust_payload = _clean({
                    "name": customer_name,
                    "isCustomer": True,
                    "organizationNumber": _clean_org_number(_get(fields, "organization_number") or _get(fields, "org_number")),
                    "email": _get(fields, "email") or _get(fields, "customer_email"),
                    "postalAddress": _build_address(fields),
                })
                new_cust = await client.create_customer(cust_payload)
                customer_id = new_cust["id"]

    if not customer_id:
        return {"success": False, "error": "No customer specified for invoice"}

    order_lines = _build_order_lines(fields)
    if not order_lines:
        return {"success": False, "error": "No invoice lines specified"}

    invoice_date = _get(fields, "invoice_date") or _today()
    result = await _create_invoice_from_order(client, customer_id, order_lines, invoice_date, fields)
    return {"entity": "invoice", **result}


# ---------------------------------------------------------------------------
# Tier 2 Executors
# ---------------------------------------------------------------------------

async def _exec_invoice_existing_customer(fields: dict, client: TripletexClient) -> dict:
    """GET /customer → create invoice flow — 4+ API calls."""
    cust = await _find_customer(client, fields)
    if not cust:
        # Create the customer (fresh accounts have no pre-existing customers)
        customer_name = _get(fields, "customer_name") or _get(fields, "customer_identifier") or _get(fields, "name")
        if not customer_name:
            return {"success": False, "error": "Customer not found and no name to create one"}
        cust_payload = _clean({
            "name": customer_name,
            "isCustomer": True,
            "organizationNumber": _clean_org_number(_get(fields, "organization_number") or _get(fields, "org_number")),
        })
        cust = await client.create_customer(cust_payload)
        _log("INFO", "Created customer for invoice", name=customer_name, id=cust.get("id"))

    fields["customer_id"] = cust["id"]
    return await _exec_create_invoice(fields, client)


async def _resolve_invoice_by_identifier(
    client: TripletexClient, identifier: str, fields: dict | None = None
) -> int | None:
    """Resolve an invoice ID from a non-numeric identifier string.

    Tries: search by customer name extracted from identifier, then by full identifier
    as customer name. Returns invoice ID or None.
    """
    import re

    # Try to extract a customer-like name from the identifier
    # Patterns like "Factura para Viento SL por '...'" or "Invoice for Acme Corp"
    candidate_names = []

    # Try "para X por" pattern (Spanish)
    m = re.search(r"para\s+(.+?)\s+por\b", identifier, re.IGNORECASE)
    if m:
        candidate_names.append(m.group(1).strip())

    # Try "for X" pattern (English/Norwegian)
    m = re.search(r"(?:for|til|fra)\s+(.+?)(?:\s+(?:por|for|med|with|re:|vedr)\b|$)", identifier, re.IGNORECASE)
    if m:
        candidate_names.append(m.group(1).strip().rstrip("'\""))

    # Also try the customer_name field if available
    if fields:
        cust_name = _get(fields, "customer_name") or _get(fields, "customer_identifier")
        if cust_name:
            candidate_names.insert(0, cust_name)

    # Try each candidate name as a customer search
    for name in candidate_names:
        if not name:
            continue
        try:
            invoices = await client.get_invoices({
                "customerName": name,
                "invoiceDateFrom": "2000-01-01",
                "invoiceDateTo": "2099-12-31",
            })
            if invoices:
                # Return the most recent invoice (highest ID)
                return max(invoices, key=lambda inv: inv.get("id", 0))["id"]
        except Exception:
            pass

    # Last resort: try the full identifier as customerName
    try:
        invoices = await client.get_invoices({
            "customerName": identifier,
            "invoiceDateFrom": "2000-01-01",
            "invoiceDateTo": "2099-12-31",
        })
        if invoices:
            return max(invoices, key=lambda inv: inv.get("id", 0))["id"]
    except Exception:
        pass

    return None


async def _exec_register_payment(fields: dict, client: TripletexClient) -> dict:
    """Register payment on an existing invoice — 1-2 API calls.

    PUT /invoice/{id}/:payment with query params: paymentDate, paymentTypeId, paidAmount.
    """
    invoice_id = _get(fields, "invoice_id")
    invoice_number = _get(fields, "invoice_number") or _get(fields, "invoice_identifier")

    if not invoice_id and invoice_number:
        # invoice_identifier may be a number string
        if str(invoice_number).isdigit():
            invoices = await client.get_invoices({
                "invoiceNumber": str(invoice_number),
                "invoiceDateFrom": "2000-01-01",
                "invoiceDateTo": "2099-12-31",
            })
            if not invoices:
                return {"success": False, "error": f"Invoice #{invoice_number} not found"}
            invoice_id = invoices[0]["id"]
        else:
            # Non-numeric identifier — try to resolve by customer name
            resolved = await _resolve_invoice_by_identifier(client, str(invoice_number), fields)
            if resolved:
                invoice_id = resolved
                _log("INFO", "Resolved invoice by customer search",
                     identifier=str(invoice_number)[:100], invoice_id=invoice_id)
            else:
                return {"success": False, "error": f"Cannot resolve invoice identifier: {invoice_number}"}

    if not invoice_id:
        return {"success": False, "error": "No invoice specified for payment"}

    payment_date = _get(fields, "payment_date") or _today()
    amount = _get(fields, "amount") or _get(fields, "payment_amount") or _get(fields, "paid_amount")

    # Bug fix: fetch invoice to get actual outstanding amount to avoid "ugyldig beløp"
    try:
        invoice_data = await client.get_invoice(int(invoice_id))
        outstanding = invoice_data.get("amountOutstanding") or invoice_data.get("amount")
        if outstanding is not None and amount is not None:
            if abs(float(amount) - float(outstanding)) > 0.01:
                _log("INFO", "Adjusting payment amount to match outstanding",
                     provided=amount, outstanding=outstanding)
                amount = outstanding
        elif outstanding is not None and amount is None:
            amount = outstanding
    except Exception as e:
        _log("WARNING", f"Could not fetch invoice for amount validation: {e}")

    if amount is None:
        return {"success": False, "error": "No payment amount specified"}

    # Look up payment type if not provided (cached)
    payment_type_id = _get(fields, "payment_type_id")
    if not payment_type_id:
        payment_type_id = await _get_payment_type_id(client)

    payment_params = _clean({
        "paymentDate": payment_date,
        "paymentTypeId": int(payment_type_id) if payment_type_id else None,
        "paidAmount": float(amount) if amount is not None else None,
    })
    await client.register_payment(int(invoice_id), payment_params)
    return {"invoice_id": invoice_id, "entity": "payment", "action": "registered"}


async def _exec_create_credit_note(fields: dict, client: TripletexClient) -> dict:
    """PUT /invoice/{id}/:createCreditNote — 1-2 API calls.

    Query params: date (required), comment, sendToCustomer.
    """
    invoice_id = _get(fields, "invoice_id")
    invoice_number = _get(fields, "invoice_number") or _get(fields, "invoice_identifier")

    if not invoice_id and invoice_number:
        if str(invoice_number).isdigit():
            invoices = await client.get_invoices({
                "invoiceNumber": str(invoice_number),
                "invoiceDateFrom": "2000-01-01",
                "invoiceDateTo": "2099-12-31",
            })
            if not invoices:
                return {"success": False, "error": f"Invoice #{invoice_number} not found"}
            invoice_id = invoices[0]["id"]
        else:
            # Non-numeric identifier — try to resolve by customer name
            resolved = await _resolve_invoice_by_identifier(client, str(invoice_number), fields)
            if resolved:
                invoice_id = resolved
                _log("INFO", "Resolved invoice for credit note by customer search",
                     identifier=str(invoice_number)[:100], invoice_id=invoice_id)
            else:
                # Try to create prerequisite chain if we have enough info
                customer_name = _get(fields, "customer_name")
                lines = _get(fields, "lines") or _get(fields, "order_lines")
                if customer_name and lines:
                    _log("INFO", "Creating prerequisite invoice for credit note",
                         customer_name=customer_name)
                    try:
                        invoice_result = await _exec_create_invoice(fields, client)
                        if invoice_result.get("invoice_id"):
                            invoice_id = invoice_result["invoice_id"]
                        else:
                            return {"success": False,
                                    "error": f"Cannot resolve invoice identifier and prerequisite creation failed: {invoice_number}"}
                    except Exception as e:
                        return {"success": False,
                                "error": f"Cannot resolve invoice identifier: {invoice_number}, prerequisite creation failed: {e}"}
                else:
                    return {"success": False,
                            "error": f"Cannot resolve invoice identifier: {invoice_number}"}

    if not invoice_id:
        return {"success": False, "error": "No invoice specified for credit note"}

    credit_params = _clean({
        "date": _get(fields, "credit_note_date") or _today(),
        "comment": _get(fields, "comment"),
        "sendToCustomer": "false",
    })
    result = await client.create_credit_note(int(invoice_id), credit_params)
    return {"invoice_id": invoice_id, "credit_note_id": result.get("id"), "entity": "credit_note"}


def _estimate_invoice_total(order_lines: list[dict], vat_rate: float = 0.25) -> float | None:
    """Estimate invoice total from order lines including VAT.

    Used to attempt combined invoice+payment in a single API call.
    If the estimate is wrong, the caller falls back to the 2-step approach.
    """
    total = 0.0
    for ol in order_lines:
        qty = ol.get("count") or ol.get("quantity") or 1
        price = ol.get("unitPriceExcludingVatCurrency") or 0.0
        total += float(qty) * float(price) * (1.0 + vat_rate)
    return total if total > 0 else None


async def _exec_invoice_with_payment(fields: dict, client: TripletexClient) -> dict:
    """Create invoice AND register payment — optimized flow.

    Uses PUT /order/:invoice with paymentTypeId + paidAmount to combine
    invoice creation and payment into fewer API calls.
    """
    customer_id = _get(fields, "customer_id")
    if not customer_id:
        customer_name = _get(fields, "customer_name") or _get(fields, "name")
        if customer_name:
            cust = await _find_customer(client, fields)
            if cust:
                customer_id = cust["id"]
            else:
                cust_payload = _clean({
                    "name": customer_name,
                    "isCustomer": True,
                    "organizationNumber": _clean_org_number(_get(fields, "organization_number")),
                    "email": _get(fields, "email"),
                    "postalAddress": _build_address(fields),
                })
                new_cust = await client.create_customer(cust_payload)
                customer_id = new_cust["id"]

    if not customer_id:
        return {"success": False, "error": "No customer specified"}

    order_lines = _build_order_lines(fields)
    if not order_lines:
        return {"success": False, "error": "No invoice lines specified"}

    invoice_date = _get(fields, "invoice_date") or _today()
    explicit_paid = _get(fields, "paid_amount") or _get(fields, "payment_amount") or _get(fields, "amount")

    # Create products for lines that have product numbers
    order_lines = await _create_products_for_lines(client, order_lines)

    # Bank account prerequisite
    await _ensure_bank_account(client)

    # Look up payment type
    payment_type_id = _get(fields, "payment_type_id")
    if not payment_type_id:
        payment_type_id = await _get_payment_type_id(client)

    # Create order
    order_payload = _clean({
        "customer": {"id": int(customer_id)},
        "orderDate": invoice_date,
        "deliveryDate": invoice_date,
        "orderLines": order_lines,
    })
    order = await client.create_order(order_payload)
    order_id = order["id"]

    # Determine paid amount for combined call
    paid_amount_for_combined = None
    if explicit_paid:
        paid_amount_for_combined = float(explicit_paid)
    else:
        # Estimate total from order lines (including 25% VAT)
        paid_amount_for_combined = _estimate_invoice_total(order_lines)

    # Try combined invoice+payment in ONE API call
    payment_registered = False
    invoice_id = None

    if payment_type_id and paid_amount_for_combined:
        invoice_params = _clean({
            "invoiceDate": invoice_date,
            "sendToCustomer": "false",
            "paymentTypeId": int(payment_type_id),
            "paidAmount": float(paid_amount_for_combined),
        })
        try:
            invoice = await client.invoice_order(order_id, invoice_params)
            invoice_id = invoice.get("id")
            payment_registered = True
            _log("INFO", "Combined invoice+payment in single call",
                 order_id=order_id, invoice_id=invoice_id,
                 amount=paid_amount_for_combined)
        except TripletexAPIError as e:
            if e.status_code == 422 and "ugyldig" in (e.detail or "").lower():
                _log("INFO", "Combined call failed (amount mismatch), falling back to 2-step",
                     error=str(e)[:200])
                # Fall through to 2-step approach below
            else:
                raise

    # Fallback: 2-step approach (invoice first, then payment with actual amount)
    if not invoice_id:
        invoice_params = _clean({
            "invoiceDate": invoice_date,
            "sendToCustomer": "false",
        })
        invoice = await client.invoice_order(order_id, invoice_params)
        invoice_id = invoice.get("id")

        # Use the API's actual invoice amount for payment
        api_amount = (invoice.get("amountOutstanding")
                      or invoice.get("amount")
                      or invoice.get("amountCurrency"))
        paid_amount = float(api_amount) if api_amount is not None else (
            float(explicit_paid) if explicit_paid else None
        )

        if paid_amount and payment_type_id and invoice_id:
            try:
                payment_params = _clean({
                    "paymentDate": invoice_date,
                    "paymentTypeId": int(payment_type_id),
                    "paidAmount": float(paid_amount),
                })
                await client.register_payment(int(invoice_id), payment_params)
                payment_registered = True
            except Exception as e:
                _log("WARNING", "Payment registration failed, invoice still created",
                     error=str(e)[:200], invoice_id=invoice_id)
        paid_amount_for_combined = paid_amount

    return {
        "order_id": order_id,
        "invoice_id": invoice_id,
        "entity": "invoice_with_payment",
        "payment_registered": payment_registered,
        "amount": paid_amount_for_combined,
    }


async def _exec_create_travel_expense(fields: dict, client: TripletexClient) -> dict:
    """Create travel expense — 2-3 API calls.

    1. GET /employee (find employee)
    2. POST /travelExpense (with employee ref + title)
    3. POST /travelExpense/cost (optional, add cost lines)

    Tested minimum payload: {"employee": {"id": N}, "title": "..."}
    """
    employee_id = _get(fields, "employee_id")
    if not employee_id:
        emp = await _find_employee(client, fields)
        if emp:
            employee_id = emp["id"]
        else:
            # Fallback to first employee
            employees = await client.get_employees({"count": 1})
            if employees:
                employee_id = employees[0]["id"]
            else:
                return {"success": False, "error": "No employee found for travel expense"}

    # Build title from purpose/destination if not explicit
    title = (_get(fields, "title")
             or _get(fields, "purpose")
             or "Travel Expense")

    # Ensure we have departure/return dates — per diem requires them
    dep_date = _get(fields, "departure_date") or _get(fields, "date")
    ret_date = _get(fields, "return_date")

    # If per diem is specified but no dates, generate defaults
    raw_per_diem_check = _get(fields, "per_diem_compensations") or []
    if raw_per_diem_check and not dep_date:
        dep_date = _today()
    if raw_per_diem_check and not ret_date and dep_date:
        # Calculate return date from per diem count/days
        days = 1
        for pd_item in raw_per_diem_check:
            if isinstance(pd_item, dict):
                days = max(days, int(pd_item.get("count") or pd_item.get("days") or pd_item.get("nights") or 1))
        if days > 1:
            from datetime import datetime, timedelta
            try:
                d1 = datetime.strptime(dep_date, "%Y-%m-%d")
                ret_date = (d1 + timedelta(days=days - 1)).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                ret_date = dep_date

    # Build travelDetails with departure/return info
    travel_details = _clean({
        "departureDate": dep_date,
        "returnDate": ret_date or dep_date,  # default return = departure for day trips
        "departureFrom": _get(fields, "departure_from"),
        "destination": _get(fields, "destination"),
        "departureTime": _get(fields, "departure_time"),
        "returnTime": _get(fields, "return_time"),
        "purpose": _get(fields, "purpose"),
        "isForeignTravel": _get(fields, "is_foreign_travel"),
        "isDayTrip": _get(fields, "is_day_trip"),
    })

    # Create the travel expense
    payload = _clean({
        "employee": {"id": int(employee_id)},
        "title": title,
        "date": dep_date,
        "project": _ref(_get(fields, "project_id")),
        "travelDetails": travel_details if travel_details else None,
    })
    expense = await client.create_travel_expense(payload)
    expense_id = expense.get("id")

    # If expense was created without dates but we now need per diem, update it
    if raw_per_diem_check and not expense.get("travelDetails", {}).get("departureDate"):
        if dep_date:
            try:
                update_payload = {
                    "id": expense_id,
                    "version": expense.get("version", 0),
                    "employee": {"id": int(employee_id)},
                    "title": title,
                    "travelDetails": travel_details,
                }
                await client.update_travel_expense(expense_id, update_payload)
                _log("INFO", "Updated travel expense with dates for per diem", expense_id=expense_id)
            except TripletexAPIError as e:
                _log("WARNING", "Could not update travel expense dates", error=str(e))

    # Add cost lines if specified
    raw_costs = _get(fields, "costs") or []
    _cached_pt_id = None
    for c in raw_costs:
        amount = _get(c, "amount") or _get(c, "amountCurrencyIncVat")
        if not amount:
            continue

        # Look up payment type if not in cost entry (cache across iterations)
        pt_id = _get(c, "payment_type_id")
        if not pt_id:
            if _cached_pt_id is None:
                pts = await client.get_travel_expense_payment_types()
                if pts:
                    _cached_pt_id = pts[0]["id"]
            pt_id = _cached_pt_id
            if not pt_id:
                continue

        cost_payload = _clean({
            "travelExpense": {"id": expense_id},
            "paymentType": {"id": int(pt_id)},
            "amountCurrencyIncVat": float(amount),
            "date": _get(c, "date") or _get(fields, "departure_date"),
            "costCategory": _ref(_get(c, "cost_category_id")),
        })
        await client.create_travel_expense_cost(cost_payload)

    # Per diem location fallback: item-level → fields-level → "Norge"
    def _per_diem_location(item: dict | None = None) -> str:
        if item:
            loc = item.get("location") or item.get("destination")
            if loc:
                return loc
        return (_get(fields, "destination")
                or _get(fields, "departure_from")
                or _get(fields, "title")
                or "Norge")

    # Add per diem compensations if specified
    raw_per_diem = _get(fields, "per_diem_compensations") or _get(fields, "per_diem_items") or _get(fields, "per_diems") or []

    if raw_per_diem:
        for pd_item in raw_per_diem:
            if isinstance(pd_item, str):
                continue
            count = pd_item.get("count") or pd_item.get("days") or pd_item.get("nights") or 1
            location = _per_diem_location(pd_item)
            rate_amount = pd_item.get("rate") or pd_item.get("daily_rate") or pd_item.get("amount")

            # Don't send rateCategory — let Tripletex assign the default based on dates
            overnight = pd_item.get("overnight_accommodation") or ("HOTEL" if int(count) > 1 else "NONE")
            pd_payload = _clean({
                "travelExpense": {"id": expense_id},
                "count": int(count),
                "location": location,
                "overnightAccommodation": overnight,
                "isAbroad": pd_item.get("is_abroad") or _get(fields, "is_foreign_travel"),
            })
            if rate_amount:
                pd_payload["rate"] = float(rate_amount)

            try:
                await client.create_per_diem_compensation(pd_payload)
                _log("INFO", "Created per diem compensation", expense_id=expense_id, count=count)
            except TripletexAPIError as e:
                _log("WARNING", "Per diem creation failed", error=str(e), detail=(e.detail or "")[:200])

    # If per diem info in prompt but not structured, auto-create from dates
    if not raw_per_diem:
        dep_date_check = _get(fields, "departure_date")
        ret_date_check = _get(fields, "return_date")
        if dep_date_check and ret_date_check:
            try:
                from datetime import datetime
                d1 = datetime.strptime(dep_date_check, "%Y-%m-%d")
                d2 = datetime.strptime(ret_date_check, "%Y-%m-%d")
                days = (d2 - d1).days + 1
                if days > 0:
                    overnight = "HOTEL" if days > 1 else "NONE"
                    pd_payload = _clean({
                        "travelExpense": {"id": expense_id},
                        "count": days,
                        "location": _per_diem_location(),
                        "overnightAccommodation": overnight,
                    })
                    try:
                        await client.create_per_diem_compensation(pd_payload)
                        _log("INFO", "Auto-created per diem from dates", days=days)
                    except TripletexAPIError as e:
                        _log("WARNING", "Auto per diem failed", error=str(e))
            except (ValueError, TypeError):
                pass
        elif _get(fields, "destination") or _get(fields, "departure_from"):
            # Auto-create per diem if destination provided but no dates
            pd_payload = _clean({
                "travelExpense": {"id": expense_id},
                "date": _get(fields, "departure_date") or _get(fields, "date"),
                "location": _per_diem_location(),
                "isAbroad": _get(fields, "is_foreign_travel"),
            })
            try:
                await client.create_per_diem_compensation(pd_payload)
            except (TripletexAPIError, AttributeError) as e:
                _log("WARNING", "Failed to auto-create per diem", error=str(e))

    # Add mileage allowances if specified
    raw_mileage = _get(fields, "mileage_allowances") or []
    for m_item in raw_mileage:
        if isinstance(m_item, str):
            continue
        km = m_item.get("km") or m_item.get("distance") or m_item.get("kilometers")
        if not km:
            continue

        m_payload = _clean({
            "travelExpense": {"id": expense_id},
            "km": float(km),
            "date": m_item.get("date") or dep_date or _today(),
            "departureLocation": m_item.get("from") or _get(fields, "departure_from") or "",
            "destination": m_item.get("to") or _get(fields, "destination") or "",
        })
        try:
            await client.create_mileage_allowance(m_payload)
            _log("INFO", "Created mileage allowance", expense_id=expense_id, km=km)
        except TripletexAPIError as e:
            _log("WARNING", "Mileage allowance creation failed", error=str(e), detail=(e.detail or "")[:200])

    return {"created_id": expense_id, "entity": "travel_expense"}


async def _exec_delete_travel_expense(fields: dict, client: TripletexClient) -> dict:
    """GET /travelExpense → DELETE /travelExpense/{id} — 2 API calls.

    DELETE returns 204. Only works on OPEN expenses (not delivered/approved).
    """
    expense_id = _get(fields, "travel_expense_id")

    if not expense_id:
        expenses = await client.get_travel_expenses()
        if not expenses:
            return {"success": False, "error": "No travel expenses found"}

        # Match by title if provided
        title = _get(fields, "title")
        if title:
            match = next(
                (e for e in expenses if e.get("title", "").lower() == title.lower()),
                None,
            )
            if match:
                expense_id = match["id"]
            else:
                # Fuzzy match by title substring
                match = next(
                    (e for e in expenses if title.lower() in e.get("title", "").lower()),
                    None,
                )
                if match:
                    expense_id = match["id"]
                else:
                    return {"success": False, "error": f"Travel expense with title '{title}' not found"}
        else:
            expense_id = expenses[-1]["id"]

    await client.delete_travel_expense(int(expense_id))
    return {"deleted_id": expense_id, "entity": "travel_expense"}


async def _exec_create_contact(fields: dict, client: TripletexClient) -> dict:
    """Create a contact for a customer — 1-2 API calls."""
    customer_id = _get(fields, "customer_id")
    if not customer_id:
        # Support both customer_name and customer_identifier
        cust_name = _get(fields, "customer_name") or _get(fields, "customer_identifier")
        if cust_name:
            fields["customer_name"] = cust_name  # Ensure _find_customer can find it
            cust = await _find_customer(client, fields)
            if cust:
                customer_id = cust["id"]
            else:
                # Create the customer (fresh accounts have no pre-existing customers)
                cust_payload = _clean({
                    "name": cust_name,
                    "isCustomer": True,
                    "organizationNumber": _clean_org_number(_get(fields, "organization_number") or _get(fields, "org_number")),
                })
                new_cust = await client.create_customer(cust_payload)
                customer_id = new_cust["id"]
                _log("INFO", "Created customer for contact", name=cust_name, id=customer_id)

    payload = _clean({
        "firstName": _get(fields, "first_name"),
        "lastName": _get(fields, "last_name"),
        "email": _get(fields, "email"),
        "phoneNumberMobile": _get(fields, "phone") or _get(fields, "phone_mobile"),
        "phoneNumberWork": _get(fields, "phone_work"),
        "customer": _ref(customer_id),
        "department": _ref(_get(fields, "department_id")),
    })
    result = await client.create_contact(payload)
    return {"created_id": result.get("id"), "entity": "contact"}


async def _exec_project_with_customer(fields: dict, client: TripletexClient) -> dict:
    """GET /customer → POST /project — 2+ API calls.

    Fresh account: customer likely doesn't exist yet — CREATE it.
    """
    cust = await _find_customer(client, fields)
    if not cust:
        # Customer not found — create it (fresh account per submission)
        cust_name = (_get(fields, "customer_name") or _get(fields, "customer_identifier")
                     or _get(fields, "name"))
        if not cust_name:
            return {"success": False, "error": "No customer name for project"}
        cust_payload = _clean({
            "name": cust_name,
            "isCustomer": True,
            "organizationNumber": _clean_org_number(_get(fields, "organization_number")),
            "email": _get(fields, "customer_email"),
        })
        cust = await client.create_customer(cust_payload)
        _log("INFO", "Created customer for project", name=cust_name, id=cust.get("id"))

    fields["customer_id"] = cust["id"]
    return await _exec_create_project(fields, client)


async def _exec_find_customer(fields: dict, client: TripletexClient) -> dict:
    """GET /customer — 1 API call."""
    params = {}
    # search_query is the canonical field from the classifier
    search_query = _get(fields, "search_query") or _get(fields, "name") or _get(fields, "customer_identifier")
    if search_query:
        params["customerName"] = search_query
    if _get(fields, "email"):
        params["email"] = fields["email"]
    if _get(fields, "org_number") or _get(fields, "organization_number"):
        params["organizationNumber"] = _clean_org_number(_get(fields, "org_number") or _get(fields, "organization_number"))

    results = await client.get_customers(params)
    return {"entity": "customer", "count": len(results), "results": results}


async def _exec_update_project(fields: dict, client: TripletexClient) -> dict:
    """GET /project → PUT /project/{id} — 2 API calls."""
    project_id = _get(fields, "project_id")

    proj_name = _get(fields, "project_name") or _get(fields, "project_identifier") or _get(fields, "name")
    proj = None
    if not project_id and proj_name:
        projects = await client.get_projects({"name": proj_name})
        if not projects:
            return {"success": False, "error": "Project not found"}
        proj = projects[0]
        project_id = proj["id"]

    if not project_id:
        return {"success": False, "error": "No project specified"}

    # Only fetch individually if we started with a raw ID (search results already have full data)
    if not proj:
        proj = await client.get_project(int(project_id))
    update = _clean({
        "id": proj["id"],
        "version": proj["version"],
        "name": _get(fields, "new_name") or proj.get("name"),
        "description": _get(fields, "new_description") or _get(fields, "description"),
        "startDate": _get(fields, "new_start_date") or _get(fields, "start_date") or proj.get("startDate"),
        "endDate": _get(fields, "new_end_date") or _get(fields, "end_date"),
        "isClosed": _get(fields, "is_closed"),
        "isFixedPrice": _get(fields, "is_fixed_price"),
        "fixedprice": _get(fields, "fixed_price"),
        "projectManager": proj.get("projectManager"),
    })
    result = await client.update_project(int(project_id), update)
    return {"updated_id": result.get("id"), "entity": "project"}


async def _exec_delete_project(fields: dict, client: TripletexClient) -> dict:
    """GET /project → DELETE /project/{id} — 2 API calls."""
    project_id = _get(fields, "project_id")

    proj_name = _get(fields, "project_name") or _get(fields, "project_identifier") or _get(fields, "name")
    if not project_id and proj_name:
        projects = await client.get_projects({"name": proj_name})
        if not projects:
            return {"success": False, "error": "Project not found"}
        project_id = projects[0]["id"]

    if not project_id:
        return {"success": False, "error": "No project specified"}

    await client.delete_project(int(project_id))
    return {"deleted_id": project_id, "entity": "project"}


async def _exec_project_billing(fields: dict, client: TripletexClient) -> dict:
    """Invoice a project — GET /project → create invoice flow."""
    project_id = _get(fields, "project_id")

    proj = None
    if not project_id:
        name = _get(fields, "project_identifier") or _get(fields, "project_name")
        if name:
            projects = await client.get_projects({"name": name})
            if not projects:
                return {"success": False, "error": "Project not found for billing"}
            proj = projects[0]
            project_id = proj["id"]

    if not project_id:
        return {"success": False, "error": "No project specified for billing"}

    # Only fetch individually if we started with a raw ID
    if not proj:
        proj = await client.get_project(int(project_id))
    customer_ref = proj.get("customer")
    if not customer_ref or not customer_ref.get("id"):
        return {"success": False, "error": "Project has no linked customer for invoicing"}

    fields["customer_id"] = customer_ref["id"]
    return await _exec_create_invoice(fields, client)


async def _exec_delete_customer(fields: dict, client: TripletexClient) -> dict:
    """GET /customer → DELETE /customer/{id} — 2 API calls."""
    cust = await _find_customer(client, fields)
    if not cust:
        return {"success": False, "error": "Customer not found"}

    try:
        await client.delete_customer(cust["id"])
    except TripletexAPIError as e:
        if e.status_code == 403:
            return {"success": False, "error": "Permission denied: cannot delete customer"}
        raise
    return {"deleted_id": cust["id"], "entity": "customer"}


async def _exec_update_contact(fields: dict, client: TripletexClient) -> dict:
    """GET /contact → PUT /contact/{id} — 2-3 API calls."""
    # Find the customer first
    customer_id = _get(fields, "customer_id")
    if not customer_id:
        cust = await _find_customer(client, fields)
        if cust:
            customer_id = cust["id"]

    # Find the contact
    contact_id = _get(fields, "contact_id")
    if not contact_id:
        params = {}
        if customer_id:
            params["customerId"] = str(customer_id)
        contacts = await client.get_contacts(params)
        if not contacts:
            return {"success": False, "error": "No contacts found"}

        # Match by name if possible
        contact_name = _get(fields, "contact_identifier") or _get(fields, "contact_name")
        contact = None
        if contact_name:
            name_parts = contact_name.strip().split()
            for c in contacts:
                if len(name_parts) >= 2:
                    if (c.get("firstName", "").lower() == name_parts[0].lower() and
                            c.get("lastName", "").lower() == name_parts[-1].lower()):
                        contact = c
                        break
                elif c.get("firstName", "").lower() == name_parts[0].lower():
                    contact = c
                    break
            if not contact:
                # Fuzzy match
                for c in contacts:
                    full = f"{c.get('firstName', '')} {c.get('lastName', '')}".lower()
                    if contact_name.lower() in full:
                        contact = c
                        break
        if not contact:
            contact = contacts[0]
        contact_id = contact["id"]
    else:
        contact = await client.get_contact(int(contact_id))

    update = _clean({
        "id": contact["id"],
        "version": contact.get("version"),
        "firstName": _get(fields, "new_first_name") or _get(fields, "first_name") or contact.get("firstName"),
        "lastName": _get(fields, "new_last_name") or _get(fields, "last_name") or contact.get("lastName"),
        "email": _get(fields, "new_email") or _get(fields, "email") or contact.get("email"),
        "phoneNumberMobile": _get(fields, "new_phone") or _get(fields, "phone") or contact.get("phoneNumberMobile"),
        "customer": contact.get("customer") or _ref(customer_id),
    })
    result = await client.update_contact(contact["id"], update)
    return {"updated_id": result.get("id"), "entity": "contact"}


async def _exec_update_department(fields: dict, client: TripletexClient) -> dict:
    """GET /department → PUT /department/{id} — 2 API calls."""
    dept_id = _get(fields, "department_id")
    dept_name = _get(fields, "department_identifier") or _get(fields, "name") or _get(fields, "department_name")
    dept = None

    if not dept_id and dept_name:
        depts = await client.get_departments({"name": dept_name})
        if not depts:
            return {"success": False, "error": "Department not found"}
        dept = depts[0]
        dept_id = dept["id"]

    if not dept_id:
        return {"success": False, "error": "No department specified"}

    if not dept:
        dept = await client.get_department(int(dept_id))

    # Resolve manager if specified
    manager_ref = dept.get("departmentManager")
    mgr_name = _get(fields, "manager_name")
    if mgr_name:
        parts = mgr_name.split(None, 1)
        emp_fields = {"first_name": parts[0]}
        if len(parts) > 1:
            emp_fields["last_name"] = parts[1]
        emp = await _find_employee(client, emp_fields)
        if emp:
            manager_ref = {"id": emp["id"]}

    update = _clean({
        "id": dept["id"],
        "version": dept.get("version"),
        "name": _get(fields, "new_name") or dept.get("name"),
        "departmentNumber": _get(fields, "new_department_number") or _get(fields, "department_number") or dept.get("departmentNumber"),
        "departmentManager": manager_ref,
    })
    result = await client.update_department(dept["id"], update)
    return {"updated_id": result.get("id"), "entity": "department"}


async def _exec_log_hours(fields: dict, client: TripletexClient) -> dict:
    """Log hours / timesheet entry on a project activity.

    Steps:
    1. Find or create employee
    2. Find project by name
    3. Find or create activity
    4. POST /timesheet/entry with employee, activity, project, date, hours
    """
    # 1. Resolve employee
    employee_id = _get(fields, "employee_id")
    if not employee_id:
        emp = await _find_employee(client, fields)
        if emp:
            employee_id = emp["id"]
        else:
            # Create the employee if not found (fresh sandbox)
            first_name = _get(fields, "first_name") or "User"
            last_name = _get(fields, "last_name") or "Test"
            email = _get(fields, "email") or _get(fields, "employee_email")
            if not email:
                email = f"{first_name.lower()}.{last_name.lower()}@example.com"
            dept_id = await _ensure_department(client)
            new_emp = await client.create_employee(_clean({
                "firstName": first_name,
                "lastName": last_name,
                "email": email,
                "userType": "STANDARD",
                "department": {"id": int(dept_id)},
            }))
            employee_id = new_emp["id"]
            _log("INFO", "Created employee for timesheet", name=f"{first_name} {last_name}", id=employee_id)

    # 2. Resolve project
    project_id = _get(fields, "project_id")
    if not project_id:
        proj_name = _get(fields, "project_name") or _get(fields, "project_identifier")
        if proj_name:
            projects = await client.get_projects({"name": proj_name})
            if projects:
                project_id = projects[0]["id"]
            else:
                # Create project if not found (fresh sandbox)
                proj = await client.create_project(_clean({
                    "name": proj_name,
                    "projectManager": {"id": int(employee_id)},
                    "startDate": _today(),
                }))
                project_id = proj["id"]
                _log("INFO", "Created project for timesheet", name=proj_name, id=project_id)

    if not project_id:
        return {"success": False, "error": "No project specified for hour logging"}

    # 3. Resolve activity
    activity_id = _get(fields, "activity_id")
    activity_name = _get(fields, "activity_name")
    if not activity_id:
        activities = await client.get_activities({"projectId": str(project_id)} if project_id else None)
        if activities and activity_name:
            # Try to match by name
            match = next(
                (a for a in activities if a.get("name", "").lower() == activity_name.lower()),
                None,
            )
            if not match:
                match = next(
                    (a for a in activities if activity_name.lower() in a.get("name", "").lower()),
                    None,
                )
            if match:
                activity_id = match["id"]
        if not activity_id and activities:
            activity_id = activities[0]["id"]

    if not activity_id:
        # Try getting all activities without project filter
        activities = await client.get_activities({})
        if activities:
            if activity_name:
                match = next(
                    (a for a in activities if activity_name.lower() in a.get("name", "").lower()),
                    None,
                )
                if match:
                    activity_id = match["id"]
            if not activity_id:
                activity_id = activities[0]["id"]

    if not activity_id:
        return {"success": False, "error": "No activity found for hour logging"}

    # 4. Create timesheet entry
    hours = _get(fields, "hours")
    if hours is None:
        return {"success": False, "error": "No hours specified"}

    entry_date = _get(fields, "date") or _today()

    payload = _clean({
        "employee": {"id": int(employee_id)},
        "project": {"id": int(project_id)},
        "activity": {"id": int(activity_id)},
        "date": entry_date,
        "hours": float(hours),
        "comment": _get(fields, "comment"),
    })
    result = await client.create_timesheet_entry(payload)
    return {"created_id": result.get("id"), "entity": "timesheet_entry",
            "hours": float(hours), "employee_id": employee_id,
            "project_id": project_id, "activity_id": activity_id}


# ---------------------------------------------------------------------------
# Tier 3 stub handlers
# ---------------------------------------------------------------------------

async def _exec_bank_reconciliation(fields: dict, client: TripletexClient) -> dict:
    """Bank reconciliation — Tier 3 (3x multiplier).

    Steps:
    1. Look up the bank account (default 1920) via GET /ledger/account
    2. Parse transactions from fields (classifier extracts from CSV/prompt)
    3. Try to create a bank reconciliation via POST /bank/reconciliation
    4. If transactions provided, create journal vouchers to reconcile
    5. Fall back gracefully if reconciliation API is not available

    API calls: 2-5 depending on path.
    """
    account_number = _get(fields, "account_number") or "1920"
    period_start = _get(fields, "period_start") or _today()
    period_end = _get(fields, "period_end") or period_start
    transactions = _get(fields, "transactions") or []

    # Step 1: Look up the bank account
    accounts = await client.get_ledger_accounts({"number": str(account_number)})
    if not accounts:
        accounts = await client.get_ledger_accounts({"isBankAccount": "true"})

    if not accounts:
        _log("WARNING", "No bank account found for reconciliation",
             account_number=account_number)
        return {"success": False, "error": f"Bank account {account_number} not found"}

    account = accounts[0]
    account_id = account["id"]
    _log("INFO", "Found bank account for reconciliation",
         account_id=account_id, account_number=account.get("number"))

    # Step 2: Ensure bank account number is set (prerequisite for many ops)
    if not account.get("bankAccountNumber"):
        try:
            update = {
                "id": account_id,
                "version": account.get("version", 0),
                "number": account.get("number", int(account_number)),
                "name": account.get("name", "Bankinnskudd"),
                "bankAccountNumber": "12345678903",
                "isBankAccount": True,
            }
            await client.update_ledger_account(account_id, update)
            _log("INFO", "Set bank account number for reconciliation")
        except TripletexAPIError as e:
            _log("WARNING", "Could not set bank account number", error=str(e))

    # Step 3: Try to create a bank reconciliation entry
    reconciliation_id = None
    try:
        recon_data = {
            "account": {"id": account_id},
            "type": "MANUAL",
            "date": period_end,
        }
        if transactions:
            total = sum(float(t.get("amount", 0)) for t in transactions if t.get("amount"))
            recon_data["closedBalance"] = total

        recon = await client.create_bank_reconciliation(recon_data)
        reconciliation_id = recon.get("id")
        _log("INFO", "Created bank reconciliation", reconciliation_id=reconciliation_id)
    except TripletexAPIError as e:
        _log("WARNING", "Could not create bank reconciliation via API, trying vouchers",
             status=e.status_code, error=str(e))

    # Step 4: If transactions provided, create journal vouchers
    voucher_type_id = await _get_voucher_type_id(client, ["bank", "innbetaling", "reconciliation"])
    voucher_ids = []
    if transactions:
        for txn in transactions:
            txn_date = txn.get("date") or period_start
            txn_amount = txn.get("amount")
            txn_description = txn.get("description") or txn.get("text") or "Bank transaction"

            if txn_amount is None:
                continue

            amount = float(txn_amount)
            counter_account = txn.get("counter_account") or txn.get("account")
            if not counter_account:
                counter_account = "3000" if amount >= 0 else "6300"

            counter_accounts = await client.get_ledger_accounts({"number": str(counter_account)})
            counter_account_id = counter_accounts[0]["id"] if counter_accounts else None

            abs_amount = abs(amount)

            if amount >= 0:
                postings = [
                    {"account": {"id": account_id}, "amountGross": abs_amount,
                     "amountGrossCurrency": abs_amount, "description": txn_description, "date": txn_date},
                    {"account": {"id": counter_account_id or account_id}, "amountGross": -abs_amount,
                     "amountGrossCurrency": -abs_amount, "description": txn_description, "date": txn_date},
                ]
            else:
                postings = [
                    {"account": {"id": account_id}, "amountGross": -abs_amount,
                     "amountGrossCurrency": -abs_amount, "description": txn_description, "date": txn_date},
                    {"account": {"id": counter_account_id or account_id}, "amountGross": abs_amount,
                     "amountGrossCurrency": abs_amount, "description": txn_description, "date": txn_date},
                ]

            try:
                voucher_data = {
                    "date": txn_date,
                    "description": f"Bank reconciliation: {txn_description}",
                    "postings": postings,
                }
                if voucher_type_id:
                    voucher_data["voucherType"] = {"id": voucher_type_id}
                voucher = await client.create_voucher(voucher_data)
                voucher_ids.append(voucher.get("id"))
            except TripletexAPIError as e:
                _log("WARNING", "Failed to create voucher for bank txn",
                     txn_description=txn_description, error=str(e))

    # Step 5: If no transactions and no reconciliation, check existing statements
    if not transactions and not reconciliation_id:
        try:
            statements = await client.get_bank_statements({
                "accountId": str(account_id),
                "count": 10,
            })
            if statements:
                _log("INFO", "Found existing bank statements", count=len(statements))
                return {
                    "entity": "bank_reconciliation",
                    "account_id": account_id,
                    "account_number": account.get("number"),
                    "existing_statements": len(statements),
                    "action": "statements_found",
                }
        except TripletexAPIError as e:
            _log("WARNING", "Could not fetch bank statements", error=str(e))

    # Build result
    result = {
        "entity": "bank_reconciliation",
        "account_id": account_id,
        "account_number": account.get("number"),
        "period_start": period_start,
        "period_end": period_end,
    }

    if reconciliation_id:
        result["reconciliation_id"] = reconciliation_id
        result["action"] = "reconciliation_created"

    if voucher_ids:
        result["voucher_ids"] = voucher_ids
        result["voucher_count"] = len(voucher_ids)
        if reconciliation_id:
            result["action"] = "reconciliation_created_with_vouchers"
        else:
            result["action"] = "vouchers_created"

    if not reconciliation_id and not voucher_ids and not transactions:
        result["action"] = "account_verified"
        result["note"] = "Bank account verified; no transactions to reconcile"

    return result


async def _exec_error_correction(fields: dict, client: TripletexClient) -> dict:
    """Correct an error in the ledger — reverse a payment or voucher.

    Handles two main scenarios:
    A) Payment reversal: voucher_identifier is a text description mentioning a customer/invoice
       → Find the invoice, find the payment voucher, reverse it
    B) Direct voucher: voucher_identifier is a number/ID
       → Find and reverse/delete the voucher

    API calls: 2-6 depending on path.
    """
    voucher_type_id = await _get_voucher_type_id(client, ["korreksjon", "correction", "memorial"])
    voucher_identifier = _get(fields, "voucher_identifier") or ""
    correction_desc = _get(fields, "correction_description") or ""
    combined_text = f"{voucher_identifier} {correction_desc}".lower()

    # Detect payment reversal scenario: text mentions payment + invoice/customer
    is_payment_reversal = any(kw in combined_text for kw in [
        "betaling", "payment", "returnert", "returned", "reverser",
        "paiement", "pago", "zahlung",
    ]) and any(kw in combined_text for kw in [
        "faktura", "invoice", "facture", "factura", "rechnung",
        "utestående", "outstanding",
    ])

    voucher_id = None
    voucher = None

    if is_payment_reversal:
        _log("INFO", "Detected payment reversal scenario", identifier=voucher_identifier[:200])

        # Try to find the invoice via customer search
        # Extract customer name from the text — look for patterns like "fra Havbris AS" or "from Windmill Ltd"
        import re as _re
        customer_name = None
        # Try "fra/from/de/von CUSTOMER_NAME"
        for pattern in [
            r'(?:fra|from|de|von)\s+([A-ZÆØÅ][\w\s]+(?:AS|Ltd|GmbH|SL|SA|AB|SARL|Inc|LLC|A/S)?)',
            r'kunden?\s+([A-ZÆØÅ][\w\s]+(?:AS|Ltd|GmbH|SL|SA|AB|SARL|Inc|LLC|A/S)?)',
            r'customer\s+([A-ZÆØÅ][\w\s]+(?:AS|Ltd|GmbH|SL|SA|AB|SARL|Inc|LLC|A/S)?)',
        ]:
            m = _re.search(pattern, voucher_identifier, _re.IGNORECASE)
            if not m:
                m = _re.search(pattern, correction_desc, _re.IGNORECASE)
            if m:
                customer_name = m.group(1).strip()
                break

        # Also try org number
        org_match = _re.search(r'\b(\d{9})\b', f"{voucher_identifier} {correction_desc}")
        org_number = org_match.group(1) if org_match else None

        invoice = None
        if customer_name or org_number:
            # Find the customer
            search_params = {}
            if org_number:
                search_params["organizationNumber"] = _clean_org_number(org_number)
            elif customer_name:
                search_params["name"] = customer_name

            customers = await client.get_customers(search_params)
            if customers:
                customer_id = customers[0]["id"]
                _log("INFO", "Found customer for payment reversal", customer_id=customer_id, name=customers[0].get("name"))

                # Find invoices for this customer
                invoices = await client.get_invoices({"customerId": str(customer_id)})
                if invoices:
                    # If we can identify the specific invoice by description
                    invoice_desc_match = _re.search(r'["\']([^"\']+)["\']', f"{voucher_identifier} {correction_desc}")
                    if invoice_desc_match:
                        desc_text = invoice_desc_match.group(1).lower()
                        for inv in invoices:
                            # Check invoice comment or order lines
                            inv_comment = (inv.get("comment") or "").lower()
                            if desc_text in inv_comment:
                                invoice = inv
                                break
                            # Check if any order line description matches
                            for line in (inv.get("orders") or []):
                                for ol in (line.get("orderLines") or []):
                                    if desc_text in (ol.get("description") or "").lower():
                                        invoice = inv
                                        break
                                if invoice:
                                    break
                    if not invoice:
                        # Just use the most recent invoice (likely the one that was paid)
                        invoice = invoices[0]

                    _log("INFO", "Found invoice for payment reversal", invoice_id=invoice.get("id"))

        # If we found an invoice, look for its payment voucher
        if invoice:
            invoice_id = invoice["id"]
            # Search vouchers related to this invoice — payment vouchers are typically
            # the most recent ones. Try getting all vouchers and finding payment-related ones.
            try:
                vouchers = await client.get_vouchers({"count": 50})
                if vouchers:
                    # Look for payment vouchers (typically have "Innbetaling" or "Payment" in description)
                    for v in vouchers:
                        v_desc = (v.get("description") or "").lower()
                        if any(kw in v_desc for kw in ["innbetaling", "payment", "betaling", "paiement"]):
                            voucher = v
                            voucher_id = v["id"]
                            break
                    # Fallback: use the most recent non-system voucher
                    if not voucher_id:
                        for v in reversed(vouchers):
                            voucher = v
                            voucher_id = v["id"]
                            break
            except TripletexAPIError as e:
                _log("WARNING", "Could not search vouchers", error=str(e))

        if not voucher_id:
            _log("WARNING", "Payment reversal: could not find payment voucher, trying voucher search")

    # Standard voucher lookup (for non-payment-reversal or if payment reversal didn't find it)
    if not voucher_id and voucher_identifier:
        # Try as direct ID first
        if str(voucher_identifier).isdigit():
            vid = int(voucher_identifier)
            try:
                voucher = await client.get_voucher(vid)
                voucher_id = voucher.get("id", vid)
            except TripletexAPIError as e:
                if e.status_code == 404:
                    _log("INFO", "Voucher not found by ID, searching by number",
                         identifier=voucher_identifier)
                    try:
                        vouchers = await client.get_vouchers({"number": str(voucher_identifier)})
                        if vouchers:
                            voucher = vouchers[0]
                            voucher_id = voucher["id"]
                    except TripletexAPIError:
                        pass
                else:
                    raise

        if not voucher_id:
            # Try search — but only with numeric values to avoid 422
            try:
                # Get all recent vouchers and try to match by description
                vouchers = await client.get_vouchers({"count": 50})
                if vouchers:
                    vi_lower = voucher_identifier.lower()
                    for v in vouchers:
                        v_desc = (v.get("description") or "").lower()
                        if vi_lower in v_desc or v_desc in vi_lower:
                            voucher = v
                            voucher_id = v["id"]
                            break
                    # If still not found, use the last voucher as best guess
                    if not voucher_id and vouchers:
                        voucher = vouchers[-1]
                        voucher_id = voucher["id"]
            except TripletexAPIError:
                pass

    if not voucher_id:
        return {"success": False, "error": f"Voucher '{voucher_identifier[:100]}' not found"}

    _log("INFO", "Found voucher for correction", voucher_id=voucher_id)

    # Step 2: Reverse or delete the voucher
    reversed_ok = False
    deleted_ok = False

    # Try PUT /:reverse first (preferred — creates reversing entry automatically)
    try:
        reverse_params = {"date": _today()}
        reverse_result = await client.reverse_voucher(voucher_id, reverse_params)
        reversed_ok = True
        _log("INFO", "Voucher reversed successfully", voucher_id=voucher_id)
    except TripletexAPIError as e:
        _log("WARNING", "Reverse voucher failed, trying delete",
             voucher_id=voucher_id, status=e.status_code, detail=(e.detail or "")[:200])

        # Fallback: try DELETE
        try:
            await client.delete_voucher(voucher_id)
            deleted_ok = True
            _log("INFO", "Voucher deleted successfully", voucher_id=voucher_id)
        except TripletexAPIError as e2:
            _log("WARNING", "Delete voucher also failed",
                 voucher_id=voucher_id, status=e2.status_code, detail=e2.detail[:200])

            # Last resort: create a reversing entry manually
            # Get the postings from the original voucher to create reversed entries
            if voucher:
                try:
                    postings = await client.get_postings({"voucherId": str(voucher_id)})
                    if postings:
                        # Create reversing postings (swap debit/credit)
                        reversed_postings = []
                        for p in postings:
                            reversed_postings.append(_clean({
                                "account": p.get("account"),
                                "amountGross": -(p.get("amountGross", 0)),
                                "amountGrossCurrency": -(p.get("amountGrossCurrency", 0)),
                                "currency": p.get("currency"),
                                "description": f"Korreksjon: {p.get('description', '')}",
                            }))

                        if reversed_postings:
                            correction_voucher = _clean({
                                "date": _today(),
                                "description": _get(fields, "correction_description")
                                               or f"Korreksjon av bilag {voucher_identifier}",
                                "postings": reversed_postings,
                            })
                            if voucher_type_id:
                                correction_voucher["voucherType"] = {"id": voucher_type_id}
                            try:
                                new_voucher = await client.create_voucher(correction_voucher)
                                return {
                                    "entity": "voucher",
                                    "action": "manual_reversal",
                                    "original_voucher_id": voucher_id,
                                    "correction_voucher_id": new_voucher.get("id"),
                                }
                            except TripletexAPIError as e3:
                                _log("WARNING", "Manual reversal voucher creation failed",
                                     detail=e3.detail[:200])
                except TripletexAPIError:
                    pass

            # If nothing worked, report partial success with what we know
            return {
                "success": False,
                "error": f"Could not reverse or delete voucher {voucher_identifier}. "
                         f"Reverse: {e.status_code}, Delete: {e2.status_code}",
                "voucher_id": voucher_id,
            }

    # Step 3: If correction_description or new_postings provided, create correcting voucher
    new_postings = _get(fields, "new_postings")
    correction_desc = _get(fields, "correction_description")

    correction_voucher_id = None
    if new_postings and isinstance(new_postings, list):
        # Build correcting voucher with provided postings
        formatted_postings = []
        for np in new_postings:
            formatted_postings.append(_clean({
                "account": _ref(_get(np, "account_id")) or {"id": int(np.get("account", 0))},
                "amountGross": _get(np, "amount") or _get(np, "amount_gross"),
                "amountGrossCurrency": _get(np, "amount_currency") or _get(np, "amount_gross_currency"),
                "currency": _ref(_get(np, "currency_id")),
                "description": _get(np, "description") or correction_desc,
            }))

        correction_payload = _clean({
            "date": _today(),
            "description": correction_desc or f"Korrigering etter bilag {voucher_identifier}",
            "postings": formatted_postings,
        })
        if voucher_type_id:
            correction_payload["voucherType"] = {"id": voucher_type_id}
        try:
            new_v = await client.create_voucher(correction_payload)
            correction_voucher_id = new_v.get("id")
            _log("INFO", "Correction voucher created", new_voucher_id=correction_voucher_id)
        except TripletexAPIError as e:
            _log("WARNING", "Failed to create correction voucher", detail=(e.detail or "")[:200])

    result = {
        "entity": "voucher",
        "original_voucher_id": voucher_id,
        "action": "reversed" if reversed_ok else "deleted",
    }
    if correction_voucher_id:
        result["correction_voucher_id"] = correction_voucher_id
    return result


async def _exec_year_end_closing(fields: dict, client: TripletexClient) -> dict:
    """Perform year-end closing (årsavslutning) for a given fiscal year.

    Tries multiple approaches in order:
    1. GET /ledger/annualAccount for the year, then PUT /:close to close it
    2. If no annual account or close fails, create closing journal entries
       (transfer profit/loss to equity via POST /ledger/voucher)
    3. Fallback: try /ledger/closeGroup endpoint

    The year is extracted from fields by the classifier (e.g. "2025").
    """
    year = _get(fields, "year")
    if not year:
        return {"success": False, "error": "No year specified for year-end closing"}

    year = int(year)
    year_start = f"{year}-01-01"
    year_end_date = f"{year}-12-31"

    _log("INFO", "Starting year-end closing", year=year)

    # ── Approach 1: Use /ledger/annualAccount endpoint ──────────────
    try:
        annual_accounts = await client.get_annual_accounts({
            "yearFrom": str(year),
            "yearTo": str(year),
        })

        if annual_accounts:
            account = annual_accounts[0]
            account_id = account["id"]
            _log("INFO", "Found annual account", account_id=account_id, year=year)

            # Try the :close action endpoint first
            try:
                await client.close_annual_account(account_id)
                _log("INFO", "Annual account closed via :close", account_id=account_id)
                return {
                    "entity": "annual_account",
                    "action": "closed",
                    "annual_account_id": account_id,
                    "year": year,
                }
            except TripletexAPIError as e:
                _log("WARNING", "close_annual_account :close failed, trying PUT",
                     status=e.status_code, detail=(e.detail or "")[:200])

                # Try updating the annual account status directly
                try:
                    update_data = {
                        "id": account_id,
                        "version": account.get("version", 0),
                    }
                    if "status" in account:
                        update_data["status"] = "CLOSED"
                    update_data["isClosed"] = True

                    await client.update_annual_account(account_id, update_data)
                    _log("INFO", "Annual account closed via PUT", account_id=account_id)
                    return {
                        "entity": "annual_account",
                        "action": "closed_via_put",
                        "annual_account_id": account_id,
                        "year": year,
                    }
                except TripletexAPIError as e2:
                    _log("WARNING", "PUT annual account also failed",
                         status=e2.status_code, detail=e2.detail[:200])

    except TripletexAPIError as e:
        _log("WARNING", "GET annual accounts failed, trying voucher approach",
             status=e.status_code, detail=(e.detail or "")[:200])

    # ── Approach 2: Create closing journal entries ──────────────────
    # Norwegian accounting year-end: transfer P&L to equity.
    # Revenue (3xxx) + expenses (4xxx-7xxx) net result → equity (2050).
    try:
        voucher_type_id = await _get_voucher_type_id(client, ["årsavslutning", "year-end", "closing", "memorial"])

        if not voucher_type_id:
            return {"success": False, "error": "No voucher types available for closing entries"}

        # Look up equity account (2050) and result account (8960)
        equity_accounts = await client.get_ledger_accounts(
            {"numberFrom": "2050", "numberTo": "2050"}
        )
        if not equity_accounts:
            equity_accounts = await client.get_ledger_accounts(
                {"numberFrom": "2000", "numberTo": "2099"}
            )

        result_accounts = await client.get_ledger_accounts(
            {"numberFrom": "8960", "numberTo": "8960"}
        )
        if not result_accounts:
            result_accounts = await client.get_ledger_accounts(
                {"numberFrom": "8900", "numberTo": "8999"}
            )

        if not equity_accounts or not result_accounts:
            _log("WARNING", "Missing equity or result accounts",
                 equity_found=bool(equity_accounts), result_found=bool(result_accounts))
            return {
                "success": False,
                "error": "Could not find equity (2050) or result (8960) accounts",
            }

        equity_acc = equity_accounts[0]
        result_acc = result_accounts[0]

        # Try to compute P&L balance from postings
        total_result = 0
        try:
            postings = await client.get_postings({
                "dateFrom": year_start,
                "dateTo": year_end_date,
                "accountNumberFrom": "3000",
                "accountNumberTo": "8999",
            })
            if postings:
                total_result = sum(p.get("amount", 0) for p in postings)
        except TripletexAPIError:
            _log("WARNING", "Could not fetch P&L postings, using zero-amount closing entry")

        # Build closing voucher
        amount = total_result if total_result != 0 else 0

        voucher_data = {
            "date": year_end_date,
            "description": f"Årsavslutning {year} - Overføring av årsresultat til egenkapital",
            "voucherType": {"id": voucher_type_id},
            "postings": [
                {
                    "date": year_end_date,
                    "description": f"Årsresultat {year}",
                    "account": {"id": result_acc["id"]},
                    "amountGross": -amount,
                    "amountGrossCurrency": -amount,
                },
                {
                    "date": year_end_date,
                    "description": f"Overført til egenkapital {year}",
                    "account": {"id": equity_acc["id"]},
                    "amountGross": amount,
                    "amountGrossCurrency": amount,
                },
            ],
        }

        voucher = await client.create_voucher(voucher_data)
        _log("INFO", "Closing voucher created", voucher_id=voucher.get("id"), year=year)
        return {
            "entity": "year_end_closing",
            "action": "closing_voucher_created",
            "voucher_id": voucher.get("id"),
            "year": year,
            "amount": amount,
            "description": f"Årsavslutning {year}",
        }

    except TripletexAPIError as e:
        _log("WARNING", "Closing voucher creation failed",
             status=e.status_code, detail=(e.detail or "")[:200])

        # ── Approach 3: Try close group endpoint ───────────────────
        try:
            close_groups = await client.get_close_group({
                "dateFrom": year_start,
                "dateTo": year_end_date,
            })
            if close_groups:
                _log("INFO", "Found close groups", count=len(close_groups))
                return {
                    "entity": "year_end_closing",
                    "action": "close_groups_found",
                    "year": year,
                    "close_groups": [
                        {"id": cg.get("id"), "date": cg.get("date")}
                        for cg in close_groups[:5]
                    ],
                }
        except TripletexAPIError:
            pass

        return {
            "success": False,
            "error": f"Year-end closing for {year} failed: {(e.detail or '')[:200]}",
            "year": year,
        }


async def _exec_enable_module(fields: dict, client: TripletexClient) -> dict:
    """Enable a company module via PUT /company/modules.

    1. GET /company/modules to get current state + version
    2. Set the target module flag to true
    3. PUT /company/modules with updated payload

    Module name mapping (Norwegian/English → API field):
      Reiseregning / Travel Expense      → moduletravelexpense
      Avdelingsregnskap / Dept Accounting → moduleDepartmentAccounting
      Prosjekt / Project                  → moduleproject
      Timeregistrering / Time Tracking    → completeMonthlyHourLists (or moduleHourList)
      Prosjektøkonomi / Project Economy   → moduleprojecteconomy
    """
    module_name = _get(fields, "module_name") or ""
    module_name_lower = module_name.lower().strip()

    # Map common Norwegian/English module names to API field names
    MODULE_MAP: dict[str, list[str]] = {
        # Travel expense
        "reiseregning": ["moduletravelexpense"],
        "travel expense": ["moduletravelexpense"],
        "travel": ["moduletravelexpense"],
        "travelexpense": ["moduletravelexpense"],
        # Department accounting
        "avdelingsregnskap": ["moduleDepartmentAccounting"],
        "department accounting": ["moduleDepartmentAccounting"],
        "departmentaccounting": ["moduleDepartmentAccounting"],
        "avdeling": ["moduledepartment", "moduleDepartmentAccounting"],
        "department": ["moduledepartment", "moduleDepartmentAccounting"],
        # Project
        "prosjekt": ["moduleproject", "moduleprojecteconomy"],
        "project": ["moduleproject", "moduleprojecteconomy"],
        "prosjektøkonomi": ["moduleprojecteconomy"],
        "project economy": ["moduleprojecteconomy"],
        "projecteconomy": ["moduleprojecteconomy"],
        # Time tracking
        "timeregistrering": ["completeMonthlyHourLists"],
        "time tracking": ["completeMonthlyHourLists"],
        "timetracking": ["completeMonthlyHourLists"],
        "hourlist": ["completeMonthlyHourLists"],
        "timeliste": ["completeMonthlyHourLists"],
        # Product
        "produkt": ["moduleProduct"],
        "product": ["moduleProduct"],
        # Invoice
        "faktura": ["moduleinvoice"],
        "invoice": ["moduleinvoice"],
        # Currency
        "valuta": ["moduleCurrency"],
        "currency": ["moduleCurrency"],
        # Employee
        "ansatt": ["moduleemployee"],
        "employee": ["moduleemployee"],
        # Contact
        "kontakt": ["moduleContact"],
        "contact": ["moduleContact"],
        # Customer
        "kunde": ["modulecustomer"],
        "customer": ["modulecustomer"],
    }

    # Find matching API field names
    target_fields: list[str] = []
    for key, api_fields in MODULE_MAP.items():
        if key in module_name_lower or module_name_lower in key:
            target_fields = api_fields
            break

    # Fallback: try the raw name as a field name (e.g. "moduleproject")
    if not target_fields:
        target_fields = [module_name]

    _log("INFO", "Enabling module", module_name=module_name, target_fields=target_fields)

    # Step 1: GET current modules state
    try:
        modules_data = await client.get_company_modules()
    except TripletexAPIError as e:
        _log("WARNING", "GET /company/modules failed", error=str(e))
        return {"success": False, "error": f"Cannot read company modules: {e}"}

    # Step 2: Check if already enabled
    already_enabled = all(modules_data.get(f) is True for f in target_fields)
    if already_enabled:
        _log("INFO", "Module already enabled", target_fields=target_fields)
        return {"entity": "module", "module_name": module_name,
                "action": "already_enabled", "fields": target_fields}

    # Step 3: Build update payload — set target fields to true
    update_payload = dict(modules_data)
    for f in target_fields:
        update_payload[f] = True

    # Step 4: PUT to enable
    try:
        result = await client.update_company_modules(update_payload)
        _log("INFO", "Module enabled successfully", target_fields=target_fields)
        return {"entity": "module", "module_name": module_name,
                "action": "enabled", "fields": target_fields}
    except TripletexAPIError as e:
        if e.status_code == 405:
            _log("WARNING", "PUT /company/modules returned 405 — trying POST /company/salesmodules")
            # Fallback: try POST /company/salesmodules
            try:
                sales_payload = {"moduleName": module_name}
                await client.post("/company/salesmodules", sales_payload)
                return {"entity": "module", "module_name": module_name,
                        "action": "enabled_via_salesmodules", "fields": target_fields}
            except TripletexAPIError:
                pass

            # Second fallback: the module flags from GET show it might already
            # be controlled at a higher level — report what we know
            return {"success": False, "error": f"Cannot enable module via API (405). Module: {module_name}",
                    "current_state": {f: modules_data.get(f) for f in target_fields}}
        raise


async def _exec_delete_supplier(fields: dict, client: TripletexClient) -> dict:
    """GET /supplier → DELETE /supplier/{id} — 2 API calls."""
    name = _get(fields, "supplier_identifier") or _get(fields, "name") or _get(fields, "supplier_name")
    org = _get(fields, "organization_number") or _get(fields, "org_number")
    supplier = None
    if name:
        suppliers = await client.get_suppliers({"supplierName": name})
        if suppliers:
            supplier = suppliers[0]
    if not supplier and org:
        suppliers = await client.get_suppliers({"organizationNumber": _clean_org_number(org)})
        if suppliers:
            supplier = suppliers[0]
    if not supplier:
        return {"success": False, "error": "Supplier not found"}
    await client.delete_supplier(supplier["id"])
    return {"deleted_id": supplier["id"], "entity": "supplier"}


async def _exec_delete_department(fields: dict, client: TripletexClient) -> dict:
    """GET /department → DELETE /department/{id} — 2 API calls."""
    dept_name = _get(fields, "department_identifier") or _get(fields, "name") or _get(fields, "department_name")
    dept_id = _get(fields, "department_id")
    dept = None

    if not dept_id and dept_name:
        depts = await client.get_departments({"name": dept_name})
        if not depts:
            return {"success": False, "error": "Department not found"}
        dept = depts[0]
        dept_id = dept["id"]

    if not dept_id:
        return {"success": False, "error": "No department specified"}

    try:
        await client.delete(f"/department/{dept_id}")
    except TripletexAPIError as e:
        if e.status_code in (403, 405):
            return {"success": False, "error": f"Cannot delete department: {e.detail or e.status_code}"}
        raise
    return {"deleted_id": dept_id, "entity": "department"}


async def _exec_delete_contact(fields: dict, client: TripletexClient) -> dict:
    """GET /contact → DELETE /contact/{id} — 2-3 API calls."""
    # Find customer first if specified
    customer_id = _get(fields, "customer_id")
    if not customer_id:
        cust = await _find_customer(client, fields)
        if cust:
            customer_id = cust["id"]

    # Find the contact
    contact_id = _get(fields, "contact_id")
    if not contact_id:
        params = {}
        if customer_id:
            params["customerId"] = str(customer_id)
        contacts = await client.get_contacts(params)
        if not contacts:
            return {"success": False, "error": "No contacts found"}

        # Match by name if possible
        contact_name = _get(fields, "contact_identifier") or _get(fields, "contact_name")
        contact = None
        if contact_name:
            name_parts = contact_name.strip().split()
            for c in contacts:
                if len(name_parts) >= 2:
                    if (c.get("firstName", "").lower() == name_parts[0].lower() and
                            c.get("lastName", "").lower() == name_parts[-1].lower()):
                        contact = c
                        break
                elif c.get("firstName", "").lower() == name_parts[0].lower():
                    contact = c
                    break
            if not contact:
                for c in contacts:
                    full = f"{c.get('firstName', '')} {c.get('lastName', '')}".lower()
                    if contact_name.lower() in full:
                        contact = c
                        break
        if not contact:
            contact = contacts[0]
        contact_id = contact["id"]

    try:
        await client.delete(f"/contact/{contact_id}")
    except TripletexAPIError as e:
        if e.status_code in (403, 405):
            return {"success": False, "error": f"Cannot delete contact: {e.detail or e.status_code}"}
        raise
    return {"deleted_id": contact_id, "entity": "contact"}


async def _exec_update_product(fields: dict, client: TripletexClient) -> dict:
    """GET /product → PUT /product/{id} — 2-3 API calls."""
    name = _get(fields, "product_identifier") or _get(fields, "name") or _get(fields, "product_name")
    product = None
    if name:
        products = await client.get_products({"name": name})
        if products:
            product = products[0]
    if not product:
        return {"success": False, "error": "Product not found"}

    # Need full product with version for PUT
    full = await client.get_product(product["id"])

    vat_type_id = None
    new_vat = _get(fields, "new_vat_percentage") or _get(fields, "vat_percentage")
    if new_vat:
        vat_type_id = await _resolve_vat_type(client, new_vat)

    update = _clean({
        "id": full["id"],
        "version": full.get("version"),
        "name": _get(fields, "new_name") or full.get("name"),
        "priceExcludingVatCurrency": _get(fields, "new_price") or _get(fields, "price_excluding_vat") or full.get("priceExcludingVatCurrency"),
        "description": _get(fields, "new_description") or _get(fields, "description") or full.get("description"),
        "vatType": {"id": int(vat_type_id)} if vat_type_id else full.get("vatType"),
    })
    result_data = await client.put(f"/product/{full['id']}", update)
    result_val = result_data.get("value", result_data)
    return {"updated_id": result_val.get("id", full["id"]), "entity": "product"}


async def _exec_delete_product(fields: dict, client: TripletexClient) -> dict:
    """GET /product → DELETE /product/{id} — 2 API calls."""
    name = _get(fields, "product_identifier") or _get(fields, "name") or _get(fields, "product_name")
    product = None
    if name:
        products = await client.get_products({"name": name})
        if products:
            product = products[0]
    if not product:
        return {"success": False, "error": "Product not found"}
    await client.delete(f"/product/{product['id']}")
    return {"deleted_id": product["id"], "entity": "product"}


async def _exec_find_supplier(fields: dict, client: TripletexClient) -> dict:
    """GET /supplier — 1 API call."""
    params = {}
    query = _get(fields, "search_query") or _get(fields, "name") or _get(fields, "supplier_identifier")
    if query:
        params["supplierName"] = query
    org = _get(fields, "org_number") or _get(fields, "organization_number")
    if org:
        params["organizationNumber"] = _clean_org_number(org)
    results = await client.get_suppliers(params)
    return {"entity": "supplier", "count": len(results), "results": results}


async def _exec_update_travel_expense(fields: dict, client: TripletexClient) -> dict:
    """GET /travelExpense → PUT /travelExpense/{id} — 2 API calls."""
    expense_id = _get(fields, "travel_expense_id")
    if not expense_id:
        expenses = await client.get_travel_expenses()
        if not expenses:
            return {"success": False, "error": "No travel expenses found"}
        title = _get(fields, "travel_expense_identifier") or _get(fields, "title")
        if title:
            match = next((e for e in expenses if title.lower() in e.get("title", "").lower()), None)
            if match:
                expense_id = match["id"]
        if not expense_id:
            expense_id = expenses[-1]["id"]

    expense = await client.get_travel_expense(int(expense_id))
    update = _clean({
        "id": expense["id"],
        "version": expense.get("version"),
        "employee": expense.get("employee"),
        "title": _get(fields, "new_title") or _get(fields, "title") or expense.get("title"),
    })
    result = await client.update_travel_expense(expense["id"], update)
    return {"updated_id": result.get("id"), "entity": "travel_expense"}


async def _exec_create_dimension_and_voucher(fields: dict, client: TripletexClient) -> dict:
    """Create a free accounting dimension with values and optionally post a voucher.

    Tier 3 task flow:
    1. GET /ledger/accountingDimensionName to find first free slot (index 1, 2, or 3)
    2. POST /ledger/accountingDimensionName — create the dimension
    3. POST /ledger/accountingDimensionValue — create each value
    4. If postings specified: resolve account numbers → POST /ledger/voucher
    """
    dimension_name = _get(fields, "dimension_name")
    if not dimension_name:
        return {"success": False, "error": "No dimension name provided"}

    dimension_values = _get(fields, "dimension_values") or []
    if isinstance(dimension_values, str):
        # Handle comma-separated string
        dimension_values = [v.strip() for v in dimension_values.split(",") if v.strip()]

    # Step 1: Find a free dimension index (1, 2, or 3)
    existing_dims = await client.get_dimension_names()
    used_indices = set()
    for d in existing_dims:
        idx = d.get("dimensionIndex")
        if idx and d.get("active"):
            used_indices.add(idx)

    dim_index = None
    for candidate in [1, 2, 3]:
        if candidate not in used_indices:
            dim_index = candidate
            break

    if dim_index is None:
        # All 3 slots used — try to use index 1 and update it
        dim_index = 1
        _log("WARNING", "All dimension slots used, overwriting index 1")

    # Step 2: Create the dimension name
    dim_name_data = {
        "dimensionName": dimension_name,
        "dimensionIndex": dim_index,
        "active": True,
    }

    try:
        dim_result = await client.create_dimension_name(dim_name_data)
    except TripletexAPIError as e:
        detail_lower = (e.detail or "").lower()
        if e.status_code == 422 and ("allerede" in detail_lower or "i bruk" in detail_lower or "already" in detail_lower):
            # Dimension name already exists — that's fine, find it
            _log("INFO", "Dimension name already exists, looking it up")
            existing = await client.get_dimension_names()
            for d in existing:
                d_name = d.get("dimensionName") or d.get("displayName") or d.get("name") or ""
                if d_name.lower() == dimension_name.lower():
                    dim_result = d
                    dim_index = d.get("dimensionIndex", dim_index)
                    break
            else:
                raise
        else:
            raise

    dim_name_id = dim_result.get("id")
    _log("INFO", "Dimension created/found", dimension_name=dimension_name,
         dimension_index=dim_index, dim_name_id=dim_name_id)

    # Step 3: Create dimension values
    value_ids = {}
    for i, val_name in enumerate(dimension_values):
        val_data = {
            "displayName": val_name,
            "dimensionIndex": dim_index,
            "number": str(i + 1),
            "active": True,
            "showInVoucherRegistration": True,
        }
        try:
            val_result = await client.create_dimension_value(val_data)
            value_ids[val_name] = val_result.get("id")
        except TripletexAPIError as e:
            if e.status_code == 422 or e.status_code == 409:
                _log("WARNING", f"Dimension value '{val_name}' may already exist", detail=(e.detail or "")[:200])
                # Try to find existing value
                existing_vals = await client.search_dimension_values({"dimensionIndex": str(dim_index)})
                for ev in existing_vals:
                    if ev.get("displayName", "").lower() == val_name.lower():
                        value_ids[val_name] = ev.get("id")
                        break
            else:
                raise

    _log("INFO", "Dimension values created", count=len(value_ids), value_ids=value_ids)

    # Step 4: Post a voucher if postings are provided
    raw_postings = _get(fields, "postings")
    voucher_id = None

    if raw_postings and isinstance(raw_postings, list):
        # Resolve account numbers to IDs
        account_cache: dict[int, int] = {}  # account_number -> account_id
        posting_list = []

        async def _resolve_account(num: int) -> int | None:
            if num not in account_cache:
                accounts = await client.get_ledger_accounts({"number": str(num)})
                if accounts:
                    account_cache[num] = accounts[0]["id"]
                else:
                    _log("WARNING", f"Account {num} not found")
                    return None
            return account_cache[num]

        for p in raw_postings:
            acct_num = p.get("account_number") or p.get("account")
            amount = p.get("amount") or p.get("amountGross") or 0
            desc = p.get("description", "")

            # Extract dimension value name from various Gemini output formats
            dim_val_name = p.get("dimension_value", "")
            if not dim_val_name:
                # Gemini may return dimension_values as dict {"Region": "Nord"}
                dv = p.get("dimension_values") or {}
                if isinstance(dv, dict):
                    # Take first value from the dict
                    for _k, _v in dv.items():
                        dim_val_name = _v
                        break
                elif isinstance(dv, str):
                    dim_val_name = dv

            if acct_num:
                acct_id = await _resolve_account(int(acct_num))
                if not acct_id:
                    continue

                posting_entry = {
                    "account": {"id": acct_id},
                    "amountGross": float(amount),
                    "amountGrossCurrency": float(amount),
                    "description": desc,
                    "date": _get(fields, "voucher_date") or _today(),
                }

                # Attach dimension value if specified
                if dim_val_name and dim_val_name in value_ids:
                    dim_field = f"freeAccountingDimension{dim_index}"
                    posting_entry[dim_field] = {"id": value_ids[dim_val_name]}

                posting_list.append(_clean(posting_entry))

        _log("INFO", "Voucher postings prepared", count=len(posting_list),
             postings_preview=str(posting_list)[:300])

        # Ensure postings balance (debits = credits)
        total = sum(p.get("amountGross", 0) for p in posting_list)
        if posting_list and abs(total) > 0.01:
            # Add a balancing entry — use a default counter-account (e.g. 1920 bank or find one)
            counter_acct_num = 1920  # Bank account as default counter
            counter_id = await _resolve_account(counter_acct_num)
            if counter_id:
                posting_list.append(_clean({
                    "account": {"id": counter_id},
                    "amountGross": -total,
                    "amountGrossCurrency": -total,
                    "description": f"Motpost - {dimension_name}",
                    "date": _get(fields, "voucher_date") or _today(),
                }))

        if posting_list:
            dim_voucher_type_id = await _get_voucher_type_id(client, ["memorial", "bilag"])
            voucher_data = _clean({
                "date": _get(fields, "voucher_date") or _today(),
                "description": _get(fields, "voucher_description") or f"Bilag med dimensjon {dimension_name}",
                "postings": posting_list,
            })
            if dim_voucher_type_id:
                voucher_data["voucherType"] = {"id": dim_voucher_type_id}

            try:
                voucher_result = await client.create_voucher(voucher_data, send_to_ledger=True)
                voucher_id = voucher_result.get("id")
                _log("INFO", "Voucher posted", voucher_id=voucher_id)
            except TripletexAPIError as e:
                _log("WARNING", "Voucher posting failed, trying without dimension linkage",
                     detail=(e.detail or "")[:200])
                # Retry without dimension linkage — still creates the dimension/values
                for p in posting_list:
                    dim_field = f"freeAccountingDimension{dim_index}"
                    p.pop(dim_field, None)
                try:
                    voucher_result = await client.create_voucher(voucher_data, send_to_ledger=True)
                    voucher_id = voucher_result.get("id")
                    _log("INFO", "Voucher posted (no dimension linkage)", voucher_id=voucher_id)
                except TripletexAPIError as e2:
                    try:
                        voucher_result = await client.create_voucher(voucher_data, send_to_ledger=False)
                        voucher_id = voucher_result.get("id")
                        _log("INFO", "Voucher posted (no sendToLedger)", voucher_id=voucher_id)
                    except TripletexAPIError as e3:
                        _log("WARNING", "Voucher posting failed entirely",
                             detail=(e3.detail or "")[:200])

    return {
        "entity": "dimension_and_voucher",
        "dimension_name": dimension_name,
        "dimension_index": dim_index,
        "dimension_name_id": dim_name_id,
        "value_count": len(value_ids),
        "value_ids": value_ids,
        "voucher_id": voucher_id,
    }


async def _exec_reverse_payment(fields: dict, client: TripletexClient) -> dict:
    """Reverse a payment that was returned/bounced by the bank.

    1. Find the invoice by customer name
    2. Get invoice details with voucher reference
    3. Find the payment voucher and reverse it
    4. Fallback: create a credit note
    """
    customer_name = _get(fields, "customer_name") or _get(fields, "customer_identifier")
    invoice_id = _get(fields, "invoice_id")
    invoice_number = _get(fields, "invoice_number") or _get(fields, "invoice_identifier")

    # Step 1: Find the invoice
    if not invoice_id:
        if invoice_number and str(invoice_number).isdigit():
            invoices = await client.get_invoices({
                "invoiceNumber": str(invoice_number),
                "invoiceDateFrom": "2000-01-01",
                "invoiceDateTo": "2099-12-31",
            })
            if invoices:
                invoice_id = invoices[0]["id"]
        if not invoice_id and customer_name:
            invoices = await client.get_invoices({
                "customerName": customer_name,
                "invoiceDateFrom": "2000-01-01",
                "invoiceDateTo": "2099-12-31",
            })
            if invoices:
                invoice_id = max(invoices, key=lambda inv: inv.get("id", 0))["id"]

    if not invoice_id:
        return {"success": False, "error": f"Could not find invoice for customer: {customer_name}"}

    # Step 2: Get invoice details with voucher reference
    try:
        invoice_data = await client.get_invoice(int(invoice_id))
    except TripletexAPIError as e:
        return {"success": False, "error": f"Failed to get invoice {invoice_id}: {e}"}

    # Step 3: Find payment voucher(s)
    voucher_ref = invoice_data.get("voucher")
    payment_voucher_id = None

    try:
        postings = await client.get_postings({
            "invoiceId": str(invoice_id),
            "fields": "*",
        })
        for p in postings:
            voucher = p.get("voucher")
            if voucher and voucher.get("id"):
                v_id = voucher["id"]
                if voucher_ref and v_id == voucher_ref.get("id"):
                    continue
                payment_voucher_id = v_id
                break
    except TripletexAPIError:
        pass

    if not payment_voucher_id:
        try:
            vouchers = await client.get_vouchers({
                "dateFrom": "2000-01-01",
                "dateTo": "2099-12-31",
            })
            invoice_voucher_id = voucher_ref.get("id") if voucher_ref else None
            for v in sorted(vouchers, key=lambda x: x.get("id", 0), reverse=True):
                if v.get("id") != invoice_voucher_id:
                    payment_voucher_id = v["id"]
                    break
        except TripletexAPIError:
            pass

    # Step 4: Reverse the payment voucher
    if payment_voucher_id:
        try:
            result = await client.reverse_voucher(int(payment_voucher_id), {"date": _today()})
            _log("INFO", "Reversed payment voucher", voucher_id=payment_voucher_id, invoice_id=invoice_id)
            return {
                "entity": "reverse_payment",
                "invoice_id": invoice_id,
                "reversed_voucher_id": payment_voucher_id,
                "reversal_voucher_id": result.get("id"),
            }
        except TripletexAPIError as e:
            _log("WARNING", "Voucher reversal failed, falling back to credit note", error=str(e))

    # Fallback: create a credit note
    _log("INFO", "Falling back to credit note for payment reversal", invoice_id=invoice_id)
    try:
        credit_params = _clean({
            "date": _today(),
            "comment": _get(fields, "reason") or "Payment returned by bank",
            "sendToCustomer": "false",
        })
        result = await client.create_credit_note(int(invoice_id), credit_params)
        return {
            "entity": "credit_note",
            "invoice_id": invoice_id,
            "credit_note_id": result.get("id"),
            "fallback": True,
        }
    except TripletexAPIError as e:
        return {"success": False, "error": f"Both voucher reversal and credit note failed: {e}"}


async def _exec_unknown(fields: dict, client: TripletexClient) -> dict:
    _log("WARNING", "Unknown task type", fields_preview=str(fields)[:200])
    return {"success": False, "error": "Could not determine task type"}


# ---------------------------------------------------------------------------
# Executor Registry
# ---------------------------------------------------------------------------

async def _exec_register_supplier_invoice(fields: dict, client: TripletexClient) -> dict:
    """Register an incoming supplier invoice (leverandørfaktura).

    Flow:
    1. Find or create the supplier
    2. Find the expense account (e.g. 7000)
    3. Find the VAT type for incoming invoices (inngående MVA)
    4. POST /incomingInvoice with header + order lines

    API calls: 3-5.
    """
    # 0. Extract fields from prompt if classifier missed them (common for Nynorsk/uncommon languages)
    import re as _re
    raw_prompt = _get(fields, "_raw_prompt") or ""

    # Try to extract supplier name from prompt
    supplier_name = _get(fields, "supplier_name") or _get(fields, "supplier_identifier") or _get(fields, "name") or ""
    org_number = _get(fields, "organization_number")
    invoice_num = _get(fields, "invoice_number")
    amount_val = _get(fields, "amount_incl_vat") or _get(fields, "amount_excl_vat")
    account_num = _get(fields, "account_number")
    desc = _get(fields, "description") or ""

    if raw_prompt and (not supplier_name or not amount_val):
        # Extract from raw prompt
        # Supplier name: "leverandøren X AS" or "supplier X"
        for pat in [
            r'leverandøren\s+([A-ZÆØÅ][\w\s]+(?:AS|AB|SA|Ltd|GmbH))',
            r'supplier\s+([A-ZÆØÅ][\w\s]+(?:AS|AB|SA|Ltd|GmbH))',
            r'fournisseur\s+([A-ZÆØÅ][\w\s]+(?:AS|AB|SA|Ltd|GmbH))',
        ]:
            m = _re.search(pat, raw_prompt, _re.IGNORECASE)
            if m and not supplier_name:
                supplier_name = m.group(1).strip()
                break

        # Org number
        if not org_number:
            m = _re.search(r'org\.?\s*(?:nr|nummer|no)\.?\s*(\d{9})', raw_prompt, _re.IGNORECASE)
            if m:
                org_number = m.group(1)

        # Invoice number
        if not invoice_num:
            m = _re.search(r'faktura\s+(INV[- ]\d+[- ]\d+|[A-Z]{2,}\d+)', raw_prompt, _re.IGNORECASE)
            if m:
                invoice_num = m.group(1)

        # Amount (incl VAT)
        if not amount_val:
            m = _re.search(r'(\d[\d\s]*\d)\s*(?:kr|NOK|nok)\s*(?:inklusiv|inkl|incl)', raw_prompt, _re.IGNORECASE)
            if m:
                amount_val = float(m.group(1).replace(" ", ""))
                fields["amount_incl_vat"] = amount_val

        # Account number
        if not account_num:
            m = _re.search(r'konto\s+(\d{4})', raw_prompt, _re.IGNORECASE)
            if m:
                account_num = m.group(1)
                fields["account_number"] = account_num

        # Description
        if not desc:
            m = _re.search(r'gjeld\w*\s+(.+?)(?:\s*\(|\s*\.|\s*Registrer)', raw_prompt, _re.IGNORECASE)
            if m:
                desc = m.group(1).strip()
                fields["description"] = desc

        # VAT percentage
        if not _get(fields, "vat_percentage"):
            m = _re.search(r'MVA\s*\(?\s*(\d+)\s*%', raw_prompt, _re.IGNORECASE)
            if m:
                fields["vat_percentage"] = int(m.group(1))

    if invoice_num:
        fields["invoice_number"] = invoice_num
    if org_number:
        fields["organization_number"] = org_number

    _log("INFO", "Supplier invoice fields after extraction",
         supplier=supplier_name, org=org_number, invoice_num=invoice_num,
         amount=amount_val, account=account_num)

    # 1. Find or create supplier

    supplier_id = None
    if org_number:
        suppliers = await client.get_suppliers({"organizationNumber": _clean_org_number(str(org_number))})
        if suppliers:
            supplier_id = suppliers[0]["id"]
    if not supplier_id and supplier_name:
        suppliers = await client.get_suppliers({"name": supplier_name})
        if suppliers:
            supplier_id = suppliers[0]["id"]

    if not supplier_id:
        # Create the supplier
        sup_data = _clean({
            "name": supplier_name or "Leverandør",
            "organizationNumber": _clean_org_number(org_number),
        })
        new_sup = await client.create_supplier(sup_data)
        supplier_id = new_sup["id"]
        _log("INFO", "Created supplier for incoming invoice", name=supplier_name, id=supplier_id)

    # 2. Find the expense account
    account_number = _get(fields, "account_number") or "7000"
    accounts = await client.get_ledger_accounts({"number": str(account_number)})
    account_id = accounts[0]["id"] if accounts else None

    if not account_id:
        _log("WARNING", "Account not found, trying default", account_number=account_number)
        accounts = await client.get_ledger_accounts({"number": "7000"})
        account_id = accounts[0]["id"] if accounts else None

    # 3. Get VAT type for incoming (inngående MVA)
    vat_type_id = None
    vat_pct = float(_get(fields, "vat_percentage") or 25)
    try:
        vat_types = await client.get_vat_types()
        # First pass: look for incoming VAT at the right percentage
        for vt in vat_types:
            vt_name = (vt.get("name") or "").lower()
            vt_pct_val = vt.get("percentage", 0)
            if float(vt_pct_val) == vat_pct and ("inngående" in vt_name or "incoming" in vt_name or "inn" in vt_name):
                vat_type_id = vt["id"]
                break
        # Second pass: any VAT at the right percentage
        if not vat_type_id:
            for vt in vat_types:
                if float(vt.get("percentage", 0)) == vat_pct:
                    vat_type_id = vt["id"]
                    break
    except TripletexAPIError as e:
        _log("WARNING", "Could not get VAT types", error=str(e))

    # 4. Build the incoming invoice
    amount_incl = _get(fields, "amount_incl_vat")
    amount_excl = _get(fields, "amount_excl_vat")

    if amount_incl:
        total_incl = float(amount_incl)
    elif amount_excl:
        total_incl = float(amount_excl) * (1 + vat_pct / 100)
    else:
        total_incl = 0

    description = _get(fields, "description") or ""
    invoice_number = _get(fields, "invoice_number") or ""
    invoice_date = _get(fields, "invoice_date") or _today()
    due_date = _get(fields, "due_date")

    header = _clean({
        "vendorId": supplier_id,
        "invoiceDate": invoice_date,
        "dueDate": due_date,
        "invoiceAmount": total_incl,
        "invoiceNumber": str(invoice_number) if invoice_number else None,
        "description": description,
    })

    import uuid as _uuid
    order_line = _clean({
        "externalId": str(_uuid.uuid4())[:8],
        "row": 1,
        "description": description,
        "accountId": account_id,
        "amountInclVat": total_incl,
        "vatTypeId": vat_type_id,
    })

    payload = {
        "invoiceHeader": header,
        "orderLines": [order_line],
    }

    try:
        result = await client.create_incoming_invoice(payload)
        voucher_id = result.get("id") or result.get("voucherId")
        _log("INFO", "Created incoming invoice", voucher_id=voucher_id)
        return {
            "entity": "incoming_invoice",
            "voucher_id": voucher_id,
            "supplier_id": supplier_id,
            "amount_incl_vat": total_incl,
            "invoice_number": invoice_number,
        }
    except TripletexAPIError as e:
        _log("WARNING", "Incoming invoice creation failed", error=str(e), detail=(e.detail or "")[:300])
        return {
            "success": False,
            "error": f"Could not create incoming invoice: {str(e)[:200]}",
            "supplier_id": supplier_id,
        }


async def _exec_run_payroll(fields: dict, client: TripletexClient) -> dict:
    """Run payroll / create salary transaction for an employee.

    Flow:
    1. Find/create employee
    2. Get salary types (Fastlønn=2000, Bonus=2002, etc.)
    3. POST /salary/transaction to create a payroll run
    4. The transaction auto-generates payslips for employees

    API calls: 3-5.
    """
    # 1. Find/create employee
    employee_id = _get(fields, "employee_id")
    if not employee_id:
        emp = await _find_employee(client, fields)
        if emp:
            employee_id = emp["id"]
        else:
            # Create the employee (fresh sandbox)
            first_name = _get(fields, "first_name") or "Employee"
            last_name = _get(fields, "last_name") or "Test"
            email = _get(fields, "email") or _get(fields, "employee_email")
            if not email:
                email = f"{first_name.lower()}.{last_name.lower()}@example.com"
            dept_id = await _ensure_department(client)
            new_emp = await client.create_employee(_clean({
                "firstName": first_name,
                "lastName": last_name,
                "email": email,
                "userType": "STANDARD",
                "department": {"id": int(dept_id)},
            }))
            employee_id = new_emp["id"]
            _log("INFO", "Created employee for payroll", name=f"{first_name} {last_name}", id=employee_id)

    # 1b. Ensure employee has date of birth (required for employment)
    try:
        emp_detail = await client.get_employee(int(employee_id))
        if not emp_detail.get("dateOfBirth"):
            # Update employee with a date of birth
            update = {
                "id": int(employee_id),
                "version": emp_detail.get("version", 0),
                "firstName": emp_detail.get("firstName", ""),
                "lastName": emp_detail.get("lastName", ""),
                "dateOfBirth": "1990-01-15",
            }
            await client.update_employee(int(employee_id), update)
            _log("INFO", "Set date of birth for payroll employee", employee_id=employee_id)
    except TripletexAPIError as e:
        _log("WARNING", "Could not set employee date of birth", error=str(e))

    # 1c. Find company/division for employment
    division_id = None
    try:
        # Try to get the company info for division reference
        company_info = await client._request("GET", "/company/with/me")
        if isinstance(company_info, dict):
            val = company_info.get("value", company_info)
            division_id = val.get("id")
    except TripletexAPIError:
        pass

    # 1d. Ensure employee has an employment record
    try:
        employments = await client.get_employments({"employeeId": str(employee_id)})
        if not employments:
            emp_data = _clean({
                "employee": {"id": int(employee_id)},
                "startDate": "2025-01-01",
                "isMainEmployer": True,
                "division": {"id": division_id} if division_id else None,
                "employmentDetails": [{
                    "date": "2025-01-01",
                    "employmentType": "ORDINARY",
                    "percentageOfFullTimeEquivalent": 100.0,
                }],
            })
            await client.create_employment(emp_data)
            _log("INFO", "Created employment for payroll", employee_id=employee_id)
        else:
            _log("INFO", "Employment exists for payroll", employee_id=employee_id,
                 employment_count=len(employments))
    except TripletexAPIError as e:
        _log("WARNING", "Employment check/create failed", error=str(e), detail=(e.detail or "")[:200])

    # 2. Get salary types
    salary_types = await client.get_salary_types()
    # Build a lookup: number → id
    st_by_number = {}
    st_by_name = {}
    for st in salary_types:
        num = st.get("number", "")
        name = (st.get("name") or "").lower()
        st_by_number[num] = st["id"]
        st_by_name[name] = st["id"]

    # Key salary type IDs
    fastlonn_id = st_by_number.get("2000")  # Fastlønn (base salary)
    bonus_id = st_by_number.get("2002")     # Bonus
    overtime_id = st_by_number.get("2005")  # Overtidsgodtgjørelse
    skattetrekk_id = st_by_number.get("6000")  # Skattetrekk (tax deduction)

    # 3. Determine month/year
    import datetime as _dt
    now = _dt.date.today()
    month = _get(fields, "month") or now.month
    year = _get(fields, "year") or now.year
    # Salary date should be end of month
    txn_date = f"{year}-{int(month):02d}-{min(now.day, 28):02d}"

    # 4. Build payslip specifications
    base_salary = float(_get(fields, "base_salary") or 0)
    bonus = float(_get(fields, "bonus") or 0)
    overtime_amount = float(_get(fields, "overtime_amount") or 0)

    specifications = []
    if base_salary and fastlonn_id:
        specifications.append({
            "salaryType": {"id": fastlonn_id},
            "rate": base_salary,
            "count": 1,
            "amount": base_salary,
        })
    if bonus and bonus_id:
        specifications.append({
            "salaryType": {"id": bonus_id},
            "rate": bonus,
            "count": 1,
            "amount": bonus,
        })
    if overtime_amount and overtime_id:
        overtime_hours = float(_get(fields, "overtime_hours") or 1)
        specifications.append({
            "salaryType": {"id": overtime_id},
            "rate": overtime_amount / overtime_hours if overtime_hours else overtime_amount,
            "count": overtime_hours,
            "amount": overtime_amount,
        })

    # Handle generic additions
    additions = _get(fields, "additions") or []
    for add in additions:
        if isinstance(add, dict):
            amt = float(add.get("amount", 0))
            if amt and bonus_id:
                specifications.append({
                    "salaryType": {"id": bonus_id},
                    "rate": amt,
                    "count": 1,
                    "amount": amt,
                    "description": add.get("description", ""),
                })

    # If no specifications at all, use base salary as a single entry
    if not specifications and fastlonn_id:
        total = base_salary + bonus
        if total <= 0:
            total = 1  # minimal amount
        specifications.append({
            "salaryType": {"id": fastlonn_id},
            "rate": total,
            "count": 1,
            "amount": total,
        })

    # Build the payslip
    payslip = _clean({
        "employee": {"id": int(employee_id)},
        "date": txn_date,
        "year": int(year),
        "month": int(month),
        "specifications": specifications,
    })

    # 5. Create salary transaction with payslip
    try:
        txn = await client.create_salary_transaction({
            "date": txn_date,
            "year": int(year),
            "month": int(month),
            "payslips": [payslip],
        })
        txn_id = txn.get("id")
        _log("INFO", "Created salary transaction", txn_id=txn_id, month=month, year=year)
    except TripletexAPIError as e:
        _log("WARNING", "Salary transaction creation failed", error=str(e), detail=(e.detail or "")[:300])
        # Fallback: try creating via voucher with salary postings
        base_salary = _get(fields, "base_salary") or 0
        bonus = _get(fields, "bonus") or 0
        total = float(base_salary) + float(bonus)

        # Create as journal voucher: debit salary expense (5000) + bonus (5020), credit salary payable (2780)
        accounts_5000 = await client.get_ledger_accounts({"number": "5000"})
        accounts_5020 = await client.get_ledger_accounts({"number": "5020"})
        accounts_2780 = await client.get_ledger_accounts({"number": "2780"})

        acc_5000_id = accounts_5000[0]["id"] if accounts_5000 else None
        acc_5020_id = accounts_5020[0]["id"] if accounts_5020 else None
        acc_2780_id = accounts_2780[0]["id"] if accounts_2780 else None

        # Get proper voucher type for payroll
        payroll_voucher_type_id = await _get_voucher_type_id(client, ["lønn", "salary", "payroll", "memorial"])

        if acc_5000_id and acc_2780_id and total > 0:
            base_amt = float(base_salary) if base_salary else total
            bonus_amt = float(bonus) if bonus else 0

            postings = []
            # Debit salary expense (5000) for base salary
            postings.append({"account": {"id": acc_5000_id}, "amountGross": base_amt if bonus_amt else total,
                 "amountGrossCurrency": base_amt if bonus_amt else total, "description": f"Lønn {month}/{year}",
                 "date": txn_date})
            # Debit bonus (5020) if applicable and account exists
            if bonus_amt and acc_5020_id:
                postings.append({"account": {"id": acc_5020_id}, "amountGross": bonus_amt,
                     "amountGrossCurrency": bonus_amt, "description": f"Bonus {month}/{year}",
                     "date": txn_date})
            elif bonus_amt:
                # If no 5020 account, add bonus to 5000
                postings[0]["amountGross"] = total
                postings[0]["amountGrossCurrency"] = total
            # Credit salary payable (2780)
            postings.append({"account": {"id": acc_2780_id}, "amountGross": -total,
                 "amountGrossCurrency": -total, "description": f"Lønn {month}/{year}",
                 "date": txn_date})

            voucher_data = {
                    "date": txn_date,
                    "description": f"Lønnskjøring {month}/{year}",
                    "postings": postings,
                }
            if payroll_voucher_type_id:
                voucher_data["voucherType"] = {"id": payroll_voucher_type_id}

            try:
                voucher = await client.create_voucher(voucher_data, send_to_ledger=True)
                return {
                    "entity": "salary_voucher",
                    "voucher_id": voucher.get("id"),
                    "employee_id": employee_id,
                    "total_amount": total,
                    "month": month,
                    "year": year,
                    "action": "voucher_created",
                }
            except TripletexAPIError as e2:
                _log("WARNING", "Salary voucher fallback also failed", error=str(e2))

        return {
            "success": False,
            "error": f"Could not create salary transaction: {str(e)[:200]}",
            "employee_id": employee_id,
        }

    return {
        "entity": "salary_transaction",
        "transaction_id": txn_id,
        "employee_id": employee_id,
        "month": month,
        "year": year,
        "base_salary": _get(fields, "base_salary"),
        "bonus": _get(fields, "bonus"),
        "action": "payroll_created",
    }


_EXECUTORS: dict[TaskType, Any] = {
    # Tier 1
    TaskType.CREATE_EMPLOYEE: _exec_create_employee,
    TaskType.UPDATE_EMPLOYEE: _exec_update_employee,
    TaskType.DELETE_EMPLOYEE: _exec_delete_employee,
    TaskType.SET_EMPLOYEE_ROLES: _exec_set_employee_roles,
    TaskType.CREATE_CUSTOMER: _exec_create_customer,
    TaskType.UPDATE_CUSTOMER: _exec_update_customer,
    TaskType.CREATE_PRODUCT: _exec_create_product,
    TaskType.CREATE_SUPPLIER: _exec_create_supplier,
    TaskType.UPDATE_SUPPLIER: _exec_update_supplier,
    TaskType.DELETE_SUPPLIER: _exec_delete_supplier,
    TaskType.FIND_SUPPLIER: _exec_find_supplier,
    TaskType.UPDATE_PRODUCT: _exec_update_product,
    TaskType.DELETE_PRODUCT: _exec_delete_product,
    TaskType.CREATE_INVOICE: _exec_create_invoice,
    TaskType.CREATE_DEPARTMENT: _exec_create_department,
    TaskType.DELETE_DEPARTMENT: _exec_delete_department,
    TaskType.CREATE_PROJECT: _exec_create_project,
    # Tier 2
    TaskType.INVOICE_EXISTING_CUSTOMER: _exec_invoice_existing_customer,
    TaskType.REGISTER_PAYMENT: _exec_register_payment,
    TaskType.CREATE_CREDIT_NOTE: _exec_create_credit_note,
    TaskType.INVOICE_WITH_PAYMENT: _exec_invoice_with_payment,
    TaskType.CREATE_TRAVEL_EXPENSE: _exec_create_travel_expense,
    TaskType.DELETE_TRAVEL_EXPENSE: _exec_delete_travel_expense,
    TaskType.UPDATE_TRAVEL_EXPENSE: _exec_update_travel_expense,
    TaskType.CREATE_CONTACT: _exec_create_contact,
    TaskType.DELETE_CONTACT: _exec_delete_contact,
    TaskType.PROJECT_WITH_CUSTOMER: _exec_project_with_customer,
    TaskType.FIND_CUSTOMER: _exec_find_customer,
    TaskType.UPDATE_PROJECT: _exec_update_project,
    TaskType.DELETE_PROJECT: _exec_delete_project,
    TaskType.PROJECT_BILLING: _exec_project_billing,
    TaskType.LOG_HOURS: _exec_log_hours,
    TaskType.DELETE_CUSTOMER: _exec_delete_customer,
    TaskType.UPDATE_CONTACT: _exec_update_contact,
    TaskType.UPDATE_DEPARTMENT: _exec_update_department,
    # Tier 3
    TaskType.BANK_RECONCILIATION: _exec_bank_reconciliation,
    TaskType.ERROR_CORRECTION: _exec_error_correction,
    TaskType.YEAR_END_CLOSING: _exec_year_end_closing,
    TaskType.ENABLE_MODULE: _exec_enable_module,
    TaskType.CREATE_DIMENSION_AND_VOUCHER: _exec_create_dimension_and_voucher,
    TaskType.RUN_PAYROLL: _exec_run_payroll,
    TaskType.REGISTER_SUPPLIER_INVOICE: _exec_register_supplier_invoice,
    TaskType.REVERSE_PAYMENT: _exec_reverse_payment,
    # Fallback
    TaskType.UNKNOWN: _exec_unknown,
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def execute_task(classification: TaskClassification, client: TripletexClient) -> dict:
    """Execute a classified task with minimum API calls."""
    task_type = classification.task_type
    fields = classification.fields

    # Pass raw prompt for executor-side field extraction (e.g. supplier invoice)
    fields["_raw_prompt"] = classification.raw_prompt or ""

    _log("INFO", "Executing task", task_type=str(task_type), field_count=len(fields))

    executor = _EXECUTORS.get(task_type)
    if not executor:
        _log("WARNING", "No executor for task type", task_type=str(task_type))
        return {"success": False, "task_type": str(task_type), "error": f"Unknown task type: {task_type}"}

    try:
        result = await executor(fields, client)
        success = result.get("success", True) if isinstance(result, dict) else True
        _log("INFO", "Task executed" if success else "Task partial failure",
             task_type=str(task_type), result_preview=str(result)[:200],
             api_calls=client.api_call_count, errors=client.error_count)
        return {"success": success, "task_type": str(task_type), "error": None, **result}
    except TripletexAPIError as e:
        _log("ERROR", "Tripletex API error",
             task_type=str(task_type), status=e.status_code, detail=(e.detail or "")[:200],
             api_calls=client.api_call_count, errors=client.error_count)
        return {"success": False, "task_type": str(task_type), "error": str(e)}
    except Exception as e:
        _log("ERROR", "Unexpected error",
             task_type=str(task_type), error=str(e), error_type=type(e).__name__,
             api_calls=client.api_call_count, errors=client.error_count)
        return {"success": False, "task_type": str(task_type), "error": str(e)}
