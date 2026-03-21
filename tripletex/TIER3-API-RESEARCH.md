# Tier 3 API Research — Missing Task Types

**Date:** 2026-03-21
**Status:** All 4 task types already have executors implemented!

## Summary

After reviewing `executor.py`, `tripletex_client.py`, and `task_types.py`, all four "missing" task types already have working implementations:

| Task Type | Executor Function | Line | Status |
|-----------|------------------|------|--------|
| YEAR_END_CLOSING | `_exec_year_end_closing` | executor.py:2313 | Implemented |
| RUN_PAYROLL | `_exec_run_payroll` | executor.py:2625 | Implemented |
| ENABLE_MODULE | `_exec_enable_module` | executor.py:2506 | Implemented |
| REGISTER_SUPPLIER_INVOICE | `_exec_create_supplier_invoice` | executor.py:2845 | Implemented (as CREATE_SUPPLIER_INVOICE) |

All four are registered in the `_HANDLERS` dispatch table (executor.py:3605-3611).

---

## 1. YEAR_END_CLOSING (executor.py:2313-2503)

**Purpose:** Perform year-end closing (årsavslutning) for a given fiscal year.

**Classifier fields:** `year` (e.g., 2025)

### API Endpoints Used (3 approaches, tried in order):

#### Approach 1: Annual Account endpoint
- `GET /ledger/annualAccount` with `?yearFrom={year}&yearTo={year}`
- `PUT /ledger/annualAccount/{id}/:close` — close the annual account
- Fallback: `PUT /ledger/annualAccount/{id}` with `status: "CLOSED"`, `isClosed: true`

#### Approach 2: Closing journal entries (voucher)
If annual account approach fails:
1. `GET /ledger/voucherType` — find a suitable voucher type (searches for: årsavslutning, year-end, closing, avslutning, årsoppgjør)
2. `GET /ledger/account?numberFrom=2050&numberTo=2050` — equity account
3. `GET /ledger/account?numberFrom=8960&numberTo=8960` — result account
4. `GET /ledger/posting?dateFrom={year}-01-01&dateTo={year}-12-31&accountNumberFrom=3000&accountNumberTo=8999` — sum P&L
5. `POST /ledger/voucher` — create closing voucher transferring P&L to equity

**Voucher payload:**
```json
{
  "date": "{year}-12-31",
  "description": "Årsavslutning {year} - Overføring av årsresultat til egenkapital",
  "voucherType": {"id": <voucher_type_id>},
  "postings": [
    {"date": "{year}-12-31", "account": {"id": <result_8960>}, "amountGross": -amount},
    {"date": "{year}-12-31", "account": {"id": <equity_2050>}, "amountGross": amount}
  ]
}
```

#### Approach 3: Close Group
- `GET /ledger/closeGroup?dateFrom={year}-01-01&dateTo={year}-12-31`

### Client methods (tripletex_client.py):
- `get_annual_accounts()` — GET /ledger/annualAccount
- `close_annual_account(id)` — PUT /ledger/annualAccount/{id}/:close
- `update_annual_account(id, data)` — PUT /ledger/annualAccount/{id}
- `get_close_group()` — GET /ledger/closeGroup

---

## 2. RUN_PAYROLL (executor.py:2625-2806)

**Purpose:** Run payroll / create salary payment for an employee.

**Classifier fields:** `employee_identifier`, `first_name`, `last_name`, `email`, `base_salary`, `bonus`, `month`, `year`, `period`

### Strategy: Voucher-based salary posting
The salary API (`/salary/transaction`) is available but the executor uses voucher postings to avoid system-managed account restrictions.

### API Endpoints Used:
1. **Find employee:** `GET /employee?firstName={name}` (shared `_find_employee` helper)
2. **Find salary expense account:** `GET /ledger/account?number={n}` — tries 7700, 7000, 5900, 7099 (avoids 5000 which is system-managed)
3. **Find salary liability account:** `GET /ledger/account?number={n}` — tries 2920, 2780, 2400
4. **Get voucher type:** `GET /ledger/voucherType` — searches for "lønn", "salary", "payroll"
5. **Create salary voucher:** `POST /ledger/voucher`

**Voucher payload:**
```json
{
  "date": "{payroll_date}",
  "description": "Lønn {month_name} {year}: {employee_name}",
  "voucherType": {"id": <voucher_type_id>},
  "postings": [
    {"date": "...", "account": {"id": <expense_7700>}, "amountGross": base_salary, "description": "Base salary - Name"},
    {"date": "...", "account": {"id": <expense_7700>}, "amountGross": bonus, "description": "Bonus - Name"},
    {"date": "...", "account": {"id": <liability_2920>}, "amountGross": -total, "description": "Lønn ..."}
  ]
}
```

**Key details:**
- Account 5000 is system-managed (salary module), so 7700/7000/5900 are used instead
- Default salary: 30,000 NOK if none specified
- Payroll date: last day of the payroll month
- Norwegian month name parsing supported

### Client methods (tripletex_client.py):
- `get_salary_types()` — GET /salary/type
- `create_salary_transaction()` — POST /salary/transaction
- `get_payslips()` — GET /salary/payslip
- Note: These exist but the executor uses the voucher approach instead

---

## 3. ENABLE_MODULE (executor.py:2506-2622)

**Purpose:** Enable a company module/feature in Tripletex.

**Classifier fields:** `module_name` (e.g., "Reiseregning", "Travel Expense", "Prosjekt")

### API Endpoints Used:
1. `GET /company/modules?fields=*` — get current module flags + version
2. `PUT /company/modules` — enable target module flags (set to `true`)
3. Fallback on 405: `POST /company/salesmodules` with `{"moduleName": "..."}`

### Module Name → API Field Mapping:
| Norwegian / English | API Field(s) |
|---|---|
| Reiseregning / Travel Expense | `moduletravelexpense` |
| Avdelingsregnskap / Dept Accounting | `moduleDepartmentAccounting` |
| Prosjekt / Project | `moduleproject`, `moduleprojecteconomy` |
| Timeregistrering / Time Tracking | `completeMonthlyHourLists` |
| Produkt / Product | `moduleProduct` |
| Faktura / Invoice | `moduleinvoice` |
| Valuta / Currency | `moduleCurrency` |
| Ansatt / Employee | `moduleemployee` |
| Kunde / Customer | `modulecustomer` |

### Flow:
1. GET current modules → check if already enabled (return early if so)
2. Build update payload with target fields set to `true`
3. PUT /company/modules
4. On 405 → try POST /company/salesmodules
5. On second failure → report error with current state

### Client methods (tripletex_client.py):
- `get_company_modules()` — GET /company/modules?fields=*
- `update_company_modules(data)` — PUT /company/modules (may return 405 in sandbox)

---

## 4. REGISTER_SUPPLIER_INVOICE / CREATE_SUPPLIER_INVOICE (executor.py:2845-2985)

**Purpose:** Register an incoming supplier/vendor invoice.

**Note:** `REGISTER_SUPPLIER_INVOICE` appears in test classifier cases but maps to `CREATE_SUPPLIER_INVOICE` in the task_types enum. The executor is `_exec_create_supplier_invoice`.

**Classifier fields:** `supplier_name`, `name`, `organization_number`, `amount_including_vat`, `amount_excluding_vat`, `amount`, `account_number`, `invoice_number`, `invoice_date`, `due_date`, `description`

### Strategy: Voucher-based, with /supplierInvoice fallback

### API Endpoints Used:

#### Primary: Voucher approach
1. `GET /supplier?name={name}` or `?organizationNumber={org}` — find existing supplier
2. `POST /supplier` — create supplier if not found
3. `GET /ledger/account?number=4000` — expense account
4. `GET /ledger/account?number=2400` — supplier liability account
5. `POST /ledger/voucher` — create voucher with debit/credit postings

**Voucher payload:**
```json
{
  "date": "{invoice_date}",
  "description": "Supplier invoice from {supplier_name}",
  "postings": [
    {"date": "...", "account": {"id": <expense_4000>}, "amountGross": amount, "row": 1},
    {"date": "...", "account": {"id": <liability_2400>}, "supplier": {"id": <supplier_id>}, "amountGross": -amount, "row": 2}
  ]
}
```

#### Fallback: /supplierInvoice endpoint
If voucher creation fails, tries:
```
POST /supplierInvoice
```
```json
{
  "invoiceNumber": "{invoice_number}",
  "invoiceDate": "{date}",
  "invoiceDueDate": "{due_date}",
  "supplier": {"id": <supplier_id>},
  "voucher": {
    "date": "{date}",
    "description": "...",
    "postings": [...]
  }
}
```

### Client methods (tripletex_client.py):
- `create_incoming_invoice(data)` — POST /incomingInvoice (exists but NOT used by executor)
- `get_incoming_invoice_vat_types()` — GET /incomingInvoice/vatType
- Note: The `/incomingInvoice` endpoint exists in the client but the executor uses voucher + /supplierInvoice instead

---

## Potential Issues / Gaps

1. **REGISTER_SUPPLIER_INVOICE not in task_types.py** — The test files reference `TaskType.REGISTER_SUPPLIER_INVOICE` but it doesn't exist in `task_types.py`. Either it needs to be added as an alias for `CREATE_SUPPLIER_INVOICE`, or the classifier needs to route these to `CREATE_SUPPLIER_INVOICE`.

2. **`/incomingInvoice` endpoint unused** — The client has `create_incoming_invoice()` (POST /incomingInvoice) which may be more appropriate for registering incoming supplier invoices. The current executor uses voucher postings instead. Could try `/incomingInvoice` as a primary or fallback approach.

3. **RUN_PAYROLL avoids salary API** — The `/salary/transaction` endpoint exists in the client but isn't used. The voucher-based approach works but may not create proper payslips. If salary module tasks require actual payslips, the salary API may need to be integrated.

4. **YEAR_END_CLOSING sandbox limitations** — The `:close` action on annual accounts may fail in sandbox. The voucher fallback is robust but creates manual closing entries rather than using the built-in closing flow.
