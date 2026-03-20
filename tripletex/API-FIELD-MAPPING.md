# Tripletex API — Minimum Required Fields & Payload Reference

> Quick-reference for the executor module. Based on OpenAPI spec + official Tripletex examples.
> **Important:** The OpenAPI spec marks NO fields as `required`. Server-side validation determines what's actually needed.
> Minimum payloads below are derived from official examples in [tripletex-api2/examples/json](https://github.com/Tripletex/tripletex-api2/tree/master/examples/json).

---

## Entity: Employee

**Endpoint:** `POST /employee`

### Minimum required payload:
```json
{
  "firstName": "Ola",
  "lastName": "Nordmann"
}
```

### Recommended payload (from official example):
```json
{
  "firstName": "Ola",
  "lastName": "Nordmann",
  "address": {
    "addressLine1": "Storgata 1",
    "postalCode": "0001",
    "city": "Oslo"
  }
}
```

### All writable fields:
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `firstName` | string | **Yes** | |
| `lastName` | string | **Yes** | |
| `email` | string | No | |
| `dateOfBirth` | string | No | YYYY-MM-DD |
| `employeeNumber` | string | No | Auto-generated if omitted |
| `nationalIdentityNumber` | string | No | Norwegian SSN (fødselsnummer) |
| `dnumber` | string | No | D-number (foreign workers) |
| `phoneNumberMobile` | string | No | |
| `phoneNumberHome` | string | No | |
| `phoneNumberWork` | string | No | |
| `bankAccountNumber` | string | No | Norwegian bank account |
| `iban` | string | No | International bank account |
| `bic` | string | No | SWIFT/BIC code |
| `userType` | string | No | `STANDARD`, `EXTENDED`, `NO_ACCESS` |
| `isContact` | boolean | No | True = external contact, not employee |
| `comments` | string | No | |
| `address` | Address | No | See Address schema below |
| `department` | `{"id": N}` | No | |
| `employeeCategory` | `{"id": N}` | No | |

---

## Entity: Customer

**Endpoint:** `POST /customer`

### Minimum required payload:
```json
{
  "name": "Acme AS"
}
```

### Recommended payload:
```json
{
  "name": "Acme AS",
  "email": "post@acme.no",
  "postalAddress": {
    "addressLine1": "Storgata 1",
    "postalCode": "0001",
    "city": "Oslo"
  }
}
```

### All writable fields:
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `name` | string | **Yes** | Company or person name |
| `organizationNumber` | string | No | Norwegian org number |
| `email` | string | No | Primary email |
| `invoiceEmail` | string | No | For invoice delivery |
| `phoneNumber` | string | No | |
| `phoneNumberMobile` | string | No | |
| `isPrivateIndividual` | boolean | No | Person vs company |
| `isInactive` | boolean | No | |
| `invoiceSendMethod` | string | No | `EMAIL`, `EHF`, `EFAKTURA`, `PAPER`, `MANUAL` |
| `invoicesDueIn` | integer | No | Payment terms (number) |
| `invoicesDueInType` | string | No | `DAYS`, `MONTHS`, `RECURRING_DAY_OF_MONTH` |
| `currency` | `{"id": N}` | No | Default: company currency |
| `postalAddress` | Address | No | |
| `physicalAddress` | Address | No | |
| `deliveryAddress` | DeliveryAddress | No | |
| `accountManager` | `{"id": N}` | No | Employee ref |
| `department` | `{"id": N}` | No | |
| `description` | string | No | |
| `language` | string | No | |
| `website` | string | No | |
| `discountPercentage` | number | No | Default discount |

---

## Entity: Product

**Endpoint:** `POST /product`

### Minimum required payload:
```json
{
  "name": "Konsulenttime"
}
```

### Recommended payload:
```json
{
  "name": "Konsulenttime",
  "priceExcludingVatCurrency": 1200.00,
  "vatType": {"id": 3}
}
```

### All writable fields:
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `name` | string | **Yes** | |
| `number` | string | No | Auto-generated if omitted |
| `description` | string | No | |
| `priceExcludingVatCurrency` | number | No | Sale price excl. VAT |
| `priceIncludingVatCurrency` | number | No | Sale price incl. VAT |
| `costExcludingVatCurrency` | number | No | Purchase cost |
| `vatType` | `{"id": N}` | No | See VAT types section |
| `currency` | `{"id": N}` | No | Default: company currency |
| `productUnit` | `{"id": N}` | No | See product units |
| `account` | `{"id": N}` | No | Ledger account |
| `department` | `{"id": N}` | No | |
| `isStockItem` | boolean | No | Track inventory |
| `isInactive` | boolean | No | |
| `ean` | string | No | Barcode |

---

## Entity: Department

**Endpoint:** `POST /department`

### Minimum required payload:
```json
{
  "name": "Salg"
}
```

### Recommended payload:
```json
{
  "name": "Salg",
  "departmentNumber": "100"
}
```

### All writable fields:
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `name` | string | **Yes** | |
| `departmentNumber` | string | No | Auto-generated if omitted |
| `departmentManager` | `{"id": N}` | No | Employee ref |
| `isInactive` | boolean | No | |

---

## Entity: Project

**Endpoint:** `POST /project`

### Minimum required payload:
```json
{
  "name": "AI Consulting",
  "projectManager": {"id": 1}
}
```

### Recommended payload:
```json
{
  "name": "AI Consulting",
  "projectManager": {"id": 1},
  "startDate": "2026-03-19",
  "isInternal": false
}
```

### All writable fields:
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `name` | string | **Yes** | |
| `projectManager` | `{"id": N}` | **Likely yes** | Employee ref |
| `number` | string | No | Auto-generated if NULL |
| `description` | string | No | |
| `startDate` | string | No | YYYY-MM-DD |
| `endDate` | string | No | YYYY-MM-DD |
| `customer` | `{"id": N}` | No | |
| `department` | `{"id": N}` | No | |
| `mainProject` | `{"id": N}` | No | Parent project |
| `isInternal` | boolean | No | |
| `isFixedPrice` | boolean | No | Fixed vs hourly |
| `isClosed` | boolean | No | |
| `isOffer` | boolean | No | Offer vs project |
| `projectCategory` | `{"id": N}` | No | |
| `fixedprice` | number | No | Fixed price amount |
| `currency` | `{"id": N}` | No | |

---

## Entity: Contact

**Endpoint:** `POST /contact`

### Minimum required payload:
```json
{
  "firstName": "Per",
  "lastName": "Hansen",
  "customer": {"id": 42}
}
```

### All writable fields:
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `firstName` | string | **Yes** | |
| `lastName` | string | **Yes** | |
| `customer` | `{"id": N}` | **Likely yes** | Must be linked to a customer |
| `email` | string | No | |
| `phoneNumberMobile` | string | No | |
| `phoneNumberWork` | string | No | |
| `department` | `{"id": N}` | No | |
| `isInactive` | boolean | No | |

---

## Entity: Order

**Endpoint:** `POST /order`

### Minimum required payload:
```json
{
  "customer": {"id": 42},
  "orderDate": "2026-03-19",
  "deliveryDate": "2026-03-19",
  "orderLines": [
    {
      "product": {"id": 1},
      "count": 1,
      "unitPriceExcludingVatCurrency": 500.00
    }
  ]
}
```

### Order line without product (freetext):
```json
{
  "customer": {"id": 42},
  "orderDate": "2026-03-19",
  "deliveryDate": "2026-03-19",
  "orderLines": [
    {
      "description": "Rådgivning",
      "count": 2,
      "unitPriceExcludingVatCurrency": 1200.00,
      "vatType": {"id": 3}
    }
  ]
}
```

### VAT-inclusive pricing:
```json
{
  "customer": {"id": 42},
  "orderDate": "2026-03-19",
  "deliveryDate": "2026-03-19",
  "isPrioritizeAmountsIncludingVat": true,
  "orderLines": [
    {
      "product": {"id": 1},
      "count": 1,
      "unitPriceIncludingVatCurrency": 625.00
    }
  ]
}
```

### All writable fields (Order):
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `customer` | `{"id": N}` | **Yes** | |
| `orderDate` | string | **Yes** | YYYY-MM-DD |
| `deliveryDate` | string | **Likely yes** | YYYY-MM-DD |
| `orderLines` | array | **Yes** | At least one line |
| `invoicesDueIn` | integer | No | Payment terms |
| `invoicesDueInType` | string | No | `DAYS`, `MONTHS` |
| `currency` | `{"id": N}` | No | Default: company currency |
| `department` | `{"id": N}` | No | |
| `project` | `{"id": N}` | No | |
| `invoiceComment` | string | No | Appears on invoice |
| `internalComment` | string | No | Internal only |
| `isPrioritizeAmountsIncludingVat` | boolean | No | Use VAT-inclusive prices |
| `deliveryAddress` | DeliveryAddress | No | |
| `deliveryComment` | string | No | |
| `reference` | string | No | |
| `ourContactEmployee` | `{"id": N}` | No | |
| `receiverEmail` | string | No | |
| `isClosed` | boolean | No | |

### All writable fields (OrderLine):
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `product` | `{"id": N}` | One of product/description | |
| `description` | string | One of product/description | Freetext line |
| `count` | number | **Yes** | Quantity |
| `unitPriceExcludingVatCurrency` | number | **Yes** (or incl) | Sale price excl. VAT |
| `unitPriceIncludingVatCurrency` | number | Alt to above | If `isPrioritizeAmountsIncludingVat` |
| `unitCostCurrency` | number | No | Cost price |
| `vatType` | `{"id": N}` | No | Inherited from product if omitted |
| `discount` | number | No | Discount % |
| `markup` | number | No | Markup % |
| `currency` | `{"id": N}` | No | |

---

## Entity: Invoice

**Endpoint:** `POST /invoice`

### Method 1: Invoice from existing order (preferred)
```
PUT /order/{orderId}/:invoice?invoiceDate=2026-03-19
```
No request body needed — just query params. Returns the created invoice.

**Query params:**
| Param | Required | Notes |
|-------|----------|-------|
| `invoiceDate` | **Yes** | YYYY-MM-DD |
| `sendToCustomer` | No | Default false |
| `paymentTypeId` | No | For prepaid invoices |
| `paidAmount` | No | Prepaid amount |

### Method 2: Invoice with inline order
```json
POST /invoice?sendToCustomer=false
{
  "invoiceDate": "2026-03-19",
  "invoiceDueDate": "2026-04-19",
  "orders": [{
    "customer": {"id": 42},
    "orderDate": "2026-03-19",
    "deliveryDate": "2026-03-19",
    "orderLines": [{
      "product": {"id": 1},
      "count": 10,
      "unitPriceExcludingVatCurrency": 500.00
    }]
  }]
}
```

### Method 3: Invoice referencing existing order
```json
POST /invoice?sendToCustomer=false
{
  "invoiceDate": "2026-03-19",
  "invoiceDueDate": "2026-04-19",
  "orders": [{"id": 123}]
}
```

### All writable fields:
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `invoiceDate` | string | **Yes** | YYYY-MM-DD |
| `invoiceDueDate` | string | **Yes** | YYYY-MM-DD |
| `orders` | array | **Yes** | `[{"id": N}]` or inline order objects |
| `invoiceNumber` | integer | No | 0 = auto-generate |
| `comment` | string | No | |
| `currency` | `{"id": N}` | No | |
| `kid` | string | No | KID payment reference |
| `customer` | `{"id": N}` | No | Usually from order |
| `paymentTypeId` | integer | No | For prepaid |
| `paidAmount` | number | No | For prepaid |

---

## Action: Register Payment

**Endpoint:** `PUT /invoice/{id}/:payment`

All params are **query parameters** (no request body):

```
PUT /invoice/{id}/:payment?paymentDate=2026-03-19&paymentTypeId=1&paidAmount=5000.00
```

| Param | Required | Notes |
|-------|----------|-------|
| `paymentDate` | **Yes** | YYYY-MM-DD |
| `paymentTypeId` | **Yes** | Get from `GET /invoice/paymentType` |
| `paidAmount` | **Yes** | Amount in payment type currency |
| `paidAmountCurrency` | No | Amount in invoice currency (required for foreign currency invoices) |

---

## Action: Create Credit Note

**Endpoint:** `PUT /invoice/{id}/:createCreditNote`

All params are **query parameters** (no request body):

```
PUT /invoice/{id}/:createCreditNote?date=2026-03-19
```

| Param | Required | Notes |
|-------|----------|-------|
| `date` | **Yes** | YYYY-MM-DD |
| `comment` | No | Credit note comment |
| `sendToCustomer` | No | |
| `creditNoteEmail` | No | Override email |

---

## Action: Send Invoice

**Endpoint:** `PUT /invoice/{id}/:send`

```
PUT /invoice/{id}/:send?sendType=EMAIL
```

| Param | Required | Notes |
|-------|----------|-------|
| `sendType` | **Yes** | `EMAIL`, `EHF`, `EFAKTURA`, `PAPER` etc. |
| `overrideEmailAddress` | No | Override recipient |

---

## Entity: Travel Expense

**Endpoint:** `POST /travelExpense`

### Minimum required payload:
```json
{
  "employee": {"id": 1}
}
```

### With travel details:
```json
{
  "employee": {"id": 1},
  "title": "Kundebesøk Oslo",
  "travelDetails": {
    "isForeignTravel": false,
    "isDayTrip": true,
    "departureDate": "2026-03-19",
    "returnDate": "2026-03-19",
    "departureFrom": "Stavanger",
    "destination": "Oslo",
    "departureTime": "07:00",
    "returnTime": "18:00",
    "purpose": "Kundemøte"
  },
  "isChargeable": false,
  "isFixedInvoicedAmount": false
}
```

### With costs:
```json
{
  "employee": {"id": 1},
  "title": "Kundebesøk",
  "travelDetails": {
    "isForeignTravel": false,
    "isDayTrip": true,
    "departureDate": "2026-03-19",
    "returnDate": "2026-03-19",
    "departureFrom": "Oslo",
    "destination": "Bergen",
    "departureTime": "08:00",
    "returnTime": "18:00",
    "purpose": "Møte"
  },
  "costs": [
    {
      "paymentType": {"id": PAYMENT_TYPE_ID},
      "date": "2026-03-19",
      "costCategory": {"id": COST_CATEGORY_ID},
      "amountCurrencyIncVat": 350.00
    }
  ]
}
```

### With mileage allowance:
```json
{
  "employee": {"id": 1},
  "travelDetails": { ... },
  "mileageAllowances": [
    {
      "rateType": {"id": RATE_TYPE_ID},
      "date": "2026-03-19",
      "departureLocation": "Oslo",
      "destination": "Bergen",
      "km": 463
    }
  ]
}
```

### With per diem compensation:
```json
{
  "employee": {"id": 1},
  "travelDetails": { ... },
  "perDiemCompensations": [
    {
      "rateType": {"id": RATE_TYPE_ID},
      "count": 1,
      "location": "Bergen"
    }
  ]
}
```

### With accommodation allowance:
```json
{
  "employee": {"id": 1},
  "travelDetails": { ... },
  "accommodationAllowances": [
    {
      "rateType": {"id": RATE_TYPE_ID},
      "count": 1,
      "location": "Bergen"
    }
  ]
}
```

### All writable fields:
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `employee` | `{"id": N}` | **Yes** | |
| `title` | string | No | |
| `travelDetails` | TravelDetails | No | But needed for most tasks |
| `project` | `{"id": N}` | No | |
| `department` | `{"id": N}` | No | |
| `isChargeable` | boolean | No | |
| `isFixedInvoicedAmount` | boolean | No | |
| `travelAdvance` | number | No | |
| `costs` | array:Cost | No | Inline costs |
| `perDiemCompensations` | array | No | Inline per diem |
| `mileageAllowances` | array | No | Create separately after |
| `accommodationAllowances` | array | No | Create separately after |

### TravelDetails fields:
| Field | Type | Notes |
|-------|------|-------|
| `isForeignTravel` | boolean | |
| `isDayTrip` | boolean | |
| `departureDate` | string | YYYY-MM-DD |
| `returnDate` | string | YYYY-MM-DD |
| `departureFrom` | string | Location name |
| `destination` | string | Location name |
| `departureTime` | string | HH:mm |
| `returnTime` | string | HH:mm |
| `purpose` | string | |

### Cost fields:
| Field | Type | Notes |
|-------|------|-------|
| `paymentType` | `{"id": N}` | Get from `GET /travelExpense/paymentType` |
| `date` | string | YYYY-MM-DD |
| `costCategory` | `{"id": N}` | Get from `GET /travelExpense/costCategory` |
| `amountCurrencyIncVat` | number | Amount including VAT |
| `currency` | `{"id": N}` | Default: company currency |
| `vatType` | `{"id": N}` | |
| `comments` | string | |

### MileageAllowance fields:
| Field | Type | Notes |
|-------|------|-------|
| `rateType` | `{"id": N}` | Get from `GET /travelExpense/rate` |
| `date` | string | YYYY-MM-DD |
| `departureLocation` | string | |
| `destination` | string | |
| `km` | number | Kilometers driven |
| `isCompanyCar` | boolean | |

### PerDiemCompensation fields:
| Field | Type | Notes |
|-------|------|-------|
| `rateType` | `{"id": N}` | Get from `GET /travelExpense/rate` |
| `count` | integer | Number of days |
| `location` | string | |
| `overnightAccommodation` | string | |
| `isDeductionForBreakfast` | boolean | |
| `isDeductionForLunch` | boolean | |
| `isDeductionForDinner` | boolean | |

### AccommodationAllowance fields:
| Field | Type | Notes |
|-------|------|-------|
| `rateType` | `{"id": N}` | Get from `GET /travelExpense/rate` |
| `count` | integer | Number of nights |
| `location` | string | |

---

## Entity: Voucher (Journal Entry)

**Endpoint:** `POST /ledger/voucher?sendToLedger=true`

### Minimum required payload:
```json
{
  "date": "2026-03-19",
  "description": "Office supplies",
  "postings": [
    {
      "account": {"id": 6300},
      "amountGross": 1000.00,
      "amountGrossCurrency": 1000.00
    },
    {
      "account": {"id": 1920},
      "amountGross": -1000.00,
      "amountGrossCurrency": -1000.00
    }
  ]
}
```

**CRITICAL:** Postings must **balance to zero** (sum of all `amountGross` = 0).
**CRITICAL:** Only **gross amounts** are used. Round to **2 decimals**.

### All writable fields (Voucher):
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `date` | string | **Yes** | YYYY-MM-DD |
| `description` | string | No | |
| `postings` | array | **Yes** | Must balance to 0 |
| `voucherType` | `{"id": N}` | No | |

### Posting fields:
| Field | Type | Likely Required | Notes |
|-------|------|----------------|-------|
| `account` | `{"id": N}` | **Yes** | Ledger account |
| `amountGross` | number | **Yes** | In company currency |
| `amountGrossCurrency` | number | **Yes** | In specified currency |
| `description` | string | No | |
| `customer` | `{"id": N}` | No | |
| `supplier` | `{"id": N}` | No | |
| `employee` | `{"id": N}` | No | |
| `project` | `{"id": N}` | No | |
| `department` | `{"id": N}` | No | |
| `vatType` | `{"id": N}` | No | |
| `currency` | `{"id": N}` | No | |
| `date` | string | No | |

---

## Entity: Supplier

**Endpoint:** `POST /supplier`

### Minimum required payload:
```json
{
  "name": "Leverandør AS"
}
```

### Recommended payload:
```json
{
  "name": "Leverandør AS",
  "postalAddress": {
    "addressLine1": "Gata 1",
    "postalCode": "0001",
    "city": "Oslo"
  }
}
```

---

## Reference Data Lookups

These endpoints return IDs needed for creating entities. **Call these first to get valid IDs.**

### VAT Types
```
GET /ledger/vatType
```
Common Norwegian VAT types (IDs may vary per sandbox):
| ID | Number | Name | Rate |
|----|--------|------|------|
| 3 | 3 | Utgående mva. høy sats | 25% |
| 5 | 5 | Utgående mva. middels sats | 15% |
| 6 | 6 | Utgående mva. lav sats | 12% |
| 0 | 0 | Ingen mva. | 0% |

### Invoice Payment Types
```
GET /invoice/paymentType
```
Returns payment types with IDs for use in `PUT /invoice/{id}/:payment`.

### Travel Expense Payment Types
```
GET /travelExpense/paymentType
```
Returns payment types for travel expense costs.

### Travel Expense Cost Categories
```
GET /travelExpense/costCategory
```
Returns cost categories (e.g., meals, transport, accommodation).

### Travel Expense Rate Types
```
GET /travelExpense/rate
```
Returns rate types for mileage, per diem, and accommodation allowances.

### Currencies
```
GET /currency
```
Common: NOK (id=1 usually), EUR, USD, SEK, DKK, GBP.

### Product Units
```
GET /product/unit
```
Returns units like stk (pieces), timer (hours), kg, etc.

### Ledger Accounts
```
GET /ledger/account
```
Norwegian standard chart of accounts (NS 4102). Common:
| Number | Description |
|--------|-------------|
| 1500 | Kundefordringer (Accounts receivable) |
| 1920 | Bankinnskudd (Bank deposits) |
| 3000 | Salgsinntekt (Sales revenue) |
| 6300 | Kontorrekvisita (Office supplies) |
| 6800 | Reisekostnad (Travel expense) |

### Employees (for self-reference)
```
GET /employee?fields=id,firstName,lastName
```
Need employee IDs for project manager, travel expense owner, etc.

---

## Common Schema: Address

Used in Employee, Customer, Supplier entities.

```json
{
  "addressLine1": "Storgata 1",
  "addressLine2": "",
  "postalCode": "0001",
  "city": "Oslo"
}
```

## Common Schema: DeliveryAddress

Same as Address plus `name` field:
```json
{
  "name": "Lager Oslo",
  "addressLine1": "Industrivegen 5",
  "postalCode": "0580",
  "city": "Oslo"
}
```

---

## Workflow Recipes

### Recipe: Create customer → Create order → Invoice → Payment

```
1. POST /customer           → get customer.id
2. POST /product            → get product.id (or reuse existing)
3. POST /order              → get order.id (include orderLines)
4. PUT  /order/{id}/:invoice?invoiceDate=2026-03-19  → get invoice.id
5. PUT  /invoice/{id}/:payment?paymentDate=2026-03-19&paymentTypeId=X&paidAmount=Y
```

### Recipe: Create credit note

```
1. GET  /invoice?invoiceDateFrom=...&invoiceDateTo=...  → find invoice.id
2. PUT  /invoice/{id}/:createCreditNote?date=2026-03-19
```

### Recipe: Create employee with department

```
1. POST /department          → get department.id (or find existing)
2. POST /employee            → include {"department": {"id": N}}
```

### Recipe: Travel expense with mileage

```
1. GET  /travelExpense/rate  → find mileage rateType.id
2. POST /travelExpense       → include employee, travelDetails, mileageAllowances
```

### Recipe: Add order line to existing order

```
POST /order/orderline
{
  "order": {"id": ORDER_ID},
  "product": {"id": PRODUCT_ID},
  "count": 5,
  "unitPriceExcludingVatCurrency": 500.00
}
```

---

## Discovery Strategy for the Executor

On startup (or first request), fetch and cache these reference data:
```python
DISCOVERY_ENDPOINTS = [
    "/ledger/vatType",           # VAT type IDs
    "/currency",                 # Currency IDs
    "/invoice/paymentType",      # Payment type IDs
    "/travelExpense/paymentType",# Travel payment type IDs
    "/travelExpense/costCategory",# Cost category IDs
    "/travelExpense/rate",       # Rate type IDs
    "/product/unit",             # Product unit IDs
    "/employee?count=100",       # Employee IDs
    "/department?count=100",     # Department IDs
]
```

Cache these in memory — they rarely change during the competition.

---

## Python httpx Code Snippets

### Base Client Setup

```python
import httpx

class TripletexClient:
    def __init__(self, base_url: str, session_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth = ("0", session_token)
        self.headers = {"Content-Type": "application/json"}

    async def _post(self, path: str, payload: dict, params: dict | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}{path}",
                json=payload,
                params=params,
                auth=self.auth,
                headers=self.headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def _put(self, path: str, payload: dict | None = None, params: dict | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{self.base_url}{path}",
                json=payload,
                params=params,
                auth=self.auth,
                headers=self.headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}{path}",
                params=params,
                auth=self.auth,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()
```

### Create Employee

```python
async def create_employee(self, first_name: str, last_name: str, **kwargs) -> dict:
    payload = {"firstName": first_name, "lastName": last_name}
    if "email" in kwargs:
        payload["email"] = kwargs["email"]
    if "date_of_birth" in kwargs:
        payload["dateOfBirth"] = kwargs["date_of_birth"]
    if "department_id" in kwargs:
        payload["department"] = {"id": kwargs["department_id"]}
    if "address" in kwargs:
        payload["address"] = kwargs["address"]  # {addressLine1, postalCode, city}
    return await self._post("/employee", payload)
```

### Create Customer

```python
async def create_customer(self, name: str, **kwargs) -> dict:
    payload = {"name": name}
    if "email" in kwargs:
        payload["email"] = kwargs["email"]
    if "organization_number" in kwargs:
        payload["organizationNumber"] = kwargs["organization_number"]
    if "invoice_email" in kwargs:
        payload["invoiceEmail"] = kwargs["invoice_email"]
    if "postal_address" in kwargs:
        payload["postalAddress"] = kwargs["postal_address"]
    if "phone_number" in kwargs:
        payload["phoneNumber"] = kwargs["phone_number"]
    if "is_private_individual" in kwargs:
        payload["isPrivateIndividual"] = kwargs["is_private_individual"]
    return await self._post("/customer", payload)
```

### Create Product

```python
async def create_product(self, name: str, **kwargs) -> dict:
    payload = {"name": name}
    if "price" in kwargs:
        payload["priceExcludingVatCurrency"] = kwargs["price"]
    if "vat_type_id" in kwargs:
        payload["vatType"] = {"id": kwargs["vat_type_id"]}
    if "number" in kwargs:
        payload["number"] = kwargs["number"]
    return await self._post("/product", payload)
```

### Create Order + Invoice (full flow)

```python
async def create_order_and_invoice(
    self,
    customer_id: int,
    order_date: str,
    delivery_date: str,
    order_lines: list[dict],
    invoice_date: str | None = None,
    due_date: str | None = None,
    send_to_customer: bool = False,
) -> dict:
    # 1. Create order
    order_payload = {
        "customer": {"id": customer_id},
        "orderDate": order_date,
        "deliveryDate": delivery_date,
        "orderLines": order_lines,
    }
    order_resp = await self._post("/order", order_payload)
    order_id = order_resp["value"]["id"]

    # 2. Create invoice from order
    inv_date = invoice_date or order_date
    params = {
        "invoiceDate": inv_date,
        "sendToCustomer": str(send_to_customer).lower(),
    }
    invoice_resp = await self._put(f"/order/{order_id}/:invoice", params=params)
    return invoice_resp
```

### Register Payment

```python
async def register_payment(
    self,
    invoice_id: int,
    payment_date: str,
    payment_type_id: int,
    paid_amount: float,
    paid_amount_currency: float | None = None,
) -> dict:
    params = {
        "paymentDate": payment_date,
        "paymentTypeId": payment_type_id,
        "paidAmount": paid_amount,
    }
    if paid_amount_currency is not None:
        params["paidAmountCurrency"] = paid_amount_currency
    return await self._put(f"/invoice/{invoice_id}/:payment", params=params)
```

### Create Credit Note

```python
async def create_credit_note(
    self,
    invoice_id: int,
    date: str,
    comment: str | None = None,
) -> dict:
    params = {"date": date}
    if comment:
        params["comment"] = comment
    return await self._put(f"/invoice/{invoice_id}/:createCreditNote", params=params)
```

### Create Department

```python
async def create_department(self, name: str, **kwargs) -> dict:
    payload = {"name": name}
    if "department_number" in kwargs:
        payload["departmentNumber"] = kwargs["department_number"]
    if "manager_id" in kwargs:
        payload["departmentManager"] = {"id": kwargs["manager_id"]}
    return await self._post("/department", payload)
```

### Create Project

```python
async def create_project(self, name: str, project_manager_id: int, **kwargs) -> dict:
    payload = {
        "name": name,
        "projectManager": {"id": project_manager_id},
    }
    if "customer_id" in kwargs:
        payload["customer"] = {"id": kwargs["customer_id"]}
    if "start_date" in kwargs:
        payload["startDate"] = kwargs["start_date"]
    if "end_date" in kwargs:
        payload["endDate"] = kwargs["end_date"]
    if "is_internal" in kwargs:
        payload["isInternal"] = kwargs["is_internal"]
    if "department_id" in kwargs:
        payload["department"] = {"id": kwargs["department_id"]}
    return await self._post("/project", payload)
```

### Create Travel Expense

```python
async def create_travel_expense(self, employee_id: int, **kwargs) -> dict:
    payload = {"employee": {"id": employee_id}}
    if "title" in kwargs:
        payload["title"] = kwargs["title"]
    if "project_id" in kwargs:
        payload["project"] = {"id": kwargs["project_id"]}
    if "department_id" in kwargs:
        payload["department"] = {"id": kwargs["department_id"]}
    if "travel_details" in kwargs:
        payload["travelDetails"] = kwargs["travel_details"]
    if "costs" in kwargs:
        payload["costs"] = kwargs["costs"]
    if "mileage_allowances" in kwargs:
        payload["mileageAllowances"] = kwargs["mileage_allowances"]
    if "per_diem_compensations" in kwargs:
        payload["perDiemCompensations"] = kwargs["per_diem_compensations"]
    if "is_chargeable" in kwargs:
        payload["isChargeable"] = kwargs["is_chargeable"]
    return await self._post("/travelExpense", payload)
```

---

## Validation Rules & Gotchas

### Critical Rules

1. **OpenAPI spec marks NO fields as `required`** — server-side validation determines requirements. The minimum payloads above are derived from official examples and testing.

2. **Object references use `{"id": N}` format** — when referencing an existing entity (customer, employee, department, etc.), only provide the `id`. Do NOT include other fields in the reference object.

3. **Version field for updates** — every `PUT` request requires the current `version` field. Fetch the entity first with `GET`, then include `version` in your payload. Mismatch = HTTP 409 Conflict.

4. **VAT price consistency** — if `isPrioritizeAmountsIncludingVat: true` on an order, ALL order lines must use `unitPriceIncludingVatCurrency`. Mixing `unitPriceExcludingVatCurrency` with this flag causes validation error: *"The unit price must be exclusive VAT since the unit price on the order is exclusive VAT."*

5. **Invoice creation from order** — `PUT /order/{id}/:invoice` uses **query parameters only**, no request body. The most important param is `invoiceDate`.

6. **Payment registration** — `PUT /invoice/{id}/:payment` also uses **query parameters only**. All of `paymentDate`, `paymentTypeId`, `paidAmount` are required.

7. **Credit note creation** — `PUT /invoice/{id}/:createCreditNote` uses **query parameters only**. `date` is required.

8. **Postings must balance** — when creating vouchers, the sum of all `amountGross` values must equal zero.

9. **Gross amounts only for vouchers** — use `amountGross` and `amountGrossCurrency`, not `amount`. Round to 2 decimals.

10. **Address IDs for updates** — when updating an entity with addresses (customer, supplier, employee), include the address `id` in the address object. Creating new = omit `id`. Updating existing = include `id`.

11. **Delivery address updates** — for customers/suppliers, delivery addresses must be updated via `PUT /address/{id}`, not through the parent entity update.

12. **`sendToCustomer` defaults** — `PUT /order/{id}/:invoice` defaults `sendToCustomer=true`. Always set `sendToCustomer=false` unless you explicitly want to email the invoice.

### Common Error Causes

| Error Code | HTTP | Meaning | Common Cause |
|------------|------|---------|--------------|
| 4000 | 400 | Bad Request | Malformed JSON, missing required fields |
| 6000 | 404 | Not Found | Invalid ID reference (customer, employee, etc.) |
| 7000 | 409 | Conflict | Version mismatch on PUT |
| 9000 | 403 | Forbidden | Missing module/permission |
| 15000 | 422 | Value Validation | Invalid field value (wrong type, out of range) |
| 18000 | 422 | Validation | Business rule violation |

### Prerequisites by Entity

| Entity | Prerequisites |
|--------|--------------|
| Employee | None — can be created standalone |
| Customer | None — can be created standalone |
| Product | None — can be created standalone (vatType optional, defaults to company default) |
| Department | None — can be created standalone |
| Project | Needs at least 1 employee (for `projectManager`) |
| Contact | Needs a customer (for `customer` ref) |
| Order | Needs a customer. Product optional (can use freetext lines with `description` + `vatType`) |
| Invoice (via order) | Needs an order |
| Invoice (direct POST) | Needs a customer + order lines (inline or existing order) |
| Payment | Needs an invoice + payment type ID |
| Credit Note | Needs an invoice |
| Travel Expense | Needs an employee |
| Travel Expense Cost | Needs a travel expense + payment type ID + cost category ID |
| Voucher | Needs valid ledger account IDs |

### ID Discovery Order

For the competition, always discover/create entities in this order:
```
1. GET /employee           → get default employee ID (for projectManager, travel expense)
2. GET /ledger/vatType     → cache VAT type IDs
3. GET /currency           → cache currency IDs (NOK = usually 1)
4. GET /invoice/paymentType → cache payment type IDs
5. GET /travelExpense/paymentType → cache travel payment type IDs
6. GET /travelExpense/costCategory → cache cost category IDs
7. GET /travelExpense/rate  → cache rate type IDs for mileage/per diem
8. GET /product/unit        → cache product unit IDs
```

Then create entities as needed by the task, always checking if they already exist first via `GET` with search params.

---

## Field Name Mapping (Norwegian → API)

For the NLP parser — map Norwegian terms to API field names:

| Norwegian | English | API Field | Entity |
|-----------|---------|-----------|--------|
| fornavn | first name | `firstName` | Employee |
| etternavn | last name | `lastName` | Employee |
| e-post | email | `email` | Employee/Customer |
| fødselsdato | date of birth | `dateOfBirth` | Employee |
| telefon | phone | `phoneNumber` | Customer |
| mobil | mobile | `phoneNumberMobile` | Employee/Customer |
| kunde | customer | `customer` | Order/Project |
| avdeling | department | `department` | Many |
| prosjekt | project | `project` | Order/TravelExpense |
| prosjektleder | project manager | `projectManager` | Project |
| faktura | invoice | — | Invoice |
| ordre | order | — | Order |
| leveringsdato | delivery date | `deliveryDate` | Order |
| ordredato | order date | `orderDate` | Order |
| forfallsdato | due date | `invoiceDueDate` | Invoice |
| antall | quantity/count | `count` | OrderLine |
| pris | price | `unitPriceExcludingVatCurrency` | OrderLine |
| mva | VAT | `vatType` | OrderLine/Product |
| beløp | amount | `paidAmount` / `amountGross` | Payment/Voucher |
| reise | travel | — | TravelExpense |
| utgift | expense/cost | — | TravelExpense |
| kjøregodtgjørelse | mileage allowance | `mileageAllowances` | TravelExpense |
| diett | per diem | `perDiemCompensations` | TravelExpense |
| overnatting | accommodation | `accommodationAllowances` | TravelExpense |
| adresse | address | `address` / `postalAddress` | Employee/Customer |
| postnummer | postal code | `postalCode` | Address |
| poststed/by | city | `city` | Address |
| organisasjonsnummer | org number | `organizationNumber` | Customer |
| kontonummer | bank account | `bankAccountNumber` | Employee |
| ansattnummer | employee number | `employeeNumber` | Employee |
| avdelingsnummer | department number | `departmentNumber` | Department |
| produktnummer | product number | `number` | Product |
| beskrivelse | description | `description` | Many |
| kommentar | comment | `comment` / `invoiceComment` | Invoice/Order |
| rabatt | discount | `discount` / `discountPercentage` | OrderLine/Customer |
| valuta | currency | `currency` | Many |
| betaling | payment | — | Payment |
| kreditnota | credit note | — | CreditNote |
