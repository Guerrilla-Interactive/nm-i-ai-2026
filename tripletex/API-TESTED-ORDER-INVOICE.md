# Tripletex API: Order → Invoice Flow — Tested Results

**Sandbox:** `https://kkpqfuj-amager.tripletex.dev/v2`
**Auth:** Basic Auth, username `0`, password: `eyJ0b2tlbklkIjoyMTQ3NjUyNjMyLCJ0b2tlbiI6ImQ4NWU3MDZmLWI1MjQtNDk0MS04ZTQ1LWUxZWNiMjVlN2M2MyJ9`
**Tested:** 2026-03-20

---

## Prerequisites

### Company Bank Account Required
Invoices CANNOT be created until the company has a bank account number registered on ledger account 1920.

```
PUT /v2/ledger/account/{account1920id}
{
  "id": {account1920id},
  "version": 0,
  "number": 1920,
  "name": "Bankinnskudd",
  "bankAccountNumber": "12345678903",
  "isBankAccount": true
}
```

Find account 1920 via: `GET /v2/ledger/account?isBankAccount=true`

Error if missing: `"Faktura kan ikke opprettes før selskapet har registrert et bankkontonummer."`

---

## 1. Create Customer

**Endpoint:** `POST /v2/customer`

**Minimum required fields:**
```json
{"name": "Test Customer AS"}
```

**Response (key fields):**
```json
{
  "value": {
    "id": 108168567,
    "name": "Test Customer AS",
    "customerNumber": 10002,
    "isCustomer": true,
    "invoicesDueIn": 14,
    "invoicesDueInType": "DAYS",
    "currency": {"id": 1},
    "invoiceSendMethod": "EMAIL"
  }
}
```

**Notes:**
- Only `name` is required
- Customer automatically gets a `customerNumber`
- Default 14-day invoice terms

---

## 2. Create Product

**Endpoint:** `POST /v2/product`

**Minimum required fields:**
```json
{"name": "Test Product"}
```

**Response (key fields):**
```json
{
  "value": {
    "id": 84382010,
    "name": "Test Product",
    "priceExcludingVatCurrency": 0,
    "vatType": {"id": 6},
    "currency": {"id": 1}
  }
}
```

**Notes:**
- Only `name` is required
- Price defaults to 0 — set `priceExcludingVatCurrency` or override on order line
- VAT type defaults to id 6

---

## 3. Create Order

**Endpoint:** `POST /v2/order`

**Minimum required fields:**
```json
{
  "customer": {"id": <customer_id>},
  "orderDate": "2026-03-20",
  "deliveryDate": "2026-03-25"
}
```

**Required fields:**
| Field | Required | Notes |
|---|---|---|
| `customer.id` | YES | Must exist |
| `orderDate` | YES | Format: YYYY-MM-DD |
| `deliveryDate` | YES | Error: "Kan ikke være null." if missing |
| `orderLines` | NO | Can be empty, added separately later |

**Response (key fields):**
```json
{
  "value": {
    "id": 401950669,
    "number": "1",
    "customer": {"id": 108168567},
    "orderDate": "2026-03-20",
    "deliveryDate": "2026-03-25",
    "isClosed": false,
    "currency": {"id": 1},
    "invoicesDueIn": 14,
    "invoicesDueInType": "DAYS",
    "preliminaryInvoice": {"id": 2147518523},
    "orderLines": []
  }
}
```

**Notes:**
- `preliminaryInvoice` is auto-created (draft) — this becomes the real invoice
- Order lines can be included inline OR added separately via POST /order/orderline

---

## 4. Add Order Lines

**Endpoint:** `POST /v2/order/orderline`

### With product reference:
```json
{
  "order": {"id": <order_id>},
  "product": {"id": <product_id>},
  "count": 2,
  "unitPriceExcludingVatCurrency": 100.00
}
```

### Without product (free-text line):
```json
{
  "order": {"id": <order_id>},
  "description": "Manual line item",
  "count": 1,
  "unitPriceExcludingVatCurrency": 250.00
}
```

**Required fields:**
| Field | Required | Notes |
|---|---|---|
| `order.id` | YES | Must reference existing order |
| `count` | YES | Quantity |
| `unitPriceExcludingVatCurrency` | YES | Unit price excl. VAT |
| `product.id` | NO | If omitted, `description` is used as display name |
| `description` | NO | Free text, overrides product name if set |

**Response (key fields):**
```json
{
  "value": {
    "id": 1607495654,
    "product": {"id": 84382010},
    "count": 2.0,
    "unitPriceExcludingVatCurrency": 100.0,
    "amountExcludingVatCurrency": 200.00,
    "amountIncludingVatCurrency": 200.00,
    "vatType": {"id": 6},
    "discount": 0.00,
    "order": {"id": 401950669}
  }
}
```

---

## 5. Convert Order to Invoice

### Method A: PUT /order/{id}/:invoice (Recommended)

**Endpoint:** `PUT /v2/order/{order_id}/:invoice?invoiceDate=YYYY-MM-DD&sendToCustomer=false`

**Parameters (query string):**
| Param | Required | Notes |
|---|---|---|
| `invoiceDate` | YES | Format: YYYY-MM-DD |
| `sendToCustomer` | NO | `false` to not email customer |

**Example:**
```
PUT /v2/order/401950669/:invoice?invoiceDate=2026-03-20&sendToCustomer=false
```

### Method B: POST /invoice

**Endpoint:** `POST /v2/invoice`

**Body:**
```json
{
  "invoiceDate": "2026-03-20",
  "invoiceDueDate": "2026-04-03",
  "orders": [{"id": <order_id>}]
}
```

**Required fields:**
| Field | Required | Notes |
|---|---|---|
| `invoiceDate` | YES | YYYY-MM-DD |
| `invoiceDueDate` | YES | YYYY-MM-DD |
| `orders` | YES | Non-empty array of order refs |

**IMPORTANT:** `sendToCustomer` is NOT a valid field on POST /invoice body (error: "Feltet eksisterer ikke i objektet").

**Cannot create invoice without order:** Error: `"orders": "Kan ikke være null."` and `"Listen kan ikke være tom."`

### Response (both methods, key fields):
```json
{
  "value": {
    "id": 2147518523,
    "invoiceNumber": 1,
    "invoiceDate": "2026-03-20",
    "invoiceDueDate": "2026-04-03",
    "customer": {"id": 108168567},
    "orders": [{"id": 401950669}],
    "orderLines": [{"id": 1607495651}, {"id": 1607495654}],
    "voucher": {"id": 608818352},
    "deliveryDate": "2026-03-25",
    "amount": 400.0,
    "amountCurrency": 400.0,
    "amountExcludingVat": 400.0,
    "amountExcludingVatCurrency": 400.0,
    "amountOutstanding": 400.0,
    "isCreditNote": false,
    "isCharged": true,
    "isApproved": true,
    "documentId": 1024147263
  }
}
```

---

## 6. List/Get Invoices

### List invoices:
```
GET /v2/invoice?invoiceDateFrom=2026-01-01&invoiceDateTo=2026-12-31
```

**Required query params:**
| Param | Required |
|---|---|
| `invoiceDateFrom` | YES |
| `invoiceDateTo` | YES |

Error if missing: `"invoiceDateFrom": "Kan ikke være null."`, `"invoiceDateTo": "Kan ikke være null."`

### Get single invoice:
```
GET /v2/invoice/{id}
GET /v2/invoice/{id}?fields=*
```

### Full field list (from fields=*):
```
id, version, url, invoiceNumber, invoiceDate, customer, creditedInvoice,
isCredited, invoiceDueDate, kid, invoiceComment, comment, orders, orderLines,
travelReports, projectInvoiceDetails, voucher, deliveryDate, amount,
amountCurrency, amountExcludingVat, amountExcludingVatCurrency, amountRoundoff,
amountRoundoffCurrency, amountOutstanding, amountCurrencyOutstanding,
amountOutstandingTotal, amountCurrencyOutstandingTotal, sumRemits, currency,
isCreditNote, isCharged, isApproved, postings, reminders, invoiceRemarks,
invoiceRemark, isPeriodizationPossible, documentId
```

---

## 7. Register Payment

**Endpoint:** `PUT /v2/invoice/{id}/:payment`

**Parameters (query string):**
| Param | Required | Notes |
|---|---|---|
| `paymentDate` | YES | YYYY-MM-DD |
| `paymentTypeId` | YES | Must be an INCOMING payment type ID |
| `paidAmount` | YES | Amount paid |

**Example:**
```
PUT /v2/invoice/2147518551/:payment?paymentDate=2026-03-20&paymentTypeId=33998616&paidAmount=1500
```

### Finding payment type IDs:

**Outgoing payment types** (for supplier invoices): `GET /v2/ledger/paymentTypeOut`
- IDs found: 33998620-33998623 (sandbox)

**Incoming payment types** (for customer invoice payments):
- NOT listed at `/v2/ledger/paymentTypeIn` (404) or `/v2/ledger/paymentType` (404)
- IDs found by testing: 33998616-33998619 (just below the outgoing range)
- ID 33998616 = "Kontant" (cash payment, incoming)

**Error if using outgoing type:** `"Den angitte betalingstypen må være en innbetaling."`

### Result after payment:
```json
{
  "amountOutstanding": 0.00,
  "amountCurrencyOutstanding": 0.00
}
```

**Notes:**
- Payment can exceed invoice amount (creates overpayment / negative outstanding)
- Multiple payments can be registered on the same invoice

---

## 8. Create Credit Note

**Endpoint:** `PUT /v2/invoice/{id}/:createCreditNote`

**Parameters (query string):**
| Param | Required | Notes |
|---|---|---|
| `date` | YES | YYYY-MM-DD |
| `comment` | NO | Comment on credit note |
| `sendToCustomer` | NO | `false` to not email |

**Example:**
```
PUT /v2/invoice/2147518542/:createCreditNote?date=2026-03-20&comment=Test+credit+note&sendToCustomer=false
```

**Response (key fields):**
```json
{
  "value": {
    "id": 2147518543,
    "invoiceNumber": 3,
    "creditedInvoice": 2147518542,
    "isCreditNote": true,
    "amount": -250.00,
    "amountOutstanding": 0.00,
    "comment": "Test credit note"
  }
}
```

**Notes:**
- Creates a new invoice with negative amount
- `isCreditNote: true` on the credit note
- `creditedInvoice` points to the original invoice ID
- The original invoice gets `isCredited: true`

---

## Dependency Chain

```
1. Company bank account (ledger account 1920) must have bankAccountNumber set
2. Customer (POST /customer) — needs: name
3. Product (POST /product) — needs: name (optional, can use free-text lines)
4. Order (POST /order) — needs: customer.id, orderDate, deliveryDate
5. Order Lines (POST /order/orderline) — needs: order.id, count, unitPriceExcludingVatCurrency
6. Invoice (PUT /order/{id}/:invoice OR POST /invoice) — needs: order with lines, invoiceDate
7. Payment (PUT /invoice/{id}/:payment) — needs: paymentDate, paymentTypeId (incoming), paidAmount
8. Credit Note (PUT /invoice/{id}/:createCreditNote) — needs: date
```

**You CANNOT skip the order step.** Invoices require at least one order reference.

---

## Common Errors

| Error | Cause |
|---|---|
| `"Faktura kan ikke opprettes før selskapet har registrert et bankkontonummer."` | Company has no bank account on ledger 1920 |
| `"deliveryDate": "Kan ikke være null."` | Order missing deliveryDate |
| `"orders": "Kan ikke være null."` / `"Listen kan ikke være tom."` | POST /invoice without orders array |
| `"invoiceDateFrom": "Kan ikke være null."` | GET /invoice without date range |
| `"Den angitte betalingstypen må være en innbetaling."` | Used outgoing payment type for invoice payment |
| `"Feltet eksisterer ikke i objektet."` | Unknown field in JSON body (e.g., sendToCustomer on POST /invoice) |
| `"invoiceDate": "Kan ikke være null."` | PUT :invoice without invoiceDate query param |

---

## VAT Types (Observed)

| VAT Type ID | Context |
|---|---|
| 0 | No VAT (used on free-text order lines without product) |
| 6 | Default product VAT type |

---

## Tested Entity IDs (Sandbox)

| Entity | ID | Notes |
|---|---|---|
| Company | 108167433 | "NM i AI /BATCH ULTRATHINK a23fd25c" |
| Customer | 108168567 | "Test Customer AS" |
| Product | 84382010 | "Test Product" |
| Bank Account (1920) | 436982614 | bankAccountNumber: 12345678903 |
| Incoming Payment Type | 33998616 | "Kontant" |
| Outgoing Payment Types | 33998620-33998623 | Various |
