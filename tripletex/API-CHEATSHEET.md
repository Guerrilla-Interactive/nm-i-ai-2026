# Tripletex API Cheatsheet

Base: `{base_url}/v2` | Auth: Basic `0:{session_token}` | Refs: `{"id": N}` format

---

## SETUP — Bank Account (required before invoicing)
GET /ledger/account?isBankAccount=true → find account 1920 id+version
PUT /ledger/account/{id} {"id":N,"version":V,"number":1920,"name":"Bankinnskudd","bankAccountNumber":"12345678903","isBankAccount":true}
Without this: "Faktura kan ikke opprettes før selskapet har registrert et bankkontonummer."

## Create Employee
POST /employee {"firstName":"X","lastName":"Y","email":"x@y.com","userType":"STANDARD","department":{"id":N}}
Valid userType: STANDARD, EXTENDED (both get 4 entitlements), NO_ACCESS (0 entitlements). Others → 422.
email is IMMUTABLE after creation. userType is write-only (always null in GET).

## Update Employee
GET /employee?firstName=X → get id, version, email
PUT /employee/{id} — must include: id, version, firstName, lastName, email (unchanged!), dateOfBirth
Can change: phone numbers, comments, department, address, isContact, dateOfBirth
Cannot change: email (422), allowInformationRegistration (ignored)
Wrong version → 409 Conflict. Missing dateOfBirth → 422.
Address update must include address.id or you get 422.

## Delete Employee
DELETE /employee/{id} → 403 Forbidden (not available in sandbox)

## Employee Search Params
GET /employee?firstName=X — exact match ✅
GET /employee?email=x@y.com — exact match ✅
GET /employee?includeContacts=true — includes isContact=true employees ✅
NOT working: lastName, departmentId, id, name, employeeNumber

## Create Customer
POST /customer {"name":"X"}
Only name required. Gets auto customerNumber, 14-day invoice terms.

## Update Customer
GET /customer?name=X → id, version
PUT /customer/{id} — include id + version + fields to update

## Create Product
POST /product {"name":"X"}
Only name required. Price defaults 0. vatType defaults id=6 (0%).
Name must be unique (422 if duplicate). vatType id=3 (25%) REJECTED for products.
Optional: number, description, priceExcludingVatCurrency, currency

## Create Department
POST /department {"name":"X","departmentNumber":N}
Sandbox departments: 864717 (Avdeling), 865127 (Hovedavdeling)

## Create Project
POST /project {"name":"X","projectManager":{"id":N},"startDate":"YYYY-MM-DD"}
All 3 required. Use projectManager (object), NOT projectManagerId (→ 422).
Number auto-increments. Optional: endDate, customer, department, description

## Create Order
POST /order {"customer":{"id":N},"orderDate":"YYYY-MM-DD","deliveryDate":"YYYY-MM-DD"}
deliveryDate required (422 if missing). orderLines optional (add inline or separately).

## Add Order Lines
POST /order/orderline {"order":{"id":N},"product":{"id":N},"count":1,"unitPriceExcludingVatCurrency":100}
Without product: {"order":{"id":N},"description":"Free text","count":1,"unitPriceExcludingVatCurrency":250}
Required: order.id, count, unitPriceExcludingVatCurrency

## Create Invoice (from Order) — RECOMMENDED
PUT /order/{id}/:invoice?invoiceDate=YYYY-MM-DD&sendToCustomer=false
Order must have lines. Returns full invoice with invoiceNumber, amounts, voucher.

## Create Invoice (alternative)
POST /invoice {"invoiceDate":"YYYY-MM-DD","invoiceDueDate":"YYYY-MM-DD","orders":[{"id":N}]}
sendToCustomer NOT valid in body (→ 422). orders array required & non-empty.

## Full Invoice Flow (minimum calls)
1. POST /order (with customer + dates + inline orderLines) → order_id
2. PUT /order/{order_id}/:invoice?invoiceDate=YYYY-MM-DD&sendToCustomer=false → invoice

## List Invoices
GET /invoice?invoiceDateFrom=YYYY-MM-DD&invoiceDateTo=YYYY-MM-DD
Both date params REQUIRED (422 if missing).

## Register Payment on Invoice
PUT /invoice/{id}/:payment?paymentDate=YYYY-MM-DD&paymentTypeId=33998616&paidAmount=N
paymentTypeId must be INCOMING type. Sandbox incoming IDs: 33998616–33998619 (33998616 = "Kontant").
Outgoing types (33998620–33998623) → "Den angitte betalingstypen må være en innbetaling."
GET /invoice/paymentType → lists incoming payment types (id, description).

## Create Credit Note
PUT /invoice/{id}/:createCreditNote?date=YYYY-MM-DD&comment=X&sendToCustomer=false
Creates new invoice with negative amount, isCreditNote=true. Original gets isCredited=true.

## Create Travel Expense
POST /travelExpense {"employee":{"id":N},"title":"X"}
date optional (defaults today). State starts OPEN.

## Add Cost to Travel Expense
POST /travelExpense/cost {"travelExpense":{"id":N},"paymentType":{"id":33998575},"amountCurrencyIncVat":150}
paymentType 33998575 = "Privat utlegg" (only one in sandbox).
Optional: date, costCategory, currency, rate. No "count" field!
Response is minimal (just URL) — GET /travelExpense/cost/{id}?fields=* for full data.

## Delete Travel Expense
DELETE /travelExpense/{id} → 204 No Content. Must be in OPEN state.

## Create Supplier
POST /supplier {"name":"X"}
Optional: email, supplierNumber, organizationNumber

## Create Timesheet Entry
POST /timesheet/entry {"employee":{"id":N},"activity":{"id":N},"date":"YYYY-MM-DD","hours":2.5}
Optional: comment, project.id
GET /activity → list activities (e.g., 5685468 = "Administrasjon")

## Create Voucher (Journal Entry)
POST /ledger/voucher {"date":"YYYY-MM-DD","description":"X","postings":[
  {"date":"YYYY-MM-DD","description":"Debit","account":{"id":N},"employee":{"id":N},"amountGross":1000,"amountGrossCurrency":1000,"currency":{"id":1},"row":1},
  {"date":"YYYY-MM-DD","description":"Credit","account":{"id":N},"employee":{"id":N},"amountGross":-1000,"amountGrossCurrency":-1000,"currency":{"id":1},"row":2}
]}
Postings must balance. row >= 1 (row 0 is system). employee.id required on each posting.

## Create Bank Reconciliation
POST /bank/reconciliation {"account":{"id":N},"accountingPeriod":{"id":N},"type":"MANUAL"}
GET /ledger/accountingPeriod → list periods (id, start, end, isClosed)

## Employee Entitlements
GET /employee/entitlement?employeeId=N
POST /employee/entitlement {"employee":{"id":N},"entitlementId":46,"customer":{"id":COMPANY_ID}}
Entitlements: 46=AUTH_HOURLIST, 47=AUTH_TRAVELREPORT, 61=AUTH_EMPLOYEE_INFO, 92=AUTH_PROJECT_INFO

---

## VAT Types
| id | % | Name |
|----|---|------|
| 0 | 0% | No VAT treatment |
| 1 | 25% | Incoming VAT, high rate |
| 3 | 25% | Outgoing VAT, high rate |
| 5 | 0% | No outgoing (within MVA law) |
| 6 | 0% | No outgoing (outside MVA law) — **default for products** |
| 7 | 0% | No VAT treatment (income) |
| 11 | 15% | Incoming, medium rate |
| 12 | 12% | Incoming, low rate |
| 31 | 15% | Outgoing, medium rate |
| 32 | 12% | Outgoing, low rate |

## Currencies
1=NOK, 2=SEK, 3=DKK, 4=USD, 5=EUR, 6=GBP, 7=CHF

## Dependency Chains
```
Bank account 1920 setup → required before any invoicing
Customer → Order → Invoice → Payment / Credit Note
Employee → Project (as projectManager)
Employee → Travel Expense → Travel Expense Cost
Employee → Timesheet Entry (+ Activity)
Ledger Accounts → Voucher postings
```

## Key Gotchas
1. References are objects: `{"id":N}` not just `N`
2. Email immutable on employees after creation
3. PUT requires version field (optimistic locking)
4. Product names must be unique
5. vatType id=3 invalid for product creation (use id=6)
6. Invoice requires order — cannot skip order step
7. GET /invoice requires both date range params
8. sendToCustomer is query param on PUT :invoice, NOT valid in POST /invoice body
9. Travel expense cost has no "count" field
10. DELETE employee → 403 (not permitted)
11. Incoming payment type IDs ≠ outgoing payment type IDs
12. GET /employee filters: only firstName, email work — lastName/departmentId/id don't filter
