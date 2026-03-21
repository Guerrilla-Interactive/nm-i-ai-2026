# SMB Owner Workflows — Tripletex API Research

Research date: 2026-03-21
Sandbox: `https://kkpqfuj-amager.tripletex.dev/v2`

---

## 1. User Persona: Small Business Owner / Daglig Leder

**Who they are:**
- Norwegian small business owner (daglig leder / styreleder / enkeltpersonforetak)
- Runs a company with 1–50 employees
- Uses Tripletex for invoicing, customer management, payroll, and basic bookkeeping
- May not have a dedicated accountant — handles many tasks themselves
- Often works in Norwegian (bokmål), sometimes English

**Primary workflows (by frequency):**
1. **Invoicing** — Create invoices, track payments, send reminders (daily/weekly)
2. **Customer management** — Add/find/update customers (weekly)
3. **Product/service catalog** — Maintain price lists (monthly)
4. **Payment tracking** — Register incoming payments, handle credit notes (weekly)
5. **Supplier invoices** — Register incoming bills (weekly)
6. **Payroll** — Run monthly salary payments (monthly)
7. **Year-end** — Annual closing, bank reconciliation (annually)

**Language patterns:**
- Primarily Norwegian bokmål, with ASCII-folded variants (ø→o, å→a, æ→ae)
- May use informal/conversational Norwegian: "Lag en faktura" vs formal "Opprett faktura"
- Mix Norwegian and English terms: "customer" vs "kunde", "invoice" vs "faktura"
- Abbreviations: "stk" (stykk/each), "kr" (kroner), "mva" (merverdiavgift/VAT)

---

## 2. API Endpoints (Full Details)

### 2.1 Customer (`/customer`)

**GET /customer** — Search/list customers
| Parameter | Type | Works? | Notes |
|-----------|------|--------|-------|
| `name` | string | YES | Substring match |
| `organizationNumber` | string | YES | Exact match |
| `email` | string | YES | Exact match |
| `customerAccountNumber` | int | YES | By customer number |
| `isInactive` | bool | YES | Filter active/inactive |
| `from`, `count` | int | YES | Pagination |
| `fields` | string | YES | Field selection (e.g., `*`) |

**POST /customer** — Create customer
```json
{
  "name": "Firma AS",              // REQUIRED — only required field
  "organizationNumber": "999888777",
  "email": "post@firma.no",
  "invoiceEmail": "faktura@firma.no",
  "phoneNumber": "22334455",
  "isPrivateIndividual": false,
  "language": "NO",
  "invoiceSendMethod": "EMAIL",     // EMAIL, EHF, EFAKTURA, PAPER, MANUAL
  "invoicesDueIn": 14,
  "invoicesDueInType": "DAYS",      // DAYS, MONTHS
  "postalAddress": {"addressLine1": "Storgata 1", "postalCode": "0001", "city": "Oslo"},
  "discountPercentage": 0.0,
  "website": "https://firma.no"
}
```

**Response fields of note:**
- `id`, `version` — needed for updates
- `customerNumber` — auto-assigned (10001, 10002, ...)
- `displayName` — "{name} ({customerNumber})"
- `currency` — defaults to `{"id": 1}` (NOK)
- `ledgerAccount` — auto-assigned (account 1500 — Kundefordringer)
- `isAutomaticSoftReminderEnabled`, `isAutomaticReminderEnabled` — reminder settings
- `bankAccountPresentation` — array (empty by default)

**PUT /customer/{id}** — Update customer (requires `id` + `version`)

**DELETE /customer/{id}** — Delete customer

**Sandbox state:** 51 customers exist (10001–10050+)

### 2.2 Product (`/product`)

**GET /product** — List/search products
| Parameter | Type | Notes |
|-----------|------|-------|
| `name` | string | Substring match |
| `number` | string | Product number |
| `isInactive` | bool | Filter |

**POST /product** — Create product
```json
{
  "name": "Widget",                          // REQUIRED — must be unique
  "number": "PROD-001",                      // Optional, auto if blank
  "description": "En fin widget",
  "priceExcludingVatCurrency": 500.0,        // Price ex. VAT
  "priceIncludingVatCurrency": 625.0,        // Price inc. VAT (25%)
  "costExcludingVatCurrency": 200.0,         // Cost price
  "vatType": {"id": 3},                      // 3 = 25% outgoing VAT
  "currency": {"id": 1},                     // NOK
  "productUnit": {"id": 3721733}             // "Stykk" (each)
}
```

**IMPORTANT GOTCHA:** `vatType` id=3 (25% outgoing) is REJECTED for product creation in sandbox! Use id=6 (0% — outside MVA law) which is the default. The VAT is applied at the order line level instead.

**Product Units (from /product/unit):**
| ID | Name | Short | CommonCode |
|----|------|-------|------------|
| 3721728 | Liter | l | LTR |
| 3721729 | Meter | m | MTR |
| 3721730 | Kilometer | km | KMT |
| 3721731 | Gram | g | GRM |
| 3721732 | Kilogram | kg | KGM |
| 3721733 | Stykk | stk | EA |

**Sandbox state:** 32 products exist

### 2.3 Order (`/order`)

**GET /order** — List orders (requires `orderDateFrom` + `orderDateTo`)

**POST /order** — Create order
```json
{
  "customer": {"id": 108168567},
  "orderDate": "2026-03-21",
  "deliveryDate": "2026-03-28",     // REQUIRED (422 if missing)
  "invoiceComment": "Ref: PO-123",
  "currency": {"id": 1},
  "orderLines": [                    // Can include inline
    {
      "product": {"id": 84382010},
      "count": 3,
      "unitPriceExcludingVatCurrency": 500.0,
      "description": "Custom widget"
    }
  ]
}
```

**Order Lines (`/order/orderline`):**
```json
{
  "order": {"id": 401950669},
  "product": {"id": 84382010},       // Optional — can use free text instead
  "description": "Free text line",    // Used if no product
  "count": 2.0,
  "unitPriceExcludingVatCurrency": 100.0,
  "discount": 10.0,                  // Percentage discount
  "vatType": {"id": 3}               // Override product VAT
}
```

**Sandbox state:** 4 orders exist

### 2.4 Invoice (`/invoice`)

**GET /invoice** — List invoices (REQUIRES `invoiceDateFrom` + `invoiceDateTo`)
| Parameter | Type | Notes |
|-----------|------|-------|
| `invoiceDateFrom` | date | REQUIRED |
| `invoiceDateTo` | date | REQUIRED |
| `invoiceNumber` | string | Filter by number |
| `customerId` | int | Filter by customer |
| `customerName` | string | Filter by customer name |

**Creating invoices — TWO methods:**

**Method A (recommended): Order → Invoice**
```
1. POST /order          → order_id
2. PUT /order/{id}/:invoice?invoiceDate=2026-03-21&sendToCustomer=false
```

**Method B (alternative):**
```
POST /invoice {"invoiceDate":"2026-03-21","invoiceDueDate":"2026-04-04","orders":[{"id":N}]}
```
Note: `sendToCustomer` is a QUERY PARAM on PUT, NOT valid in POST body (→ 422)

**Invoice response fields:**
- `invoiceNumber` — auto-assigned (1, 2, 3, ...)
- `amount` / `amountCurrency` — total including VAT
- `amountExcludingVat` / `amountExcludingVatCurrency`
- `amountOutstanding` / `amountCurrencyOutstanding` — remaining balance
- `isCreditNote` — true if this is a credit note
- `isCredited` — true if a credit note exists for this invoice
- `creditedInvoice` — ID of the original invoice (for credit notes)
- `voucher` — linked accounting voucher
- `orders` — linked order(s)
- `orderLines` — the line items
- `reminders` — array of reminders sent
- `isCharged`, `isApproved` — status flags
- `documentId` — PDF document ID

**Sandbox state:** 4 invoices exist (including 1 credit note)

### 2.5 Payment Types (`/invoice/paymentType`)

**Incoming payment types (for customer invoices):**
| ID | Description | Debit Account |
|----|-------------|---------------|
| 33998616 | Kontant (Cash) | 436982611 (1900 Kasse) |
| 33998617 | Betalt til bank (Bank transfer) | 436982614 (1920 Bankinnskudd) |

Only 2 incoming payment types in sandbox. "Kontant" is the default used by the executor.

**IMPORTANT:** Outgoing payment types (33998620–33998623) are for SUPPLIER payments. Using them for customer invoice payments → "Den angitte betalingstypen må være en innbetaling."

### 2.6 Currency (`/currency`)

| ID | Code | Description |
|----|------|-------------|
| 1 | NOK | Norge |
| 2 | SEK | Sverige |
| 3 | DKK | Danmark |
| 4 | USD | USA |
| 5 | EUR | EU |
| 6 | GBP | Storbritannia |
| 7 | CHF | Sveits |
| 8 | JPY | Japan |
| 9 | AUD | Australia |
| 10 | BHD | Bahrain |
| ... | ... | (11 total) |

### 2.7 VAT Types (`/ledger/vatType`)

**Most relevant for SMB invoicing:**
| ID | % | Name (Norwegian) | Use |
|----|---|-------------------|-----|
| 3 | 25% | Utgående avgift, høy sats | Standard outgoing VAT (services, goods) |
| 31 | 15% | Utgående avgift, middels sats | Food/beverages |
| 32 | 12% | Utgående avgift, lav sats | Transport, cinema, hotels |
| 5 | 0% | Ingen utgående avgift (innenfor mva-loven) | VAT-exempt within MVA law |
| 6 | 0% | Ingen utgående avgift (utenfor mva-loven) | Outside MVA law (default for products) |
| 7 | 0% | Ingen avgiftsbehandling (inntekter) | No VAT treatment (income) |

**For incoming/supplier invoices:**
| ID | % | Use |
|----|---|-----|
| 1 | 25% | Incoming VAT deduction, high rate |
| 11 | 15% | Incoming VAT deduction, medium rate |
| 12 | 12% | Incoming VAT deduction, low rate |

### 2.8 Supplier (`/supplier`)

**GET /supplier** — List/search suppliers
**POST /supplier** — Create supplier (only `name` required)

```json
{
  "name": "Leverandør AS",
  "organizationNumber": "987654321",
  "email": "post@leverandor.no",
  "supplierNumber": 50010
}
```

**Sandbox state:** 5 suppliers exist (50005–50009)

### 2.9 Supplier Invoice (`/supplierInvoice`)

**POST /supplierInvoice** — Register incoming invoice
```json
{
  "invoiceNumber": "INV-2026-001",
  "invoiceDate": "2026-03-15",
  "dueDate": "2026-04-15",
  "supplier": {"id": 108269521},
  "amount": 10000.0,
  "description": "Kontorrekvisita"
}
```

### 2.10 Delivery Address (`/deliveryAddress`)

**Sandbox state:** Empty (0 delivery addresses)

### 2.11 Reminder (`/reminder`)

**GET /reminder** — List reminders (requires `dateFrom` + `dateTo`)
**Sandbox state:** 0 reminders

---

## 3. Invoice Workflow (Complete Step-by-Step)

### 3.1 Full Invoice Creation Flow

```
Step 1: Find or create customer
  GET /customer?name=Firma+AS → check if exists
  If not found: POST /customer {"name":"Firma AS", ...}

Step 2: Ensure bank account is configured
  GET /ledger/account?isBankAccount=true → find account 1920
  PUT /ledger/account/{id} with bankAccountNumber if missing
  (Without this: "Faktura kan ikke opprettes før selskapet har registrert et bankkontonummer.")

Step 3: Create or find products (optional — can use free text lines)
  POST /product {"name":"Widget","priceExcludingVatCurrency":500}
  OR use existing product ID from GET /product?name=Widget

Step 4: Create order with order lines
  POST /order {
    "customer": {"id": CUST_ID},
    "orderDate": "2026-03-21",
    "deliveryDate": "2026-03-28",
    "orderLines": [
      {"product":{"id":PROD_ID},"count":3,"unitPriceExcludingVatCurrency":500},
      {"description":"Tilleggstjeneste","count":1,"unitPriceExcludingVatCurrency":250}
    ]
  }

Step 5: Convert order to invoice
  PUT /order/{ORDER_ID}/:invoice?invoiceDate=2026-03-21&sendToCustomer=false
  → Returns complete invoice with invoiceNumber, amounts, voucher
```

**Total API calls:** 3–5 (find customer + bank check + order + invoice, optionally create customer/product)

### 3.2 Invoice for Existing Customer (Shortcut)

```
Step 1: GET /customer?name=Ola+Nordmann → customer_id
Step 2: POST /order with customer.id + inline orderLines
Step 3: PUT /order/{id}/:invoice?invoiceDate=...&sendToCustomer=false
```

### 3.3 Invoice with Immediate Payment

```
Steps 1-5: Same as full flow above
Step 6: GET /invoice/paymentType → get payment type ID (33998616 = Kontant)
Step 7: PUT /invoice/{INV_ID}/:payment?paymentDate=2026-03-21&paymentTypeId=33998616&paidAmount=1500
```

---

## 4. Payment Workflow

### 4.1 Register Payment on Existing Invoice

```
Step 1: Find the invoice
  GET /invoice?invoiceNumber=1&invoiceDateFrom=2000-01-01&invoiceDateTo=2099-12-31
  OR: GET /invoice?customerId=ID&invoiceDateFrom=...&invoiceDateTo=...

Step 2: Check outstanding amount
  invoice.amountOutstanding → remaining balance

Step 3: Get payment type
  GET /invoice/paymentType → [{id:33998616, description:"Kontant"}, ...]

Step 4: Register payment
  PUT /invoice/{id}/:payment?paymentDate=2026-03-21&paymentTypeId=33998616&paidAmount=1500.00
```

**Important notes:**
- `paidAmount` must match or be ≤ `amountOutstanding` — otherwise "ugyldig beløp"
- Current executor auto-adjusts amount to match outstanding if they differ
- Partial payments are supported (amount < outstanding)
- Only INCOMING payment type IDs work (33998616–33998617 in sandbox)

### 4.2 Reverse Payment (Bounced/Returned)

Used when a bank payment is returned/bounced:
- Find the invoice with the payment
- The executor creates a reversal voucher to reopen the invoice as outstanding
- Task type: `REVERSE_PAYMENT`

---

## 5. Credit Note Workflow

### 5.1 Create Credit Note for Existing Invoice

```
Step 1: Find the original invoice
  GET /invoice?invoiceNumber=2&invoiceDateFrom=2000-01-01&invoiceDateTo=2099-12-31

Step 2: Create credit note
  PUT /invoice/{id}/:createCreditNote?date=2026-03-21&comment=Feilregistrering&sendToCustomer=false
```

**Result:**
- Original invoice gets `isCredited: true`
- New invoice created with:
  - `isCreditNote: true`
  - `creditedInvoice: {original_invoice_id}`
  - Negative amounts (e.g., `-250.0`)
  - Same order lines as original but with negative values

**Sandbox evidence:** Invoice #2 (amount=250) was credited → Invoice #3 (amount=-250, isCreditNote=true)

### 5.2 Partial Credit Notes

The API creates a full credit note (negating the entire invoice). For partial refunds, the typical workflow is:
1. Credit note the entire original invoice
2. Create a new invoice for the remaining amount

---

## 6. Prompt Patterns (Norwegian + English)

### 6.1 Invoice Creation

| Norwegian | English | TaskType |
|-----------|---------|----------|
| "Lag faktura til Ola Nordmann for 3 stk Widget à 500kr" | "Create invoice for Ola Nordmann: 3x Widget at 500kr" | CREATE_INVOICE |
| "Fakturer kunde Firma AS for konsulenttimer" | "Invoice customer Firma AS for consulting hours" | CREATE_INVOICE / INVOICE_EXISTING_CUSTOMER |
| "Send faktura til Bergen Consulting for 10 timer rådgivning à 1500kr" | "Send invoice to Bergen Consulting for 10 hours consulting at 1500kr" | INVOICE_EXISTING_CUSTOMER |
| "Lag faktura med betaling for Nordmann Handel" | "Create invoice with payment for Nordmann Handel" | INVOICE_WITH_PAYMENT |

### 6.2 Customer Management

| Norwegian | English | TaskType |
|-----------|---------|----------|
| "Opprett ny kunde: Firma AS, org.nr 999888777" | "Create new customer: Firma AS, org number 999888777" | CREATE_CUSTOMER |
| "Registrer kunde Ola Nordmann, e-post ola@example.no" | "Register customer Ola Nordmann, email ola@example.no" | CREATE_CUSTOMER |
| "Finn alle kunder med navn 'Hansen'" | "Find all customers named 'Hansen'" | FIND_CUSTOMER |
| "Oppdater e-posten til Testbedrift AS" | "Update the email for Testbedrift AS" | UPDATE_CUSTOMER |
| "Slett kunde Direct Test Corp" | "Delete customer Direct Test Corp" | DELETE_CUSTOMER |

### 6.3 Payment Registration

| Norwegian | English | TaskType |
|-----------|---------|----------|
| "Registrer betaling på faktura 10001" | "Register payment on invoice 10001" | REGISTER_PAYMENT |
| "Merk faktura 3 som betalt" | "Mark invoice 3 as paid" | REGISTER_PAYMENT |
| "Registrer innbetaling 5000 kr på faktura til Firma AS" | "Register payment of 5000 kr on invoice for Firma AS" | REGISTER_PAYMENT |

### 6.4 Credit Notes

| Norwegian | English | TaskType |
|-----------|---------|----------|
| "Opprett kreditnota for faktura 10001" | "Create credit note for invoice 10001" | CREATE_CREDIT_NOTE |
| "Krediter faktura nummer 2" | "Credit invoice number 2" | CREATE_CREDIT_NOTE |
| "Lag kreditnota - feil på faktura til Firma AS" | "Create credit note - error on invoice for Firma AS" | CREATE_CREDIT_NOTE |

### 6.5 Product Management

| Norwegian | English | TaskType |
|-----------|---------|----------|
| "Opprett produkt Widget til 500 kr" | "Create product Widget at 500 kr" | CREATE_PRODUCT |
| "Legg til ny tjeneste: Rådgivning, pris 1800 kr/time" | "Add new service: Consulting, price 1800 kr/hour" | CREATE_PRODUCT |
| "Endre prisen på Konsulenttime til 1600 kr" | "Change price of Konsulenttime to 1600 kr" | UPDATE_PRODUCT |
| "Slett produkt Test Product" | "Delete product Test Product" | DELETE_PRODUCT |

### 6.6 Supplier Management

| Norwegian | English | TaskType |
|-----------|---------|----------|
| "Registrer leverandør Acme AS, org.nr 987654321" | "Register supplier Acme AS, org number 987654321" | CREATE_SUPPLIER |
| "Registrer leverandørfaktura fra Acme AS på 10000 kr" | "Register supplier invoice from Acme AS for 10000 kr" | CREATE_SUPPLIER_INVOICE |
| "Finn leverandør med navn Staples" | "Find supplier named Staples" | FIND_SUPPLIER |

### 6.7 Common Norwegian Accounting Terms

| Norwegian | English | Context |
|-----------|---------|---------|
| faktura | invoice | Outgoing invoice to customer |
| leverandørfaktura | supplier invoice | Incoming invoice from supplier |
| inngående faktura | incoming invoice | Same as leverandørfaktura |
| kunde | customer | |
| leverandør | supplier | |
| produkt | product | |
| betaling / innbetaling | payment | |
| kreditnota | credit note | |
| purring | reminder | Payment reminder |
| ordre | order | Prerequisite for invoice |
| mva / merverdiavgift | VAT | Value Added Tax |
| stk / stykk | each/piece | Unit |
| kr / kroner | NOK | Currency |
| org.nr / organisasjonsnummer | organization number | Company ID |
| bilag / voucher | voucher | Accounting entry |
| regnskap | accounting | |
| årsavslutning | year-end closing | |
| bankavsteming | bank reconciliation | |
| lønn / lønnskjøring | payroll | |
| reiseregning | travel expense | |
| avdeling | department | |
| prosjekt | project | |
| timer / timeliste | hours / timesheet | |
| kontaktperson | contact person | |

---

## 7. Gap Analysis

### 7.1 Scenarios Our Agent CAN Handle (Confirmed Working)

| Scenario | TaskType | Status |
|----------|----------|--------|
| Create customer (basic) | CREATE_CUSTOMER | ✅ Working |
| Find customer by name | FIND_CUSTOMER | ✅ Working |
| Create product | CREATE_PRODUCT | ✅ Working |
| Create invoice (full flow) | CREATE_INVOICE | ✅ Working |
| Invoice existing customer | INVOICE_EXISTING_CUSTOMER | ✅ Working |
| Register payment | REGISTER_PAYMENT | ✅ Working |
| Create credit note | CREATE_CREDIT_NOTE | ✅ Working |
| Invoice + payment combo | INVOICE_WITH_PAYMENT | ✅ Working |
| Create supplier | CREATE_SUPPLIER | ✅ Working |
| Create supplier invoice | CREATE_SUPPLIER_INVOICE | ✅ Working |
| Update customer | UPDATE_CUSTOMER | ✅ Working |
| Delete customer | DELETE_CUSTOMER | ✅ Working |
| Run payroll | RUN_PAYROLL | ✅ Working |
| Bank reconciliation | BANK_RECONCILIATION | ✅ Working |
| Year-end closing | YEAR_END_CLOSING | ✅ Working |

### 7.2 Gaps and Limitations

#### 7.2.1 Missing Capabilities (No TaskType / Executor)

| Scenario | Impact | Notes |
|----------|--------|-------|
| **Partial credit notes** | Medium | API only supports full credit notes. No partial refund workflow. |
| **Invoice reminders (purring)** | Medium | `/reminder` endpoint exists but no task type or executor. SMB owners frequently need to send reminders. |
| **Multi-currency invoices** | Low | Customers default to NOK. Creating EUR/USD invoices is possible via order but not exposed in fields. |
| **Recurring invoices / subscriptions** | Medium | Order supports `isSubscription` but no task type handles subscription setup. |
| **Invoice PDF retrieval** | Low | `documentId` field exists on invoices but no download/view capability. |
| **Delivery address management** | Low | Endpoint exists, no executor. |
| **Product stock management** | Low | Products have `incomingStock`/`outgoingStock` but no inventory task type. |

#### 7.2.2 Classification Gaps (Recently Fixed)

| Prompt | Expected | Was | Fix Status |
|--------|----------|-----|------------|
| "Utfor arsavslutning for 2025" | YEAR_END_CLOSING | UNKNOWN | Fixed (ASCII variant) |
| "Kjor lonnskjoring for mars 2026" | RUN_PAYROLL | UNKNOWN | Fixed (ASCII variant) |
| "Aktiver modulen Prosjekt" | ENABLE_MODULE | CREATE_PROJECT | Fixed (regex + ordering) |
| "Registrer leverandorfaktura fra Acme AS" | CREATE_SUPPLIER_INVOICE | UNKNOWN | Fixed (ASCII variant) |

#### 7.2.3 Edge Cases in Current Implementation

| Issue | Detail |
|-------|--------|
| **VAT on products** | Products default to vatType=6 (0%). SMB owners expect 25% VAT on most products. The VAT is applied at order line level, but user might specify "inkl. mva" prices. |
| **Payment amount mismatch** | If user specifies a payment amount different from outstanding, executor auto-adjusts. User may want partial payment instead. |
| **Invoice search requires dates** | GET /invoice requires `invoiceDateFrom`+`invoiceDateTo`. Executor uses wide range (2000-2099) as workaround. |
| **Order date requirements** | POST /order requires `deliveryDate` even when irrelevant (e.g., services). |
| **Customer name uniqueness** | Multiple customers can have the same name (e.g., "Hamburg GmbH" appears 3 times in sandbox). Search by name may return wrong customer. |
| **Product name uniqueness** | Product names MUST be unique (422 if duplicate). |
| **Employee deletion** | DELETE /employee returns 403 in sandbox — not permitted. |
| **Bank account prerequisite** | Invoice creation fails without configured bank account on account 1920. |

### 7.3 Potential Tier 3 Prompt Patterns Not Yet Seen

```
"Lag bankavsteming for mars 2026"
"Korriger feil på bilag 608818352"
"Aktiver modul for reiseregning"
"Opprett dimensjon Kostsenter med verdier Oslo, Bergen, Trondheim"
"Årsavslutning for regnskapsåret 2025"
"Reverser betaling på faktura 1 — returnert av banken"
```

---

## 8. Recommendations

### 8.1 High Priority (Score Impact)

1. **Invoice reminder support** — Add `SEND_REMINDER` task type and executor using `/reminder` endpoint. Common SMB task.

2. **Partial payment support** — Allow user to specify a partial payment amount without auto-adjusting to outstanding. Add a `partial_payment` boolean field.

3. **Customer disambiguation** — When multiple customers match a name search, present options or use additional criteria (org number, email) to narrow down.

4. **VAT handling improvement** — When user says "500 kr inkl. mva", calculate price ex. VAT (400 kr at 25%). Add `price_including_vat` field handling in the invoice flow.

### 8.2 Medium Priority (Coverage)

5. **Recurring invoice setup** — Support `isSubscription` on orders for monthly/quarterly billing.

6. **Multi-currency support** — Allow specifying currency on invoice creation (EUR, USD, SEK, etc.).

7. **Invoice PDF download** — Retrieve invoice PDF via `documentId` for sharing/verification.

8. **Bulk operations** — "Fakturer alle kunder med utestående ordrer" (invoice all customers with outstanding orders).

### 8.3 Low Priority (Nice to Have)

9. **Delivery address management** — Not commonly requested but may appear in Tier 3.

10. **Product categories/grouping** — Products have no category system in current API.

11. **Customer import** — Bulk create customers from CSV/list.

### 8.4 Robustness Improvements

12. **ASCII folding everywhere** — Systematically fold å→a, ø→o, æ→ae in all classifier patterns. Many patterns still only have Norwegian-character versions.

13. **Informal Norwegian** — Handle conversational patterns: "Kan du lage en faktura..." (Can you create an invoice...), "Fikser du..." (Can you fix...).

14. **Amount parsing** — Handle Norwegian number formats: "1.500,50" (one thousand five hundred and fifty øre), "5000,-" (five thousand even).

15. **Date parsing** — Handle Norwegian date formats: "15. mars 2026", "i dag" (today), "neste fredag" (next Friday).
