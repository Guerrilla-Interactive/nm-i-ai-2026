# Tripletex API v2 — Field Names Research

> Research date: 2026-03-20
> Sources: Tripletex OpenAPI spec, GitHub examples (Tripletex/tripletex-api2),
> Ruby/PHP SDK model docs, FAQ, and analysis of our executor.py code.

## General API Conventions

- **Auth**: Basic Auth with username `"0"` and password = session_token
- **POST response**: `{"value": {...}}` — single entity wrapped in `value`
- **GET list response**: `{"fullResultSize": N, "values": [...]}`
- **Dates**: ISO 8601 format `"YYYY-MM-DD"` (strings, not timestamps)
- **Object references**: Always `{"id": <int>}` — never pass the full object
- **Version field**: Required for all PUT operations (optimistic locking). Omit on POST.
- **ID field**: Never set `id` on POST — the API generates it. Setting `id` causes `"An ID cannot be set when creating a new object."`
- **`fields=*`**: Use on GET requests to receive all fields including `version`
- **PUT semantics**: Tripletex uses PUT with optional fields instead of PATCH

---

## 1. Employee (`/employee`)

### GET /employee — Query Parameters
| Param | Works? | Notes |
|-------|--------|-------|
| `firstName` | YES | Exact match filter |
| `email` | YES | Exact match filter |
| `lastName` | NO | NOT a supported filter — must filter client-side |
| `name` | NO | Does not exist as a query param |
| `departmentId` | NO | Does not work for filtering |
| `employeeNumber` | NO | Does not work for filtering |
| `id` | YES | Comma-separated list of IDs |
| `fields` | YES | Use `fields=*` to get version, address, etc. |
| `includeContacts` | YES | Include contact-flagged employees |

### POST /employee — Required Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `firstName` | string | YES | |
| `lastName` | string | YES | |

### POST /employee — Common Optional Fields
| Field | Type | Notes |
|-------|------|-------|
| `email` | string | Practically required for login users. **IMMUTABLE after creation** — cannot change via PUT! |
| `userType` | string enum | `"STANDARD"`, `"EXTENDED"`, `"NO_ACCESS"`. Write-only on POST; may be ignored on PUT. |
| `department` | `{"id": int}` | Object reference. Needed for most operations. |
| `dateOfBirth` | string | `"YYYY-MM-DD"`. Not required on POST, but **required on PUT** even if null on create. |
| `phoneNumberMobile` | string | Mobile phone |
| `phoneNumberWork` | string | Work phone |
| `phoneNumberHome` | string | Home phone |
| `employeeNumber` | int/string | Employee number |
| `nationalIdentityNumber` | string | Norwegian personal ID |
| `bankAccountNumber` | string | Norwegian bank account |
| `address` | object | See address sub-object below |
| `comments` | string | Free text |

### Address Sub-Object (used in employee, customer)
```json
{
  "addressLine1": "string",
  "addressLine2": "string",
  "postalCode": "string",
  "city": "string"
}
```

### PUT /employee/{id} — Required Fields
| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Must match URL param |
| `version` | int | Optimistic locking — GET first to obtain |
| `firstName` | string | |
| `lastName` | string | |
| `email` | string | **Must pass current value — IMMUTABLE** |
| `dateOfBirth` | string | Required on PUT even if it was null on create. Use `"1990-01-01"` as fallback. |

### Fields That DON'T Exist (will cause 422)
- `startDate` — employees don't have this
- `role` — use `userType` instead
- `phone` — use `phoneNumberMobile`, `phoneNumberWork`, or `phoneNumberHome`
- `name` — use `firstName` + `lastName` separately
- `departmentId` — use `department: {"id": N}` object reference

### Common Gotchas
1. **Email is IMMUTABLE** — you cannot change it via PUT after creation
2. **userType may be ignored on PUT** — it's effectively write-only on POST
3. **dateOfBirth is required on PUT** even when not set during creation
4. **DELETE may return 403** — sandbox often denies permission

---

## 2. Customer (`/customer`)

### GET /customer — Query Parameters
| Param | Works? | Notes |
|-------|--------|-------|
| `customerName` | YES | Search by customer name |
| `email` | YES | |
| `organizationNumber` | YES | |
| `id` | YES | Comma-separated IDs |
| `isSupplier` | YES | Boolean filter |
| `isCustomer` | YES | Boolean filter |

### POST /customer — Required Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | YES | Only truly required field |

### POST /customer — Common Optional Fields
| Field | Type | Notes |
|-------|------|-------|
| `organizationNumber` | string | Must be 9 digits for Norwegian orgs. Validated against country. |
| `email` | string | General email |
| `invoiceEmail` | string | Separate invoice email |
| `phoneNumber` | string | NOT `phone` — use `phoneNumber` |
| `phoneNumberMobile` | string | Mobile phone |
| `isCustomer` | boolean | `true` to mark as customer (vs. supplier). **Defaults to false!** Always set to `true`. |
| `isPrivateIndividual` | boolean | Individual vs. company |
| `invoiceSendMethod` | string enum | `"EMAIL"`, `"EHF"`, `"EFAKTURA"`, `"VIPPS"`, `"PAPER"`, `"MANUAL"` |
| `invoicesDueIn` | int | Number of days/months until due |
| `invoicesDueInType` | string enum | `"DAYS"`, `"MONTHS"`, `"RECURRING_DAY_OF_MONTH"` |
| `postalAddress` | object | See address sub-object. Required for EHF invoices! |
| `physicalAddress` | object | Physical/visit address |
| `deliveryAddress` | object | Delivery address |
| `description` | string | |
| `website` | string | |
| `language` | string | |
| `currency` | `{"id": int}` | Currency reference |

### Fields That DON'T Exist
- `phone` — use `phoneNumber`
- `org_number` — use `organizationNumber`
- `address` — use `postalAddress`, `physicalAddress`, or `deliveryAddress`
- `customerNumber` — read-only, auto-generated
- `isSupplier` — separate field, not settable on customer create in all cases

### Common Gotchas
1. **`isCustomer` defaults to false** — always explicitly set `true`
2. **organizationNumber validation** — must be exactly 9 digits for Norway. Validated against the country in `physicalAddress`.
3. **EHF invoicing requires postalAddress** — Peppol BIS billing 3.0 requirement
4. **invoiceSendMethod defaults to `"EHF"`** when `isPrivateIndividual=false` — may cause issues if no postalAddress

---

## 3. Product (`/product`)

### POST /product — Required Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | YES | Only truly required field |

### POST /product — Common Optional Fields
| Field | Type | Notes |
|-------|------|-------|
| `number` | string | Product number (code). Auto-generated if omitted. |
| `description` | string | |
| `priceExcludingVatCurrency` | float | Price ex. VAT (used when `isPrioritizeAmountsIncludingVat=false` on order) |
| `priceIncludingVatCurrency` | float | Price inc. VAT |
| `costExcludingVatCurrency` | float | Cost/purchase price |
| `vatType` | `{"id": int}` | VAT type reference. Resolved via GET /ledger/vatType. |
| `currency` | `{"id": int}` | Currency reference |
| `productUnit` | `{"id": int}` | Unit of measure reference |
| `department` | `{"id": int}` | Department reference |

### Fields That DON'T Exist
- `price` — use `priceExcludingVatCurrency` or `priceIncludingVatCurrency`
- `vat` / `vatRate` / `vatPercentage` — use `vatType: {"id": N}` reference
- `unit` — use `productUnit: {"id": N}` reference
- `cost` — use `costExcludingVatCurrency`
- `sku` — use `number`

### Common Gotchas
1. **Product VAT type** affects which income account is used on invoices
2. **Must create products before referencing them in orders** — cannot inline
3. **Product number is string**, not int

---

## 4. Order (`/order`) + OrderLines

### POST /order — Required Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `customer` | `{"id": int}` | YES | Customer reference |
| `orderDate` | string | YES | `"YYYY-MM-DD"` |
| `deliveryDate` | string | YES | `"YYYY-MM-DD"` |

### POST /order — Common Optional Fields
| Field | Type | Notes |
|-------|------|-------|
| `orderLines` | array | Can be included inline on POST (preferred — saves API calls) |
| `invoiceComment` | string | Comment that appears on the invoice |
| `isPrioritizeAmountsIncludingVat` | boolean | Controls VAT display. Default: false (ex. VAT). |
| `contact` | `{"id": int}` | Contact person reference |
| `department` | `{"id": int}` | Department reference |
| `project` | `{"id": int}` | Project reference |
| `currency` | `{"id": int}` | Currency reference |
| `invoicesDueIn` | int | Override due days |
| `invoicesDueInType` | string | `"DAYS"`, `"MONTHS"` |
| `deliveryAddress` | object | Address object |
| `deliveryComment` | string | |
| `number` | string | Order number |
| `reference` | string | Customer reference |

### OrderLine Fields (inline in `orderLines` array)
| Field | Type | Notes |
|-------|------|-------|
| `description` | string | Line description (used if no product ref) |
| `count` | float | Quantity. **Must be float** (e.g., `2.0` not `2`). |
| `unitPriceExcludingVatCurrency` | float | Price per unit ex. VAT |
| `unitPriceIncludingVatCurrency` | float | Price per unit inc. VAT |
| `product` | `{"id": int}` | Product reference (optional) |
| `vatType` | `{"id": int}` | Override VAT type |
| `discount` | float | Discount percentage (0-100) |
| `unitCostCurrency` | float | Cost per unit |

### PUT /order/{id}/:invoice — Converting Order to Invoice
This is a **query-params-only** endpoint (no request body).

| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `invoiceDate` | string | YES | `"YYYY-MM-DD"` |
| `sendToCustomer` | string | NO | `"true"` or `"false"`. Default varies. |
| `paymentTypeId` | string | NO | For registering payment at invoice time |
| `paidAmount` | string | NO | Amount paid (combine with paymentTypeId) |

### Fields That DON'T Exist on Order/OrderLine
- `quantity` — use `count`
- `unitPrice` — use `unitPriceExcludingVatCurrency` or `unitPriceIncludingVatCurrency`
- `price` — not a field name
- `amount` — not a field name on order lines
- `orderId` on order lines when POSTing inline — the order assigns automatically

### Common Gotchas
1. **isPrioritizeAmountsIncludingVat must match the price field used** — if `true`, use `unitPriceIncludingVatCurrency`; if `false`, use `unitPriceExcludingVatCurrency`. Mixing causes 422.
2. **orderLines can be POSTed inline** or added separately via POST /order/orderline
3. **count must be a float** — `2.0` not `2`
4. **Cannot set ID on new order lines** — causes `"An ID cannot be set when creating a new object"`

---

## 5. Invoice (`/invoice`)

**Invoices are NOT created directly** via POST /invoice. They are created by invoicing an order:
`PUT /order/{id}/:invoice`

### Invoice Model Fields (read-only, from GET)
| Field | Type | Notes |
|-------|------|-------|
| `id` | int | |
| `version` | int | |
| `invoiceNumber` | int | Auto-generated |
| `invoiceDate` | string | |
| `invoiceDueDate` | string | |
| `customer` | object | Customer reference |
| `orders` | array | Linked order references |
| `amount` | float | Total inc. VAT |
| `amountExcludingVat` | float | Total ex. VAT |
| `amountOutstanding` | float | Remaining to pay |
| `comment` | string | From order's invoiceComment |
| `kid` | string | Norwegian payment reference |
| `isCreditNote` | boolean | |
| `isCharged` | boolean | |

### PUT /invoice/{id}/:payment — Register Payment
| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `paymentDate` | string | YES | `"YYYY-MM-DD"` |
| `paymentTypeId` | int | YES | From GET /invoice/paymentType |
| `paidAmount` | float | YES | Amount paid |

### PUT /invoice/{id}/:createCreditNote
| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `date` | string | YES | Credit note date |
| `comment` | string | NO | |
| `sendToCustomer` | string | NO | `"true"` or `"false"` |

### Prerequisite: Bank Account
Before any invoice can be created, ledger account 1920 must have a `bankAccountNumber` set.
Error without it: `"Faktura kan ikke opprettes for selskapet har registrert et bankkontonummer."`

Flow: `GET /ledger/account?number=1920` → check `bankAccountNumber` → if empty, `PUT /ledger/account/{id}` with a dummy number like `"12345678903"`.

---

## 6. Travel Expense (`/travelExpense`)

### POST /travelExpense — Required Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `employee` | `{"id": int}` | YES | Only truly required field |

### POST /travelExpense — Common Optional Fields
| Field | Type | Notes |
|-------|------|-------|
| `title` | string | Expense title/description |
| `date` | string | `"YYYY-MM-DD"` |
| `project` | `{"id": int}` | Project reference |
| `department` | `{"id": int}` | Department reference |
| `isChargeable` | boolean | Default: false |
| `isFixedInvoicedAmount` | boolean | Default: false |
| `isIncludeAttachedReceiptsWhenReinvoicing` | boolean | Default: false |
| `travelDetails` | object | See below |

### travelDetails Sub-Object
| Field | Type | Notes |
|-------|------|-------|
| `isForeignTravel` | boolean | |
| `isDayTrip` | boolean | |
| `departureDate` | string | `"YYYY-MM-DD"` |
| `returnDate` | string | `"YYYY-MM-DD"` |
| `departureFrom` | string | Starting location |
| `destination` | string | Travel destination |
| `departureTime` | string | `"HH:MM"` |
| `returnTime` | string | `"HH:MM"` |
| `purpose` | string | Trip purpose |

### POST /travelExpense/cost — Cost Line
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `travelExpense` | `{"id": int}` | YES | Parent expense reference |
| `paymentType` | `{"id": int}` | YES | From GET /travelExpense/paymentType |
| `amountCurrencyIncVat` | float | YES | Amount including VAT |
| `date` | string | NO | Cost date |
| `costCategory` | `{"id": int}` | NO | Category reference |

### Related Endpoints
- `GET /travelExpense/paymentType` — e.g., "Privat utlegg" (out-of-pocket)
- `GET /travelExpense/costCategory` — e.g., "Bredbånd", "Kontorrekvisita"
- `DELETE /travelExpense/{id}` — returns 204. Only works on OPEN expenses (not delivered/approved).

### Fields That DON'T Exist on TravelExpense
- `amount` — computed from cost lines
- `costs` — this is the array returned on GET, but for POST you create costs separately via /travelExpense/cost
- `departure_date` — use `travelDetails.departureDate` (camelCase)

---

## 7. Project (`/project`)

### POST /project — Required Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | YES | |
| `projectManager` | `{"id": int}` | YES | Employee reference. **NOT `projectManagerId`!** |
| `startDate` | string | YES | `"YYYY-MM-DD"` |

### POST /project — Common Optional Fields
| Field | Type | Notes |
|-------|------|-------|
| `description` | string | |
| `endDate` | string | `"YYYY-MM-DD"` |
| `customer` | `{"id": int}` | Customer reference |
| `department` | `{"id": int}` | Department reference |
| `isInternal` | boolean | |
| `isFixedPrice` | boolean | |
| `fixedprice` | float | Note: lowercase 'p' in fixedprice! |
| `number` | string | Project number |

### PUT /project/{id} — Required Fields
| Field | Type | Notes |
|-------|------|-------|
| `id` | int | |
| `version` | int | |
| `name` | string | |
| `startDate` | string | |
| `projectManager` | `{"id": int}` | Must include existing ref |

### Fields That DON'T Exist
- `projectManagerId` — use `projectManager: {"id": N}` object reference
- `managerId` — use `projectManager: {"id": N}`
- `status` — use `isClosed` boolean
- `budget` — use `fixedprice` (note lowercase)

### Common Gotchas
1. **projectManager is required** — must resolve an employee first
2. **startDate is required** — defaults should use today's date
3. **fixedprice has lowercase 'p'** — not `fixedPrice`

---

## 8. Department (`/department`)

### POST /department — Required Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | YES | Only required field |

### POST /department — Optional Fields
| Field | Type | Notes |
|-------|------|-------|
| `departmentNumber` | string | Department number/code |
| `departmentManager` | `{"id": int}` | Employee reference |

### Fields That DON'T Exist
- `number` — use `departmentNumber`
- `manager` — use `departmentManager: {"id": N}`
- `description` — departments don't have this field

### Common Gotchas
1. Very simple entity — only `name` is required
2. `departmentNumber` is a **string**, not int

---

## 9. Contact (`/contact`)

### POST /contact — Required Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `firstName` | string | YES | |
| `lastName` | string | YES | |

### POST /contact — Common Optional Fields
| Field | Type | Notes |
|-------|------|-------|
| `email` | string | |
| `phoneNumberMobile` | string | NOT `phone` |
| `phoneNumberWork` | string | |
| `customer` | `{"id": int}` | Links contact to a customer |
| `department` | `{"id": int}` | Department reference |

### Fields That DON'T Exist
- `phone` — use `phoneNumberMobile` or `phoneNumberWork`
- `customerId` — use `customer: {"id": N}` object reference
- `name` — use `firstName` + `lastName` separately

---

## 10. VAT Type (`/ledger/vatType`)

### GET /ledger/vatType — Query Parameters
| Param | Type | Notes |
|-------|------|-------|
| `typeOfVat` | string | `"outgoing"` or `"incoming"`. Outgoing = sales/revenue VAT. |
| `id` | string | Comma-separated IDs |
| `number` | string | VAT type number |
| `vatDate` | string | Date for VAT validity. Default: today. |

### VatType Fields (read-only GET response)
| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Used for references: `{"id": N}` |
| `name` | string | e.g., "Utgående mva høy sats" |
| `number` | string | VAT code number |
| `percentage` | float | e.g., `25.0`, `15.0`, `12.0`, `0.0` |

### Common Norwegian VAT Types (Outgoing/Utgående)
| Percentage | Description | Typical ID |
|-----------|-------------|------------|
| 25% | Standard rate (høy sats) | 3 |
| 15% | Food rate (matvaresats) | varies |
| 12% | Transport/hotel (lav sats) | varies |
| 0% | Exempt (fritak) | 6 |

**IDs vary per sandbox** — always resolve dynamically via `GET /ledger/vatType?typeOfVat=outgoing`.

### Common Gotchas
1. **Always use `typeOfVat=outgoing`** for product/invoice VAT — "incoming" is for purchase VAT
2. **IDs are sandbox-specific** — never hardcode
3. **Filter by percentage client-side** after fetching — no percentage query param

---

## 11. Ledger Account (`/ledger/account`)

### GET /ledger/account — Query Parameters
| Param | Type | Notes |
|-------|------|-------|
| `number` | string | Account number (e.g., "1920") |
| `isBankAccount` | string | `"true"` to filter bank accounts |
| `numberFrom` / `numberTo` | string | Range filter |

### PUT /ledger/account/{id} — Bank Account Setup
| Field | Type | Notes |
|-------|------|-------|
| `id` | int | Required |
| `version` | int | Required |
| `number` | int | Account number (e.g., 1920) |
| `name` | string | Account name |
| `bankAccountNumber` | string | **The bank account number to set** |
| `isBankAccount` | boolean | |

---

## Summary: Critical Rules

### Never Send These on POST
- `id` — auto-generated
- `version` — auto-generated (needed only for PUT)
- `changes` — read-only metadata
- `url` — read-only

### Always Use Object References
```
CORRECT:   "customer": {"id": 123}
WRONG:     "customerId": 123
WRONG:     "customer": 123
```

### Norwegian Error Messages (Common 422s)
| Norwegian | English | Cause |
|-----------|---------|-------|
| "Feltet eksisterer ikke" | "Field does not exist" | Unknown field name in payload |
| "Faktura kan ikke opprettes før selskapet har registrert et bankkontonummer" | Invoice requires bank account | Set bankAccountNumber on ledger account 1920 |
| "An ID cannot be set when creating a new object" | Don't set ID on POST | Remove `id` from POST payload |
| "Organisasjonsnummeret må bestå av 9 tall" | Org number must be 9 digits | Invalid organizationNumber format |

### API Call Efficiency
Every unnecessary API call and every 4xx error hurts the efficiency bonus (up to 2x multiplier). Minimize calls by:
1. Inlining orderLines in POST /order (saves separate POST /order/orderline calls)
2. Combining invoice + payment via paymentTypeId/paidAmount on PUT /order/:invoice
3. Using query filters to avoid fetching all entities
4. Checking bank account setup once, not per invoice

---

## Sources

- [Tripletex API v2 Docs](https://tripletex.no/v2-docs/)
- [Tripletex Developer Portal](https://developer.tripletex.no/)
- [GitHub: tripletex-api2](https://github.com/Tripletex/tripletex-api2)
- [GitHub: tripletex-api2 FAQ](https://github.com/Tripletex/tripletex-api2/blob/master/FAQ.md)
- [GitHub: tripletex-api2 JSON Examples](https://github.com/Tripletex/tripletex-api2/blob/master/examples/json/README.md)
- [GitHub: Order/Invoice Java Example](https://github.com/Tripletex/tripletex-api2/blob/master/examples/java-gradle/order/src/main/java/no/tripletex/example/order/OrderInvoiceExampleBaseline.java)
- [Ruby SDK Model Docs](https://github.com/sveredyuk/tripletex_ruby/tree/master/docs)
- [PHP SDK Model Docs](https://github.com/thorarne/php-tripletex/tree/master/docs/Model)
- [Invoice/Order FAQ](https://developer.tripletex.no/docs/documentation/faq/invoice-order/)
- [Customer FAQ](https://developer.tripletex.no/docs/documentation/faq/customer/)
- [VAT Types Documentation](https://developer.tripletex.no/docs/documentation/using-vattypes-vat-codes/)
