# Invoice Flow Test Results — 2026-03-20

## Sandbox
- Base URL: `https://kkpqfuj-amager.tripletex.dev/v2`
- Auth: Basic `0:<session_token>`

## API Findings

### Order Creation (POST /order)
- Order lines are created inline with the order — no separate endpoint needed
- **Correct field names:** `description`, `count`, `unitPriceExcludingVatCurrency`
- `unitCostCurrency` is NOT the price field (it's internal cost)
- `unitPriceIncludingVatCurrency` also works (for VAT-inclusive pricing)
- Order response doesn't include orderLines by default — use `?fields=id,orderLines(*)` to expand

### Invoice Creation (PUT /order/{id}/:invoice)
- Uses query parameters only, no JSON body
- Key params: `invoiceDate`, `sendToCustomer` (true/false string)
- Can combine with payment: add `paymentTypeId` and `paidAmount` as query params
- Returns full invoice object with `amountOutstanding`

### Payment Registration (PUT /invoice/{id}/:payment)
- Uses query parameters only: `paymentDate`, `paymentTypeId`, `paidAmount`
- Payment types available: `Kontant` (ID: 33998616), `Betalt til bank` (ID: 33998617)
- After payment, `amountOutstanding` drops to 0

### Credit Note (PUT /invoice/{id}/:createCreditNote)
- Query params: `date` (required), `comment` (optional)
- Returns a new invoice object with `isCreditNote: true`

## Test Results

### Direct API Tests (curl)
| Test | Result | API Calls | 4xx Errors |
|------|--------|-----------|------------|
| Create order with lines | ✅ | 1 | 0 |
| Invoice order | ✅ | 1 | 0 |
| Register payment | ✅ | 1 | 0 |
| Combined invoice+payment | ✅ | 2 | 0 |
| Credit note | ✅ | 1 | 0 |
| Full E2E (customer→order→invoice) | ✅ | 3 | 0 |

### Executor Tests (Python)
| Test | Task Type | Result | API Calls | 4xx |
|------|-----------|--------|-----------|-----|
| Invoice with customer lookup | CREATE_INVOICE | ✅ | 3 | 0 |
| Invoice with payment | INVOICE_WITH_PAYMENT | ✅ | 4 | 0 |
| Invoice existing customer | INVOICE_EXISTING_CUSTOMER | ✅ | 3 | 0 |
| Register payment | REGISTER_PAYMENT | ✅ | 2 | 0 |
| Credit note | CREATE_CREDIT_NOTE | ✅ | 1 | 0 |
| Invoice w/ payment (auto amount) | INVOICE_WITH_PAYMENT | ✅ | 4 | 0 |

### /solve Endpoint Tests (rule-based classifier)
| Prompt | Classification | Result | API Calls | 4xx |
|--------|---------------|--------|-----------|-----|
| "Opprett en faktura for kunde Testbedrift AS med 2 stk Widget til 299 kr" | INVOICE_EXISTING_CUSTOMER | ✅ | 3 | 0 |
| "Lag en faktura med betaling for kunde Testbedrift AS. 3 stk Konsulenttime til 1200 kr" | INVOICE_WITH_PAYMENT | ✅ | 4 | 0 |
| "Create an invoice for customer Testbedrift AS with 5 pcs Widget at 150 NOK" | INVOICE_EXISTING_CUSTOMER | ✅ | 3 | 0 |

## Bugs Fixed

1. **Duplicate `_exec_invoice_with_payment`** — Two definitions existed (lines 533 and 773). The simpler second one was overwriting the first in the registry but lacked payment type lookup. Removed the duplicate.

2. **Keyword classifier ordering** — `CREATE_CUSTOMER` was matched before `CREATE_INVOICE` / `INVOICE_EXISTING_CUSTOMER` because "opprett.*kunde" appeared in the prompt before the invoice-specific keywords. Reordered `_KEYWORD_MAP` to check invoice patterns first.

3. **Missing invoice line extraction** — Added `_extract_invoice_lines()` to parse "N stk X til Y kr" patterns from natural language into structured order lines.

4. **Customer name extraction too greedy** — Fixed regex to stop at digits followed by "stk/pcs" or period+space boundaries.

5. **Missing auto-computed `paid_amount`** — `_exec_invoice_with_payment` now computes total from order lines when `paid_amount` is not explicitly provided.

## Optimal API Call Counts
| Task | Min Calls | Notes |
|------|-----------|-------|
| CREATE_INVOICE (new customer) | 3 | POST /customer → POST /order → PUT /:invoice |
| CREATE_INVOICE (existing customer) | 3 | GET /customer → POST /order → PUT /:invoice |
| INVOICE_EXISTING_CUSTOMER | 3 | GET /customer → POST /order → PUT /:invoice |
| INVOICE_WITH_PAYMENT | 4 | GET /customer → POST /order → GET /paymentType → PUT /:invoice (combined) |
| REGISTER_PAYMENT | 2 | GET /paymentType → PUT /:payment |
| CREATE_CREDIT_NOTE | 1 | PUT /:createCreditNote |
