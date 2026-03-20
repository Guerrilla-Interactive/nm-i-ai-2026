# Tripletex API — Advanced/Tier 2-3 Endpoint Testing

**Base URL:** `https://kkpqfuj-amager.tripletex.dev/v2`
**Auth:** Basic Auth, username `0`, password (session token)
**Tested:** 2026-03-20

---

## 1. Ledger Endpoints

### GET /ledger/account — Chart of Accounts
- **Status:** 200 OK
- **Full result size:** 11 accounts
- **Query params:** `?count=N`, `?numberFrom=X&numberTo=Y`, `?number=N`, `?id=N`
- **Response structure:**
  ```json
  {
    "id": 436982614,
    "number": 1920,
    "name": "Bankinnskudd",
    "type": "ASSETS",  // ASSETS, EQUITY, etc.
    "legalVatTypes": [...],
    "ledgerType": "GENERAL",
    "balanceGroup": "Fordringer",
    "vatType": {"id": 0},
    "isBankAccount": true/false,
    "isInvoiceAccount": true/false,
    "requireReconciliation": true/false,
    "requiresDepartment": false,
    "requiresProject": false,
    "saftCode": "19",
    "displayName": "1920 Bankinnskudd"
  }
  ```

### GET /ledger/vatType — VAT Types
- **Status:** 200 OK
- **Full result size:** 11 types
- **Key VAT types found:**
  - id=1: 25% Fradrag inngående avgift, høy sats
  - id=3: 25% Utgående avgift, høy sats
  - id=5: 0% Ingen utgående avgift (innenfor mva-loven)
  - id=6: 0% Ingen utgående avgift (utenfor mva-loven)
  - id=7: 0% Ingen avgiftsbehandling (inntekter)
  - id=11: 15% middels sats
  - id=12: 12% lav sats
- **Response structure:**
  ```json
  {
    "id": 3,
    "name": "Utgående avgift, høy sats",
    "number": "3",
    "displayName": "3: (25%) Utgående avgift, høy sats",
    "percentage": 25,
    "deductionPercentage": 100.0,
    "parentType": {"id": 0}
  }
  ```

### GET /ledger/postingCategory — NOT FOUND (404)

### GET /ledger/accountingPeriod
- **Status:** 200 OK
- **Full result size:** 6 periods (Jan-Jun 2026)
- **Response structure:**
  ```json
  {
    "id": 23731256,
    "name": "Januar",
    "number": 0,
    "start": "2026-01-01",
    "end": "2026-02-01",
    "isClosed": false
  }
  ```

### GET /ledger/annualAccount
- **Status:** 200 OK
- **Response:** `{"id": 1991417, "year": 2026, "start": "2026-01-01", "end": "2027-01-01"}`

### GET /ledger/closeGroup?dateFrom=...&dateTo=...
- **Status:** 200 OK (requires dateFrom/dateTo params)
- **Result:** Empty in sandbox

### GET /ledger/posting?dateFrom=...&dateTo=...
- **Status:** 200 OK (requires dateFrom/dateTo)
- **Result:** Populated after voucher creation

### GET /ledger/paymentTypeOut
- **Status:** 200 OK
- **Full result size:** 4 payment types
- **Values:**
  - "1920 Manuelt betalt nettbank" (creditAccount: 1920)
  - Shows for incoming invoice, wage payment, travel/expense
- **Response structure:**
  ```json
  {
    "id": 33998620,
    "description": "1920 Manuelt betalt nettbank",
    "creditAccount": {"id": 436982614},
    "showIncomingInvoice": true,
    "showWagePayment": true,
    "showVatReturns": false
  }
  ```

### POST /ledger/voucher — Create Voucher (Tier 3)
- **Status:** 200 OK (SUCCESS!)
- **Required fields:**
  - `date` (string, YYYY-MM-DD)
  - `description` (string)
  - `postings` (array, cannot be null, must contain entries)
    - Each posting needs: `date`, `description`, `account.id`, `employee.id`, `amountGross`, `amountGrossCurrency`, `currency.id`, `row`
- **Important:** Postings on row 0 are system-generated and cannot be created. Use row >= 1.
- **Important:** `employee.id` is required on postings.
- **Example successful request:**
  ```json
  {
    "date": "2026-03-20",
    "description": "API Test Voucher",
    "postings": [
      {
        "date": "2026-03-20",
        "description": "Test debit",
        "account": {"id": 436982614},
        "employee": {"id": 18491802},
        "amountGross": 1000,
        "amountGrossCurrency": 1000,
        "currency": {"id": 1},
        "row": 1
      },
      {
        "date": "2026-03-20",
        "description": "Test credit",
        "account": {"id": 436982711},
        "employee": {"id": 18491802},
        "amountGross": -1000,
        "amountGrossCurrency": -1000,
        "currency": {"id": 1},
        "row": 2
      }
    ]
  }
  ```
- **Response includes:** voucher id, version, number, year, full posting details with system-assigned IDs

### GET /ledger/voucher?dateFrom=...&dateTo=...
- **Status:** 200 OK (requires dateFrom/dateTo)

---

## 2. Payment Endpoints

### GET /payment/paymentType — NOT FOUND (404)
### GET /payment — NOT FOUND (404)

### GET /invoice/paymentType
- **Status:** 200 OK
- **Full result size:** 2
- **Values:**
  - "Kontant" (debitAccount: 436982611)
  - Another payment type
- **Response structure:**
  ```json
  {
    "id": 33998616,
    "description": "Kontant",
    "displayName": "Kontant",
    "debitAccount": {"id": 436982611}
  }
  ```

### GET /bank/reconciliation/paymentType
- **Status:** 200 OK
- **Full result size:** 4
- **Values include:** "Bankgebyr" (debitAccount: 436982944 = bank fees)

---

## 3. Bank Reconciliation

### GET /bank/reconciliation
- **Status:** 200 OK
- **Returns:** List of reconciliations (empty initially)

### POST /bank/reconciliation — Create Reconciliation (Tier 3)
- **Status:** 200 OK (SUCCESS!)
- **Required fields:**
  - `account.id` — ledger account (e.g., bank account 1920)
  - `accountingPeriod.id` — must reference a valid accounting period ID
  - `type` — "MANUAL" or other types
- **Example request:**
  ```json
  {
    "account": {"id": 436982614},
    "accountingPeriod": {"id": 23731256},
    "type": "MANUAL"
  }
  ```
- **Response:**
  ```json
  {
    "id": 12705337,
    "account": {"id": 436982614},
    "accountingPeriod": {"id": 23731256},
    "voucher": null,
    "transactions": [],
    "isClosed": false,
    "type": "MANUAL",
    "bankAccountClosingBalanceCurrency": 0,
    "closedDate": null,
    "approvable": false
  }
  ```

### GET /bank/reconciliation/match
- **Status:** 200 OK (empty)

### GET /bank/reconciliation/paymentType
- **Status:** 200 OK (4 types, see above)

### GET /bank/statement
- **Status:** 200 OK (empty in sandbox)

### GET /bank
- **Status:** 200 OK
- **Full result size:** 6 banks
- **Example:** Aasen Sparebank, with `bankStatementFileFormatSupport`, `registerNumbers`, `autoPaySupport`

---

## 4. Module Management

### GET /company/modules
- **Status:** 200 OK
- **Enabled modules (true):**
  - moduleprojecteconomy, moduleemployee, moduleContact, modulecustomer
  - moduledepartment, moduleprojectcategory, moduleinvoice, moduleCurrency
  - moduleProjectBudget, moduleProduct, moduleWageProjectAccounting
  - moduleProjectAccounting, moduleVacationBalance, moduleHolydayPlan
  - moduleproject
- **Disabled modules (false):**
  - ocr, autoPayOcr, remit, agro, mamut, approveVoucher
  - modulenrf, moduleelectro, moduleRackbeat, moduleOrderOut
  - moduleQuantityHandling, completeMonthlyHourLists
  - **moduleDepartmentAccounting** — disabled
  - moduleProductAccounting, moduleAccountantConnectClient
  - moduleMultipleLedgers, moduleFixedAssetRegister
  - moduleDigitalSignature, moduleLogistics, moduleLogisticsLight

### PUT /company/modules — FAILED (405 Method Not Allowed)
- Cannot enable/disable modules via API in sandbox

---

## 5. Company Info

### GET /company — 400 (needs ID, no list endpoint)
### GET /company/{id} — 404 (company ID not discoverable via this path)

---

## 6. Activity / Timesheet

### GET /activity
- **Status:** 200 OK
- **Full result size:** 4 activities
- **Activities found:**
  - 5685468: "Administrasjon" (GENERAL_ACTIVITY)
  - 5685469: (another activity)
- **Response structure:**
  ```json
  {
    "id": 5685468,
    "name": "Administrasjon",
    "activityType": "GENERAL_ACTIVITY",
    "isProjectActivity": false,
    "isGeneral": true,
    "isChargeable": false,
    "rate": 0.0
  }
  ```

### POST /timesheet/entry — Create Timesheet Entry (Tier 2)
- **Status:** 200 OK (SUCCESS!)
- **Required fields:**
  - `employee.id`
  - `activity.id`
  - `date` (YYYY-MM-DD)
  - `hours` (decimal)
- **Optional:** `comment`, `project.id`
- **Example request:**
  ```json
  {
    "employee": {"id": 18491802},
    "activity": {"id": 5685468},
    "date": "2026-03-20",
    "hours": 2.5,
    "comment": "API test timesheet entry"
  }
  ```
- **Response:** Full entry with id, chargeable hours, locked status, etc.

### GET /timesheet/entry?dateFrom=...&dateTo=...
- **Status:** 200 OK

### GET /timesheet/timeClock
- **Status:** 200 OK (empty)

### GET /timesheet/settings
- **Status:** 200 OK
- **Response:** `{timeClock: false, timesheetCompleted: true, flexBalance: true, vacationBalance: true}`

### GET /timesheet/salaryTypeSpecification
- **Status:** 200 OK (empty)

### GET /timesheet/week
- **Status:** 422 — requires employeeId + weekYear, or id + approvedBy

---

## 7. Salary Endpoints

### GET /salary/type
- **Status:** 200 OK
- **Full result size:** 6 salary types
- **Example:** id=72779379, number "1000", name "Gjeld til ansatte"
- **Response structure:**
  ```json
  {
    "id": 72779379,
    "number": "1000",
    "name": "Gjeld til ansatte",
    "showInTimesheet": false,
    "isSickPayable": false,
    "isVacationPayable": false,
    "isTaxable": false,
    "accountNumberDebit": {"id": 436982711},
    "accountNumberCredit": null
  }
  ```

### POST /salary/payslip — 403 FORBIDDEN
- No permission to create payslips in sandbox

### GET /salary/payslip — 200 OK (with employeeId, yearFrom, monthFrom, yearTo, monthTo)
- Returns empty for sandbox

### GET /salary/settings
- **Status:** 200 OK
- **Response:** `{municipality: {id: 262}, payrollTaxCalcMethod: "AA"}`

### GET /salary/compilation?employeeId=...
- **Status:** 200 OK
- **Response:** Employee salary compilation with wages, expenses, tax deductions arrays

### GET /salary/transaction — 403 FORBIDDEN
### GET /salary/specification — 403 FORBIDDEN

---

## 8. Travel Expense

### GET /travelExpense
- **Status:** 200 OK
- **Full result size:** 1
- **Response includes:** costs, perDiemCompensations, mileageAllowances, accommodationAllowances, amount, payment details

### GET /travelExpense/rateCategory
- **Status:** 200 OK
- **Full result size:** 6 rate categories
- **Example:** "Dagsreise 5-9 timer - innland" (id=2)

### GET /travelExpense/costCategory
- **Status:** 200 OK
- **Full result size:** 6 cost categories
- **Example:** "Bredbånd" (account: 436982907)

### GET /travelExpense/rate — 422 (result set too large, >10000)
### GET /travelExpense/mileageAllowance — 200 OK (empty)
### GET /travelExpense/accommodationAllowance — 200 OK (empty)
### GET /travelExpense/perDiemCompensation — 200 OK (empty)

---

## 9. Employee Endpoints (Extended)

### GET /employee
- **Status:** 200 OK
- **Full result size:** 3 employees
- **Key employee:** id=18491802, "Frikk a23fd25c"

### GET /employee/employment
- **Status:** 200 OK (1 employment record)
- **Response includes:** startDate, endDate, division, employmentId

### GET /employee/employment/details
- **Status:** 200 OK (1 record)

### GET /employee/employment/employmentType
- **Status:** 200 OK (4 types)
- **Values:** "Ordinært arbeidsforhold" (id=1), etc.

### GET /employee/employment/remunerationType
- **Status:** 200 OK (5 types)
- **Values:** "Fastlønn" (id=100), etc.

### GET /employee/employment/workingHoursScheme
- **Status:** 200 OK (6 schemes)
- **Values:** "Ikke skiftarbeid" (id=50), etc.

### GET /employee/employment/leaveOfAbsence — 200 OK (empty)
### GET /employee/employment/leaveOfAbsenceType — 200 OK (6 types: "Permisjon" id=800, etc.)
### GET /employee/employment/occupationCode — 200 OK (6+ codes)
### GET /employee/category — 200 OK (empty)
### GET /employee/nextOfKin — 200 OK (empty)
### GET /employee/hourlyCostAndRate — 200 OK (empty)
### GET /employee/standardTime — 200 OK (empty)
### GET /employee/preferences — 200 OK (filter settings, language)

---

## 10. Project Endpoints

### POST /project — Create Project (Tier 2)
- **Status:** 200 OK (SUCCESS!)
- **Required fields:** `name`, `number`, `projectManager.id`, `startDate`
- **Response includes:** isClosed, isReadyForInvoicing, isInternal, isOffer, isFixedPrice, etc.

### GET /project
- **Status:** 200 OK

### GET /project/category — 200 OK (empty)

### GET /project/hourlyRates
- **Status:** 200 OK (2 records)

---

## 11. Supplier Endpoints

### POST /supplier — Create Supplier (Tier 2)
- **Status:** 200 OK (SUCCESS!)
- **Required:** `name`
- **Optional:** `email`, `supplierNumber`, `organizationNumber`
- **Response includes:** isSupplier, isCustomer, isInactive, showProducts, etc.

### GET /supplier — 200 OK

### POST /supplierInvoice — 500 Internal Server Error
- **Attempted fields:** supplier.id, invoiceNumber, invoiceDate, amount, currency.id
- Server error; likely needs more fields or voucher attachment

### GET /supplierInvoice?invoiceDateFrom=...&invoiceDateTo=... — 200 OK (empty)

---

## 12. Other Endpoints Tested

### GET /customer — 200 OK (2 customers)
### GET /product — 200 OK (2 products)
### GET /product/unit — 200 OK (6 units: Liter, etc.)
### GET /product/external — 422 (needs Wholesaler)
### GET /order?orderDateFrom=...&orderDateTo=... — 200 OK (requires date params)
### GET /invoice?invoiceDateFrom=...&invoiceDateTo=... — 200 OK (requires date params)
### GET /invoice/details?invoiceDateFrom=...&invoiceDateTo=... — 200 OK
### GET /department — 200 OK (2 departments)
### GET /currency — 200 OK (6 currencies: NOK, SEK, DKK, EUR, GBP, USD)
### GET /country — 200 OK (many countries)
### GET /municipality — 200 OK (many municipalities)
### GET /contact — 200 OK (empty)
### GET /address — 200 OK (5 addresses)
### GET /deliveryAddress — 200 OK (empty)
### GET /purchaseOrder — 200 OK (empty)
### GET /balanceSheet?dateFrom=...&dateTo=... — 200 OK (empty)
### GET /reminder?dateFrom=...&dateTo=... — 200 OK (empty)
### GET /event — 200 OK (full webhook event catalog)
### GET /event/subscription — 200 OK (empty)

---

## 13. Endpoints NOT Found (404)

| Endpoint | Status |
|---|---|
| GET /ledger/postingCategory | 404 |
| GET /payment/paymentType | 404 |
| GET /payment | 404 |
| GET /inventories | 404 |
| GET /companyHoliday | 404 |
| GET /document | 404 |
| GET /resultBudget | 404 |
| GET /token/session | 404 |
| GET /timesheet/month | 404 |
| GET /ledger/annual | 404 |
| GET /swagger.json | 404 |

---

## 14. Permission Denied (403)

| Endpoint | Note |
|---|---|
| POST /salary/payslip | No permission in sandbox |
| GET /salary/transaction | No permission |
| GET /salary/specification | No permission |

---

## 15. Method Not Allowed (405 → 400)

| Endpoint | Note |
|---|---|
| PUT /company/modules | Cannot modify modules via API |
| GET /company (no ID) | Needs specific ID |
| GET /order/orderline | Method not allowed on collection |
| GET /token/session/whoAmI | Method not allowed |

---

## 16. Successful POST Operations Summary

| Endpoint | Required Fields | Notes |
|---|---|---|
| POST /ledger/voucher | date, description, postings[] (each: date, description, account.id, employee.id, amountGross, amountGrossCurrency, currency.id, row) | Postings must balance, row >= 1, employee required |
| POST /timesheet/entry | employee.id, activity.id, date, hours | Optional: comment, project.id |
| POST /supplier | name | Optional: email, supplierNumber |
| POST /project | name, number, projectManager.id, startDate | Returns full project object |
| POST /bank/reconciliation | account.id, accountingPeriod.id, type ("MANUAL") | Creates reconciliation shell |

---

## 17. Event Types (Webhook Subscriptions)

Available events for `POST /event/subscription`:
- invoice.charged, order.create/update/delete
- customer.create/update/delete, supplier.create/update/delete
- product.create/update/delete, employee.create/update/delete
- contact.create/update/delete, account.create/update/delete
- project.create/update/delete, voucher.create/update/delete
- archiverelation.create/update/delete (BETA)
- notification.sent, voucherstatus.ready
- vatpaymentstatus.update, vatdeliverystatus.create/update/delete
- tripletexcustomer.update, expiredcompany.deleted

---

## 18. Key IDs in Sandbox

| Entity | ID | Description |
|---|---|---|
| Employee | 18491802 | Frikk a23fd25c |
| Account 1920 | 436982614 | Bankinnskudd (bank account) |
| Account (salary) | 436982711 | Gjeld til ansatte |
| Activity | 5685468 | Administrasjon |
| Department | 864717 | Avdeling |
| Department | 865127 | Hovedavdeling |
| Customer | 108168219 | Testbedrift AS |
| Supplier (created) | 108169099 | API Test Supplier AS |
| Currency NOK | 1 | Norge |
| Accounting Period Jan | 23731256 | 2026-01-01 to 2026-02-01 |
| Annual Account | 1991417 | Year 2026 |
| Voucher (created) | 608818357 | API Test Voucher |
| Timesheet Entry (created) | 175904059 | 2.5h Administrasjon |
| Project (created) | 401950691 | API Test Project |
| Bank Reconciliation (created) | 12705337 | Manual, Jan period |
