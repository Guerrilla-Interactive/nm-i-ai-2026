# Tripletex Sandbox API — Deep-Dive Reference

> Comprehensive research for NM i AI 2026. Covers every relevant endpoint, auth flow, data model, and API convention.
> Source: OpenAPI spec v2.75.00 from `tripletex.no/v2/openapi.json` (548 endpoints total)

---

## Table of Contents

1. [Environment & URLs](#environment--urls)
2. [Authentication](#authentication)
3. [API Conventions](#api-conventions)
4. [Rate Limiting](#rate-limiting)
5. [Pagination, Filtering & Sorting](#pagination-filtering--sorting)
6. [Response Envelopes](#response-envelopes)
7. [Endpoint Groups](#endpoint-groups)
   - [Token](#token)
   - [Employee](#employee)
   - [Customer](#customer)
   - [Product](#product)
   - [Invoice](#invoice)
   - [Order](#order)
   - [Project](#project)
   - [Department](#department)
   - [Contact](#contact)
   - [Activity](#activity)
   - [Timesheet](#timesheet)
   - [Travel Expense](#travel-expense)
   - [Salary](#salary)
   - [Ledger & Voucher](#ledger--voucher)
   - [Bank & Payment](#bank--payment)
   - [Currency](#currency)
   - [Supplier](#supplier)
   - [Purchase Order](#purchase-order)
   - [Incoming Invoice](#incoming-invoice)
   - [Events / Webhooks](#events--webhooks)
   - [Document Archive](#document-archive)
   - [Company](#company)
8. [Common Schemas](#common-schemas)
9. [Complete Endpoint Index](#complete-endpoint-index)
10. [Sandbox-Specific Notes](#sandbox-specific-notes)

---

## Environment & URLs

| Environment | Base URL | Swagger UI |
|---|---|---|
| **Sandbox (test)** | `https://api-test.tripletex.tech/v2` | `https://api-test.tripletex.tech/v2-docs/` |
| **Our sandbox** | `https://kkpqfuj-amager.tripletex.dev/v2` | `https://kkpqfuj-amager.tripletex.dev/v2-docs/` |
| **Production** | `https://tripletex.no/v2` | `https://tripletex.no/v2-docs/` |

- OpenAPI spec: `{base}/openapi.json` (NOT swagger.json)
- Test accounts **cannot** be used in production (different credential sets)
- Old test URL `api.tripletex.io` is deprecated; use `api-test.tripletex.tech`
- GitHub repo: https://github.com/Tripletex/tripletex-api2

---

## Authentication

### Three Token Types

| Token | Purpose | How to get |
|---|---|---|
| **consumerToken** | Identifies the API integration/app | Provided by Tripletex after API registration |
| **employeeToken** | Identifies the end-user (employee) | Created by admin in Tripletex UI → "API access" settings |
| **sessionToken** | Used for actual API calls | Created via `/token/session/:create` from consumer + employee tokens |

### Creating a Session Token

```
PUT /token/session/:create?consumerToken=CONSUMER&employeeToken=EMPLOYEE&expirationDate=2026-09-01
```

**Query Parameters:**
| Param | Required | Type | Description |
|---|---|---|---|
| `consumerToken` | Yes | string | The consumer (app) token |
| `employeeToken` | Yes | string | The employee token |
| `expirationDate` | Yes | string (YYYY-MM-DD) | When the session expires. **Max 6 months from now.** |

**Response:**
```json
{
  "value": {
    "id": 12345,
    "version": 0,
    "consumerToken": { "id": 67890 },
    "employeeToken": { "id": 11111 },
    "expirationDate": "2026-09-01",
    "token": "eyJhb...actual-session-token...",
    "encryptionKey": null
  }
}
```

### Using the Session Token (Basic Auth)

All API calls use HTTP Basic Authentication:
- **Username**: `0` (or target company ID; 0 = employee's own company)
- **Password**: the session token string

```bash
# Create session token
SESSION=$(curl -s -X PUT \
  "https://api-test.tripletex.tech/v2/token/session/:create?consumerToken=CONSUMER&employeeToken=EMPLOYEE&expirationDate=2026-09-01" \
  | jq -r '.value.token')

# Use it
curl -u "0:$SESSION" "https://api-test.tripletex.tech/v2/employee?fields=id,firstName,lastName"
```

**Header format:**
```
Authorization: Basic base64("0:SESSION_TOKEN")
```

### Session Token Expiry Rules

- Max expiry: **6 months** from creation date (enforced by API)
- Error if exceeded: `"Expiration date is not allowed to be older than 6 months."`
- This limit was briefly reverted but will be re-enforced

### Other Token Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/token/session/>whoAmI` | GET | Info about current authenticated user/company |
| `/token/session/{token}` | DELETE | Invalidate/delete a session token |
| `/token/consumer/byToken` | GET | Look up consumer token details |
| `/token/employee/:create` | PUT | Create employee token (requires consumer token with this privilege) |

---

## API Conventions

### HTTP Methods
- **GET** — Read/search
- **POST** — Create new resources
- **PUT** — Update existing resources (partial updates — NOT PATCH)
- **DELETE** — Delete resources

### Special Path Notation
- `:` prefix = **action/command** (e.g., `/hours/123/:approve`)
- `>` prefix = **summary/aggregation** (e.g., `/hours/>thisWeeksBillables`)

### Date/Time Formats
- Dates: `YYYY-MM-DD` (ISO 8601)
- DateTime: `YYYY-MM-DDThh:mm:ss` (ISO 8601)

### Versioning / Optimistic Locking
Every resource has a `version` field (integer). When updating:
1. Read the resource (get current `version`)
2. Send update with same `version`
3. Server rejects if version mismatch (409 Conflict)

### Request ID
Every response includes header `x-tlx-request-id` for debugging/support.

### References to Other Objects
Use `{"id": 123}` to reference related objects:
```json
{
  "customer": {"id": 42},
  "department": {"id": 5},
  "currency": {"id": 1}
}
```

---

## Rate Limiting

**Response Headers:**
| Header | Description |
|---|---|
| `X-Rate-Limit-Limit` | Max requests allowed in current period |
| `X-Rate-Limit-Remaining` | Requests remaining in current period |
| `X-Rate-Limit-Reset` | Seconds until the rate limit resets |

When exceeded: **HTTP 429 Too Many Requests**

---

## Pagination, Filtering & Sorting

### Pagination
All list endpoints support:
| Param | Type | Default | Description |
|---|---|---|---|
| `from` | integer | 0 | Offset (skip N results) |
| `count` | integer | varies | Max results to return |

Response envelope includes `fullResultSize` for total count.

### Field Selection
```
GET /customer?fields=id,name,email,postalAddress(city,postalCode)
```
- Comma-separated field names
- Nested fields via parentheses: `project(name,number)`
- Use `*` for all fields at a level
- Special `changes` field returns CREATE/UPDATE audit history

### Sorting
```
GET /customer?sorting=name,-id
```
- Comma-separated field names
- `-` prefix for descending

### Search Filters
Each endpoint has specific filter parameters. Common patterns:
- Exact match: `customerId=42`
- Range: `dateFrom=2026-01-01&dateTo=2026-12-31`
- Text search: `name=Acme` (often like-matching)
- Boolean: `isInactive=false`
- Multi-value: `id=1,2,3` (comma-separated)

---

## Response Envelopes

### Single Resource
```json
{
  "value": {
    "id": 123,
    "version": 1,
    "url": "tripletex.no/v2/customer/123",
    "name": "Acme Corp",
    ...
  }
}
```

### List of Resources
```json
{
  "fullResultSize": 150,
  "from": 0,
  "count": 25,
  "versionDigest": "abc123",
  "values": [
    { "id": 1, ... },
    { "id": 2, ... }
  ]
}
```

### Error Response
```json
{
  "status": 400,
  "code": 4000,
  "message": "Human-readable error",
  "link": "",
  "developerMessage": "Technical details",
  "validationMessages": [
    { "field": "name", "message": "Name is required" }
  ],
  "requestId": "abc-123"
}
```

### HTTP Status Codes
| Code | Meaning | Error Codes |
|---|---|---|
| 200 | OK | — |
| 201 | Created | — |
| 204 | No Content (delete success) | — |
| 400 | Bad Request | 4000, 11000, 12000 |
| 401 | Unauthorized | 3000 |
| 403 | Forbidden | 9000 |
| 404 | Not Found | 6000 |
| 409 | Conflict (version mismatch) | 7000, 8000, 10000, 14000 |
| 422 | Validation Error | 15000–23000 |
| 429 | Rate Limited | — |
| 500 | Internal Server Error | 1000 |

---

## Endpoint Groups

### Token

| Method | Endpoint | Description |
|---|---|---|
| PUT/POST | `/token/session/:create` | Create session token |
| GET | `/token/session/>whoAmI` | Current user info |
| DELETE | `/token/session/{token}` | Delete session token |
| GET | `/token/consumer/byToken` | Consumer token details |
| PUT | `/token/employee/:create` | Create employee token |

---

### Employee

**Endpoints (26 total):**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/employee` | Search employees |
| POST | `/employee` | Create one employee |
| GET | `/employee/{id}` | Get employee by ID |
| PUT | `/employee/{id}` | Update employee |
| POST | `/employee/list` | Batch create employees |
| GET | `/employee/searchForEmployeesAndContacts` | Combined search |
| **Employment** | | |
| GET/POST | `/employee/employment` | Search/create employments |
| GET/PUT | `/employee/employment/{id}` | Get/update employment |
| GET/POST | `/employee/employment/details` | Employment details |
| GET/PUT | `/employee/employment/details/{id}` | Detail by ID |
| GET | `/employee/employment/employmentType` | Employment types |
| GET | `/employee/employment/employmentType/employmentEndReasonType` | End reason types |
| GET | `/employee/employment/employmentType/employmentFormType` | Form types |
| GET | `/employee/employment/employmentType/maritimeEmploymentType` | Maritime types |
| GET | `/employee/employment/employmentType/salaryType` | Salary types |
| GET | `/employee/employment/employmentType/scheduleType` | Schedule types |
| GET/POST | `/employee/employment/leaveOfAbsence` | Leave of absence |
| POST | `/employee/employment/leaveOfAbsence/list` | Batch create leave |
| GET/PUT | `/employee/employment/leaveOfAbsence/{id}` | Manage leave by ID |
| GET | `/employee/employment/leaveOfAbsenceType` | Leave types |
| GET | `/employee/employment/occupationCode` | Occupation codes |
| GET | `/employee/employment/remunerationType` | Remuneration types |
| GET | `/employee/employment/workingHoursScheme` | Working hours schemes |
| **Other** | | |
| GET/POST | `/employee/hourlyCostAndRate` | Hourly cost/rate |
| GET/PUT | `/employee/hourlyCostAndRate/{id}` | By ID |
| GET/POST | `/employee/category` | Employee categories |
| GET/PUT/DELETE | `/employee/category/{id}` | Category by ID |
| GET/POST | `/employee/standardTime` | Standard working time |
| GET | `/employee/standardTime/byDate` | Std time by date |
| GET/POST | `/employee/nextOfKin` | Next of kin |
| GET | `/employee/entitlement` | User entitlements |
| GET | `/employee/preferences` | Employee preferences |

**Employee Schema (full):**
| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | int64 | — | Auto-generated |
| `version` | int32 | — | For optimistic locking |
| `firstName` | string | — | |
| `lastName` | string | — | |
| `employeeNumber` | string | — | |
| `dateOfBirth` | string | — | YYYY-MM-DD |
| `email` | string | — | |
| `phoneNumberMobile` | string | — | |
| `phoneNumberMobileCountry` | ref:Country | — | |
| `phoneNumberHome` | string | — | |
| `phoneNumberWork` | string | — | |
| `nationalIdentityNumber` | string | — | Norwegian SSN (fødselsnummer) |
| `dnumber` | string | — | D-number (foreign workers) |
| `internationalId` | ref:InternationalId | — | |
| `bankAccountNumber` | string | — | Norwegian bank account |
| `iban` | string | — | International bank account |
| `bic` | string | — | SWIFT/BIC code |
| `creditorBankCountryId` | int32 | — | |
| `usesAbroadPayment` | boolean | — | Domestic vs international payment |
| `userType` | string | — | `STANDARD`, `EXTENDED`, `NO_ACCESS` |
| `isContact` | boolean | — | External contact (not employee) |
| `comments` | string | — | |
| `address` | ref:Address | — | |
| `department` | ref:Department | — | |
| `employments` | array:Employment | — | |
| `employeeCategory` | ref:EmployeeCategory | — | |
| `holidayAllowanceEarned` | ref:HolidayAllowanceEarned | — | |
| `allowInformationRegistration` | boolean | readonly | Can register salary info |
| `displayName` | string | readonly | |
| `isProxy` | boolean | readonly | Accounting/auditor office |
| `pictureId` | int32 | readonly | |
| `companyId` | int32 | readonly | |

**Search parameters:** `id`, `firstName`, `lastName`, `employeeNumber`, `email`, `allowInformationRegistration`, `includeContacts`, `departmentId`, `onlyProjectManagers`, `onlyContacts`, `assignableProjectManagers`, `periodStart`, `periodEnd`, `hasSystemAccess`, `onlyEmployeeTokens`

**Example — Create Employee:**
```json
POST /employee
{
  "firstName": "Ola",
  "lastName": "Nordmann",
  "email": "ola@example.com",
  "dateOfBirth": "1990-05-15",
  "address": {
    "addressLine1": "Storgata 1",
    "postalCode": "0001",
    "city": "Oslo"
  },
  "department": {"id": 1}
}
```

---

### Customer

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/customer` | Search customers |
| POST | `/customer` | Create customer (+ addresses) |
| GET | `/customer/{id}` | Get by ID |
| PUT | `/customer/{id}` | Update customer |
| DELETE | `/customer/{id}` | Delete customer |
| POST | `/customer/list` | Batch create |
| PUT | `/customer/list` | Batch update |
| GET/POST | `/customer/category` | Categories |
| GET/PUT | `/customer/category/{id}` | Category by ID |

**Customer Schema (full):**
| Field | Type | Notes |
|---|---|---|
| `id` | int64 | Auto-generated |
| `version` | int32 | |
| `name` | string | Company or person name |
| `organizationNumber` | string | Org number |
| `globalLocationNumber` | int64 | GLN |
| `supplierNumber` | int32 | If also a supplier |
| `customerNumber` | int32 | Auto-generated if omitted |
| `isSupplier` | boolean | Also a supplier? |
| `isCustomer` | boolean | readonly |
| `isInactive` | boolean | |
| `accountManager` | ref:Employee | |
| `department` | ref:Department | |
| `email` | string | Primary email |
| `invoiceEmail` | string | For invoice delivery |
| `overdueNoticeEmail` | string | For overdue notices |
| `bankAccounts` | array:string | |
| `phoneNumber` | string | |
| `phoneNumberMobile` | string | |
| `description` | string | |
| `language` | string | |
| `displayName` | string | |
| `isPrivateIndividual` | boolean | |
| `singleCustomerInvoice` | boolean | Multiple orders → 1 invoice |
| `invoiceSendMethod` | string | `EMAIL`, `EHF`, `EFAKTURA`, `AVTALEGIRO`, `VIPPS`, `PAPER`, `MANUAL` |
| `emailAttachmentType` | string | `LINK`, `ATTACHMENT` |
| `postalAddress` | ref:Address | |
| `physicalAddress` | ref:Address | |
| `deliveryAddress` | ref:DeliveryAddress | |
| `category1` | ref:CustomerCategory | |
| `category2` | ref:CustomerCategory | |
| `category3` | ref:CustomerCategory | |
| `invoicesDueIn` | int32 | Payment terms |
| `invoicesDueInType` | string | `DAYS`, `MONTHS`, `RECURRING_DAY_OF_MONTH` |
| `currency` | ref:Currency | |
| `ledgerAccount` | ref:Account | |
| `isFactoring` | boolean | Send to factoring |
| `invoiceSendSMSNotification` | boolean | |
| `isAutomaticSoftReminderEnabled` | boolean | |
| `isAutomaticReminderEnabled` | boolean | |
| `isAutomaticNoticeOfDebtCollectionEnabled` | boolean | |
| `discountPercentage` | number | Default discount |
| `website` | string | |

**Search parameters:** `id`, `customerAccountNumber`, `organizationNumber`, `email`, `invoiceEmail`, `customerName`, `phoneNumberMobile`, `isInactive`, `accountManagerId`, `changedSince`

**Example — Create Customer:**
```json
POST /customer
{
  "name": "Acme AS",
  "organizationNumber": "912345678",
  "email": "post@acme.no",
  "invoiceEmail": "faktura@acme.no",
  "invoiceSendMethod": "EMAIL",
  "invoicesDueIn": 30,
  "invoicesDueInType": "DAYS",
  "currency": {"id": 1},
  "postalAddress": {
    "addressLine1": "Storgata 1",
    "postalCode": "0001",
    "city": "Oslo"
  }
}
```

---

### Product

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/product` | Search products |
| POST | `/product` | Create product |
| GET | `/product/{id}` | Get by ID |
| PUT | `/product/{id}` | Update product |
| DELETE | `/product/{id}` | Delete product |
| PUT/POST | `/product/list` | Batch create/update |
| POST/DELETE | `/product/{id}/image` | Upload/delete product image |
| **Groups** | | |
| GET/POST | `/product/group` | Product groups |
| GET/PUT/DELETE | `/product/group/{id}` | Group by ID |
| PUT/POST/DELETE | `/product/group/list` | Batch group ops |
| GET | `/product/group/query` | Group search |
| **Group Relations** | | |
| GET/POST | `/product/groupRelation` | Group–product relations |
| POST/DELETE | `/product/groupRelation/list` | Batch relation ops |
| **Units** | | |
| GET/POST | `/product/unit` | Product units |
| GET/PUT/DELETE | `/product/unit/{id}` | Unit by ID |
| PUT/POST | `/product/unit/list` | Batch unit ops |
| GET | `/product/unit/master` | Master unit list |
| **Supplier Products** | | |
| GET/POST | `/product/supplierProduct` | Supplier products |
| GET/PUT/DELETE | `/product/supplierProduct/{id}` | By ID |
| PUT/POST | `/product/supplierProduct/list` | Batch ops |
| **Other** | | |
| GET | `/product/external` | External products |
| GET/POST | `/product/inventoryLocation` | Inventory locations |
| GET | `/product/productPrice` | Product prices |
| GET/PUT | `/product/logisticsSettings` | Logistics settings |
| GET | `/product/discountGroup` | Discount groups |

**Product Schema (full):**
| Field | Type | Notes |
|---|---|---|
| `id` | int64 | Auto-generated |
| `version` | int32 | |
| `name` | string | |
| `number` | string | Product number |
| `description` | string | |
| `orderLineDescription` | string | Description on order lines |
| `ean` | string | Barcode/EAN |
| `costExcludingVatCurrency` | number | Purchase cost excl. VAT |
| `expenses` | number | |
| `priceExcludingVatCurrency` | number | Sale price excl. VAT |
| `priceIncludingVatCurrency` | number | Sale price incl. VAT |
| `isInactive` | boolean | |
| `isStockItem` | boolean | Track inventory |
| `vatType` | ref:VatType | |
| `currency` | ref:Currency | |
| `productUnit` | ref:ProductUnit | |
| `department` | ref:Department | |
| `account` | ref:Account | |
| `supplier` | ref:Supplier | |
| `discountGroup` | ref:DiscountGroup | |
| `weight` | number | |
| `weightUnit` | string | |
| `volume` | number | |
| `volumeUnit` | string | |
| `hsnCode` | string | |
| `image` | ref:Document | |
| `minStockLevel` | number | Min stock (stock items only) |
| `stockOfGoods` | number | readonly, current stock |
| `availableStock` | number | readonly |
| `costPrice` | number | readonly |
| `profit` | number | readonly |
| `resaleProduct` | ref:Product | |
| `mainSupplierProduct` | ref:SupplierProduct | |

**Search parameters:** `number`, `ids`, `productNumber`, `name`, `ean`, `isInactive`, `isStockItem`, `isSupplierProduct`, `supplierId`, `currencyId`, `vatTypeId`, `productUnitId`, `departmentId`, `accountId`, `costExcludingVatCurrencyFrom/To`, `priceExcludingVatCurrencyFrom/To`, `priceIncludingVatCurrencyFrom/To`

**Example — Create Product:**
```json
POST /product
{
  "name": "Konsulenttime",
  "number": "1001",
  "priceExcludingVatCurrency": 1200.00,
  "vatType": {"id": 3},
  "currency": {"id": 1},
  "productUnit": {"id": 1}
}
```

---

### Invoice

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/invoice` | Search invoices (**requires** `invoiceDateFrom` + `invoiceDateTo`) |
| POST | `/invoice` | Create invoice (can embed orders + lines) |
| GET | `/invoice/{id}` | Get by ID |
| POST | `/invoice/list` | Batch create |
| PUT | `/invoice/{id}/:payment` | Register payment |
| PUT | `/invoice/{id}/:createCreditNote` | Create credit note |
| PUT | `/invoice/{id}/:createReminder` | Create reminder |
| PUT | `/invoice/{id}/:send` | Send invoice to customer |
| GET | `/invoice/{invoiceId}/pdf` | Download PDF |
| GET | `/invoice/details` | Invoice line details |
| GET | `/invoice/details/{id}` | Detail by ID |
| GET | `/invoice/paymentType` | Available payment types |
| GET | `/invoice/paymentType/{id}` | Payment type by ID |

**Create invoice query params:**
| Param | Type | Description |
|---|---|---|
| `sendToCustomer` | boolean | Send immediately |
| `paymentTypeId` | int | Payment type for prepaid |
| `paidAmount` | number | Prepaid amount |

**Invoice Schema (full):**
| Field | Type | Notes |
|---|---|---|
| `id` | int64 | Auto-generated |
| `version` | int32 | |
| `invoiceNumber` | int32 | 0 = auto-generate |
| `invoiceDate` | string | YYYY-MM-DD |
| `invoiceDueDate` | string | YYYY-MM-DD |
| `customer` | ref:Customer | **Required** |
| `orders` | array:Order | Related orders (1 per invoice currently) |
| `orderLines` | array:OrderLine | readonly |
| `comment` | string | Invoice-specific comment |
| `invoiceComment` | string | readonly, from order |
| `currency` | ref:Currency | |
| `kid` | string | KID (payment reference) |
| `voucher` | ref:Voucher | |
| `invoiceRemark` | ref:InvoiceRemark | |
| `paymentTypeId` | int32 | For prepaid invoices |
| `paidAmount` | number | Prepaid amount |
| `deliveryDate` | string | readonly |
| `amount` | number | readonly, total in NOK |
| `amountCurrency` | number | readonly, in specified currency |
| `amountExcludingVat` | number | readonly |
| `amountExcludingVatCurrency` | number | readonly |
| `amountOutstanding` | number | readonly, unpaid amount |
| `amountRoundoff` | number | readonly |
| `isCreditNote` | boolean | readonly |
| `isCharged` | boolean | readonly |
| `isApproved` | boolean | readonly |
| `postings` | array:Posting | readonly |
| `reminders` | array:Reminder | readonly |
| `ehfSendStatus` | string | deprecated |

**Search parameters (GET):** `id`, `invoiceDateFrom` (required), `invoiceDateTo` (required), `invoiceNumber`, `kid`, `voucherId`, `customerId`

**Example — Create Invoice from Order:**
```json
POST /invoice?sendToCustomer=false
{
  "invoiceDate": "2026-03-19",
  "invoiceDueDate": "2026-04-19",
  "orders": [{"id": 123}]
}
```

**Example — Create Invoice with inline lines:**
```json
POST /invoice?sendToCustomer=true
{
  "invoiceDate": "2026-03-19",
  "invoiceDueDate": "2026-04-19",
  "customer": {"id": 42},
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

---

### Order

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/order` | Search orders (**requires** `orderDateFrom` + `orderDateTo`) |
| POST | `/order` | Create order |
| GET | `/order/{id}` | Get by ID |
| PUT | `/order/{id}` | Update order |
| DELETE | `/order/{id}` | Delete order |
| POST | `/order/list` | Batch create |
| PUT | `/order/{id}/:invoice` | Create invoice from order |
| PUT | `/order/:invoiceMultipleOrders` | Invoice multiple orders at once |
| PUT | `/order/{id}/:attach` | Attach document |
| PUT | `/order/{id}/:approveSubscriptionInvoice` | Approve subscription |
| PUT | `/order/{id}/:unApproveSubscriptionInvoice` | Unapprove subscription |
| **Order Lines** | | |
| POST | `/order/orderline` | Create order line |
| POST | `/order/orderline/list` | Batch create lines |
| GET | `/order/orderline/orderLineTemplate` | Get line template |
| GET | `/order/orderline/{id}` | Get line by ID |
| PUT | `/order/orderline/{id}` | Update line |
| DELETE | `/order/orderline/{id}` | Delete line |
| PUT | `/order/orderline/{id}/:pickLine` | Pick line (logistics) |
| PUT | `/order/orderline/{id}/:unpickLine` | Unpick line |
| **PDFs & Communication** | | |
| GET | `/order/orderConfirmation/{orderId}/pdf` | Order confirmation PDF |
| GET | `/order/packingNote/{orderId}/pdf` | Packing note PDF |
| PUT | `/order/sendInvoicePreview/{orderId}` | Send invoice preview |
| PUT | `/order/sendOrderConfirmation/{orderId}` | Send order confirmation |
| PUT | `/order/sendPackingNote/{orderId}` | Send packing note |
| **Order Groups** | | |
| GET/PUT/POST | `/order/orderGroup` | Order groups |
| GET/DELETE | `/order/orderGroup/{id}` | Group by ID |

**Order Schema (full):**
| Field | Type | Notes |
|---|---|---|
| `id` | int64 | |
| `version` | int32 | |
| `customer` | ref:Customer | **Required** |
| `contact` | ref:Contact | |
| `attn` | ref:Contact | Attention person |
| `receiverEmail` | string | |
| `overdueNoticeEmail` | string | |
| `number` | string | |
| `reference` | string | |
| `ourContact` | ref:Contact | |
| `ourContactEmployee` | ref:Employee | |
| `department` | ref:Department | |
| `orderDate` | string | **Required for search** |
| `project` | ref:Project | |
| `invoiceComment` | string | Appears on invoice |
| `internalComment` | string | Internal only |
| `currency` | ref:Currency | |
| `invoicesDueIn` | int32 | |
| `invoicesDueInType` | string | `DAYS`, `MONTHS`, `RECURRING_DAY_OF_MONTH` |
| `isShowOpenPostsOnInvoices` | boolean | |
| `isClosed` | boolean | |
| `deliveryDate` | string | |
| `deliveryAddress` | ref:DeliveryAddress | |
| `deliveryComment` | string | |
| `isPrioritizeAmountsIncludingVat` | boolean | Use VAT-inclusive amounts |
| `orderLineSorting` | string | |
| `orderGroups` | array:OrderGroup | |
| `orderLines` | array:OrderLine | Embed on creation |
| `isSubscription` | boolean | |
| `subscriptionDuration` | int32 | |
| `subscriptionDurationType` | string | |
| `subscriptionPeriodsOnInvoice` | int32 | |
| `isSubscriptionAutoInvoicing` | boolean | |
| `markUpOrderLines` | number | Markup % for lines |
| `discountPercentage` | number | Default line discount |
| `invoiceOnAccountVatHigh` | boolean | VAT on a-konto |

**OrderLine Schema:**
| Field | Type | Notes |
|---|---|---|
| `product` | ref:Product | |
| `inventory` | ref:Inventory | |
| `description` | string | |
| `count` | number | Quantity |
| `unitCostCurrency` | number | Cost price excl. VAT |
| `unitPriceExcludingVatCurrency` | number | Sale price excl. VAT |
| `unitPriceIncludingVatCurrency` | number | Sale price incl. VAT |
| `currency` | ref:Currency | |
| `markup` | number | Markup % |
| `discount` | number | Discount % |
| `vatType` | ref:VatType | |
| `order` | ref:Order | |
| `orderGroup` | ref:OrderGroup | |
| `isSubscription` | boolean | |
| `subscriptionPeriodStart` | string | |
| `subscriptionPeriodEnd` | string | |

**Search parameters (GET):** `id`, `number`, `customerId`, `orderDateFrom` (required), `orderDateTo` (required), `deliveryComment`, `isClosed`, `isSubscription`

**Example — Create Order:**
```json
POST /order
{
  "customer": {"id": 42},
  "orderDate": "2026-03-19",
  "deliveryDate": "2026-03-25",
  "invoicesDueIn": 30,
  "invoicesDueInType": "DAYS",
  "orderLines": [
    {
      "product": {"id": 1},
      "count": 5,
      "unitPriceExcludingVatCurrency": 500.00
    },
    {
      "description": "Ekstra rådgivning",
      "count": 2,
      "unitPriceExcludingVatCurrency": 1200.00,
      "vatType": {"id": 3}
    }
  ]
}
```

**FAQ:** To use VAT-inclusive prices, set `isPrioritizeAmountsIncludingVat: true` and provide `unitPriceIncludingVatCurrency` on order lines.

---

### Project

**Endpoints (35+ total):**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/project` | Search projects |
| POST | `/project` | Create project |
| GET | `/project/{id}` | Get by ID |
| PUT | `/project/{id}` | Update project |
| DELETE | `/project/{id}` | Delete project |
| PUT/POST/DELETE | `/project/list` | Batch ops |
| POST | `/project/import` | Import projects |
| GET | `/project/number/{number}` | Get by project number |
| GET | `/project/>forTimeSheet` | Projects for timesheets |
| DELETE | `/project` | Batch delete |
| **Categories** | | |
| GET/POST | `/project/category` | Categories |
| GET/PUT | `/project/category/{id}` | Category by ID |
| **Hourly Rates** | | |
| GET/POST | `/project/hourlyRates` | Project hourly rates |
| GET/PUT/DELETE | `/project/hourlyRates/{id}` | By ID |
| PUT/POST/DELETE | `/project/hourlyRates/list` | Batch ops |
| GET/POST | `/project/hourlyRates/projectSpecificRates` | Project-specific rates |
| PUT | `/project/hourlyRates/updateOrAddHourRates` | Upsert rates |
| **Order Lines** | | |
| GET/POST | `/project/orderline` | Project order lines |
| POST | `/project/orderline/list` | Batch create |
| GET/PUT/DELETE | `/project/orderline/{id}` | By ID |
| **Participants** | | |
| POST | `/project/participant` | Add participant |
| POST/DELETE | `/project/participant/list` | Batch ops |
| GET/PUT | `/project/participant/{id}` | By ID |
| **Activities** | | |
| POST | `/project/projectActivity` | Create activity |
| GET/DELETE | `/project/projectActivity/{id}` | By ID |
| DELETE | `/project/projectActivity/list` | Batch delete |
| **Reports** | | |
| GET | `/project/{id}/period/budgetStatus` | Budget status |
| GET | `/project/{id}/period/hourlistReport` | Hour list |
| GET | `/project/{id}/period/invoiced` | Invoiced amounts |
| GET | `/project/{id}/period/invoicingReserve` | Invoicing reserve |
| GET | `/project/{id}/period/monthlyStatus` | Monthly status |
| GET | `/project/{id}/period/overallStatus` | Overall status |
| **Other** | | |
| GET/PUT | `/project/settings` | Project settings |
| GET/POST | `/project/subcontract` | Subcontracts |
| GET | `/project/task` | Tasks |
| GET | `/project/template/{id}` | Project template |

**Project Schema (key fields):**
| Field | Type | Notes |
|---|---|---|
| `name` | string | |
| `number` | string | Auto-generated if NULL |
| `description` | string | |
| `projectManager` | ref:Employee | |
| `department` | ref:Department | |
| `customer` | ref:Customer | |
| `mainProject` | ref:Project | Parent project |
| `startDate` | string | |
| `endDate` | string | |
| `isClosed` | boolean | |
| `isReadyForInvoicing` | boolean | |
| `isInternal` | boolean | |
| `isOffer` | boolean | Offer vs project |
| `isFixedPrice` | boolean | Fixed price vs hourly |
| `projectCategory` | ref:ProjectCategory | |
| `fixedprice` | number | |
| `currency` | ref:Currency | |
| `participants` | array:ProjectParticipant | |
| `projectActivities` | array:ProjectActivity | |
| `projectHourlyRates` | array:ProjectHourlyRate | |
| `forParticipantsOnly` | boolean | Only participants can register |
| `generalProjectActivitiesPerProjectOnly` | boolean | |
| `accessType` | string | `READ`, `WRITE` |
| `displayNameFormat` | string | |
| `reference` | string | |
| `externalAccountsNumber` | string | |
| `vatType` | ref:VatType | |
| `markUpOrderLines` | number | |
| `markUpFeesEarned` | number | |
| `isPriceCeiling` | boolean | |
| `priceCeilingAmount` | number | |
| `invoiceDueDate` | int32 | |
| `invoiceDueDateType` | string | |
| `invoiceReceiverEmail` | string | |
| `invoiceComment` | string | |

**Example — Create Project:**
```json
POST /project
{
  "name": "AI Consulting Project",
  "projectManager": {"id": 1},
  "customer": {"id": 42},
  "startDate": "2026-03-01",
  "endDate": "2026-12-31",
  "isFixedPrice": false,
  "projectCategory": {"id": 1}
}
```

---

### Department

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/department` | Search departments |
| POST | `/department` | Create department |
| GET | `/department/{id}` | Get by ID |
| PUT | `/department/{id}` | Update |
| DELETE | `/department/{id}` | Delete |
| PUT/POST | `/department/list` | Batch create/update |
| GET | `/department/query` | Wildcard search |

**Department Schema:**
| Field | Type | Notes |
|---|---|---|
| `id` | int64 | |
| `version` | int32 | |
| `name` | string | |
| `departmentNumber` | string | |
| `departmentManager` | ref:Employee | |
| `isInactive` | boolean | |
| `displayName` | string | readonly |

**Example:**
```json
POST /department
{
  "name": "Salg",
  "departmentNumber": "100",
  "departmentManager": {"id": 1}
}
```

---

### Contact

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/contact` | Search contacts |
| POST | `/contact` | Create contact |
| GET | `/contact/{id}` | Get by ID |
| PUT | `/contact/{id}` | Update |
| POST | `/contact/list` | Batch create |
| DELETE | `/contact/list` | Batch delete |

**Contact Schema:**
| Field | Type | Notes |
|---|---|---|
| `id` | int64 | |
| `firstName` | string | |
| `lastName` | string | |
| `displayName` | string | |
| `email` | string | |
| `phoneNumberMobile` | string | |
| `phoneNumberMobileCountry` | ref:Country | |
| `phoneNumberWork` | string | |
| `customer` | ref:Customer | Associated customer |
| `department` | ref:Department | |
| `isInactive` | boolean | |

**Search parameters:** `id`, `firstName`, `lastName`, `email`, `customerId`, `departmentId`

---

### Activity

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/activity` | Search activities |
| POST | `/activity` | Create activity |
| GET | `/activity/{id}` | Get by ID |
| POST | `/activity/list` | Batch create |
| GET | `/activity/>forTimeSheet` | Activities for timesheets (requires `projectId`) |

**Search parameters:** `id`, `name`, `number`, `description`, `isProjectActivity`, `isGeneral`, `isChargeable`, `isTask`, `isInactive`

---

### Timesheet

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET/POST | `/timesheet/entry` | Search/create entries |
| GET/PUT/DELETE | `/timesheet/entry/{id}` | By ID |
| PUT/POST | `/timesheet/entry/list` | Batch create/update |
| GET | `/timesheet/entry/>totalHours` | Total hours |
| GET | `/timesheet/entry/>recentProjects` | Recent projects |
| GET | `/timesheet/entry/>recentActivities` | Recent activities |
| **Month** | | |
| PUT | `/timesheet/month/:approve` | Approve month |
| PUT | `/timesheet/month/:complete` | Complete month |
| PUT | `/timesheet/month/:reopen` | Reopen month |
| PUT | `/timesheet/month/:unapprove` | Unapprove month |
| GET | `/timesheet/month/{id}` | Get month |
| GET | `/timesheet/month/byMonthNumber` | By month number |
| **Week** | | |
| GET | `/timesheet/week` | Get week |
| PUT | `/timesheet/week/:approve` | Approve week |
| PUT | `/timesheet/week/:complete` | Complete week |
| PUT | `/timesheet/week/:reopen` | Reopen week |
| **Time Clock** | | |
| GET | `/timesheet/timeClock` | Search time clocks |
| PUT | `/timesheet/timeClock/:start` | Start clock |
| PUT | `/timesheet/timeClock/{id}/:stop` | Stop clock |
| GET | `/timesheet/timeClock/present` | Currently present |
| **Other** | | |
| GET/POST | `/timesheet/allocated` | Allocated hours |
| GET/POST | `/timesheet/companyHoliday` | Company holidays |
| GET | `/timesheet/settings` | Settings |
| GET/POST | `/timesheet/salaryTypeSpecification` | Salary type spec |
| GET/POST | `/timesheet/salaryProjectTypeSpecification` | Salary project spec |

**TimesheetEntry Example:**
```json
POST /timesheet/entry
{
  "project": {"id": 123},
  "activity": {"id": 456},
  "employee": {"id": 1},
  "date": "2026-03-19",
  "hours": 7.5,
  "chargeableHours": 7.5,
  "chargeable": true
}
```

---

### Travel Expense

**Endpoints (40+ total):**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/travelExpense` | Search travel expenses |
| POST | `/travelExpense` | Create travel expense |
| GET | `/travelExpense/{id}` | Get by ID |
| PUT | `/travelExpense/{id}` | Update |
| DELETE | `/travelExpense/{id}` | Delete |
| PUT | `/travelExpense/:approve` | Approve |
| PUT | `/travelExpense/:unapprove` | Unapprove |
| PUT | `/travelExpense/:deliver` | Deliver |
| PUT | `/travelExpense/:undeliver` | Undeliver |
| PUT | `/travelExpense/:copy` | Copy expense |
| PUT | `/travelExpense/:createVouchers` | Create vouchers |
| PUT | `/travelExpense/{id}/convert` | Convert |
| **Attachments** | | |
| GET/POST/DELETE | `/travelExpense/{travelExpenseId}/attachment` | Attachments |
| POST | `/travelExpense/{travelExpenseId}/attachment/list` | Batch upload |
| **Sub-resources** | | |
| GET/POST | `/travelExpense/perDiemCompensation` | Per diem |
| GET/PUT/DELETE | `/travelExpense/perDiemCompensation/{id}` | By ID |
| GET/POST | `/travelExpense/mileageAllowance` | Mileage |
| GET/PUT/DELETE | `/travelExpense/mileageAllowance/{id}` | By ID |
| GET/POST | `/travelExpense/accommodationAllowance` | Accommodation |
| GET/PUT/DELETE | `/travelExpense/accommodationAllowance/{id}` | By ID |
| GET/POST | `/travelExpense/cost` | Costs |
| PUT | `/travelExpense/cost/list` | Batch update costs |
| GET/PUT/DELETE | `/travelExpense/cost/{id}` | By ID |
| POST | `/travelExpense/costParticipant` | Cost participants |
| POST | `/travelExpense/drivingStop` | Driving stops |
| GET/POST | `/travelExpense/passenger` | Passengers |
| **Reference Data** | | |
| GET | `/travelExpense/costCategory` | Cost categories |
| GET | `/travelExpense/paymentType` | Payment types |
| GET | `/travelExpense/rate` | Rates |
| GET | `/travelExpense/rateCategory` | Rate categories |
| GET | `/travelExpense/rateCategoryGroup` | Rate category groups |
| GET | `/travelExpense/zone` | Zones |
| GET | `/travelExpense/settings` | Settings |

**TravelExpense Schema (key fields):**
| Field | Type | Notes |
|---|---|---|
| `employee` | ref:Employee | |
| `project` | ref:Project | |
| `department` | ref:Department | |
| `title` | string | |
| `travelDetails` | ref:TravelDetails | Departure/return info |
| `isChargeable` | boolean | |
| `isFixedInvoicedAmount` | boolean | |
| `travelAdvance` | number | |
| `perDiemCompensations` | array | |
| `mileageAllowances` | array | readonly on parent |
| `accommodationAllowances` | array | readonly on parent |
| `costs` | array | |
| `state` | string | readonly |
| `isCompleted` | boolean | readonly |
| `isApproved` | boolean | readonly |
| `amount` | number | readonly |

**Example — Create Travel Expense:**
```json
POST /travelExpense
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
  "costs": [
    {
      "paymentType": {"id": 1},
      "date": "2026-03-19",
      "costCategory": {"id": 1},
      "amountCurrencyIncVat": 350.00
    }
  ]
}
```

---

### Salary

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| **Transactions** | | |
| POST | `/salary/transaction` | Create salary transaction |
| GET | `/salary/transaction/{id}` | Get by ID |
| DELETE | `/salary/transaction/{id}` | Delete |
| POST | `/salary/transaction/{id}/attachment` | Upload attachment |
| POST | `/salary/transaction/{id}/attachment/list` | Batch upload |
| PUT | `/salary/transaction/{id}/deleteAttachment` | Delete attachment |
| **Types** | | |
| GET | `/salary/type` | Search salary types |
| GET | `/salary/type/{id}` | Get type by ID |
| **Payslips** | | |
| GET | `/salary/payslip` | Search payslips |
| GET | `/salary/payslip/{id}` | Get payslip |
| GET | `/salary/payslip/{id}/pdf` | Download payslip PDF |
| **Settings** | | |
| GET/PUT | `/salary/settings` | Salary settings |
| GET/POST | `/salary/settings/holiday` | Holiday settings |
| GET/POST | `/salary/settings/pensionScheme` | Pension schemes |
| GET/POST | `/salary/settings/standardTime` | Standard time |
| **Compilation** | | |
| GET | `/salary/compilation` | Compilation |
| GET | `/salary/compilation/pdf` | Compilation PDF |
| **Reconciliation (various)** | | |
| POST | `/salary/payrollTax/reconciliation/context` | Payroll tax |
| POST | `/salary/financeTax/reconciliation/context` | Finance tax |
| POST | `/salary/holidayAllowance/reconciliation/context` | Holiday allowance |
| POST | `/salary/mandatoryDeduction/reconciliation/context` | Mandatory deductions |
| POST | `/salary/taxDeduction/reconciliation/context` | Tax deductions |

**SalaryTransaction Schema:**
| Field | Type | Notes |
|---|---|---|
| `date` | string | Voucher date |
| `year` | int32 | |
| `month` | int32 | |
| `isHistorical` | boolean | Historical wage voucher |
| `paySlipsAvailableDate` | string | When payslips available to employee |
| `payslips` | array:Payslip | Individual payslips |

**Create with:** `generateTaxDeduction` query param (boolean)

**Salary type search params:** `id`, `number`, `name`, `description`, `showInTimesheet`, `isInactive`, `employeeIds`

---

### Ledger & Voucher

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| **Voucher** | | |
| GET | `/ledger/voucher` | Search vouchers (**requires** `dateFrom` + `dateTo`) |
| POST | `/ledger/voucher` | Create voucher + postings |
| GET | `/ledger/voucher/{id}` | Get by ID |
| PUT | `/ledger/voucher/{id}` | Update |
| DELETE | `/ledger/voucher/{id}` | Delete |
| PUT | `/ledger/voucher/list` | Batch update |
| PUT | `/ledger/voucher/{id}/:reverse` | Reverse voucher |
| PUT | `/ledger/voucher/{id}/:sendToInbox` | Send to inbox |
| PUT | `/ledger/voucher/{id}/:sendToLedger` | Send to ledger |
| GET | `/ledger/voucher/{id}/options` | Available actions |
| GET | `/ledger/voucher/{voucherId}/pdf` | Download PDF |
| POST | `/ledger/voucher/{voucherId}/attachment` | Upload attachment |
| DELETE | `/ledger/voucher/{voucherId}/attachment` | Delete attachment |
| GET | `/ledger/voucher/>nonPosted` | Non-posted vouchers |
| GET | `/ledger/voucher/>externalVoucherNumber` | By external number |
| GET | `/ledger/voucher/>voucherReception` | Voucher reception |
| POST | `/ledger/voucher/importDocument` | Import document |
| POST | `/ledger/voucher/importGbat10` | Import GBAT10 |
| **Opening Balance** | | |
| GET/POST/DELETE | `/ledger/voucher/openingBalance` | Opening balance |
| GET | `/ledger/voucher/openingBalance/>correctionVoucher` | Correction voucher |
| **Historical** | | |
| POST | `/ledger/voucher/historical/historical` | Create historical |
| POST | `/ledger/voucher/historical/employee` | Historical employee |
| PUT | `/ledger/voucher/historical/:closePostings` | Close postings |
| PUT | `/ledger/voucher/historical/:reverseHistoricalVouchers` | Reverse historical |
| **Account** | | |
| GET | `/ledger/account` | Search accounts |
| POST | `/ledger/account` | Create account |
| GET | `/ledger/account/{id}` | Get by ID |
| PUT | `/ledger/account/{id}` | Update |
| DELETE | `/ledger/account/{id}` | Delete |
| PUT/POST/DELETE | `/ledger/account/list` | Batch ops |
| **Postings** | | |
| GET | `/ledger/posting` | Search postings |
| GET | `/ledger/posting/{id}` | Get by ID |
| PUT | `/ledger/posting/:closePostings` | Close postings |
| GET | `/ledger/posting/openPost` | Open postings |
| **Other** | | |
| GET | `/ledger` | Ledger info |
| GET | `/ledger/accountingPeriod` | Accounting periods |
| GET | `/ledger/annualAccount` | Annual accounts |
| GET | `/ledger/closeGroup` | Close groups |
| GET | `/ledger/openPost` | Open posts |
| GET | `/ledger/postingByDate` | Postings by date |
| GET | `/ledger/postingRules` | Posting rules |
| GET/PUT | `/ledger/vatSettings` | VAT settings |
| GET | `/ledger/vatType` | VAT types |
| PUT | `/ledger/vatType/createRelativeVatType` | Create relative VAT type |
| GET | `/ledger/voucherType` | Voucher types |
| GET/POST | `/ledger/paymentTypeOut` | Outgoing payment types |

**Voucher Schema:**
| Field | Type | Notes |
|---|---|---|
| `date` | string | Voucher date |
| `number` | int32 | readonly, system-generated |
| `description` | string | |
| `voucherType` | ref:VoucherType | |
| `postings` | array:Posting | **Must balance to 0** |
| `document` | ref:Document | |
| `attachment` | ref:Document | |
| `externalVoucherNumber` | string | Max 70 chars |
| `vendorInvoiceNumber` | string | |

**Posting Schema:**
| Field | Type | Notes |
|---|---|---|
| `account` | ref:Account | **Required** |
| `amount` | number | In company currency |
| `amountCurrency` | number | In specified currency |
| `amountGross` | number | Gross amount |
| `amountGrossCurrency` | number | Gross in currency |
| `date` | string | |
| `description` | string | |
| `customer` | ref:Customer | |
| `supplier` | ref:Supplier | |
| `employee` | ref:Employee | |
| `project` | ref:Project | |
| `product` | ref:Product | |
| `department` | ref:Department | |
| `vatType` | ref:VatType | |
| `currency` | ref:Currency | |
| `invoiceNumber` | string | |
| `termOfPayment` | string | |
| `row` | int32 | |

Create voucher with `sendToLedger` query param (boolean).

**IMPORTANT:** When creating vouchers, only gross amounts are used. Amounts should be **rounded to 2 decimals**.

**Example — Create Journal Entry:**
```json
POST /ledger/voucher?sendToLedger=true
{
  "date": "2026-03-19",
  "description": "Office supplies",
  "postings": [
    {
      "account": {"id": 6300},
      "amountGross": 1000.00,
      "amountGrossCurrency": 1000.00,
      "description": "Office supplies"
    },
    {
      "account": {"id": 1920},
      "amountGross": -1000.00,
      "amountGrossCurrency": -1000.00,
      "description": "Office supplies"
    }
  ]
}
```

**Account search params:** `id`, `number`, `isBankAccount`, `isInactive`, `isApplicableForSupplierInvoice`, `ledgerType`, `isBalanceAccount`, `saftCode`

---

### Bank & Payment

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| **Bank** | | |
| GET | `/bank` | Search banks |
| GET | `/bank/{id}` | Get by ID |
| **Reconciliation** | | |
| GET/POST | `/bank/reconciliation` | Search/create reconciliations |
| GET/PUT/DELETE | `/bank/reconciliation/{id}` | By ID |
| GET | `/bank/reconciliation/>last` | Most recent (by account) |
| GET | `/bank/reconciliation/>lastClosed` | Last closed |
| PUT | `/bank/reconciliation/{id}/:adjustment` | Add adjustments |
| GET | `/bank/reconciliation/closedWithUnmatchedTransactions` | Closed w/ unmatched |
| PUT | `/bank/reconciliation/transactions/unmatched:csv` | Export unmatched CSV |
| **Reconciliation Matching** | | |
| GET/POST | `/bank/reconciliation/match` | Matches |
| GET/PUT/DELETE | `/bank/reconciliation/match/{id}` | Match by ID |
| PUT | `/bank/reconciliation/match/:suggest` | Auto-suggest matches |
| GET | `/bank/reconciliation/match/count` | Match count |
| GET | `/bank/reconciliation/match/query` | Query matches |
| **Statement** | | |
| GET | `/bank/statement` | Search statements |
| GET/DELETE | `/bank/statement/{id}` | By ID |
| POST | `/bank/statement/import` | Import statement |
| GET | `/bank/statement/transaction` | Statement transactions |
| GET | `/bank/statement/transaction/{id}` | Transaction by ID |
| GET | `/bank/statement/transaction/{id}/details` | Transaction details |
| **Reconciliation Settings** | | |
| GET/POST | `/bank/reconciliation/settings` | Settings |
| PUT | `/bank/reconciliation/settings/{id}` | Update settings |
| GET | `/bank/reconciliation/paymentType` | Payment types |

**Bank search params:** `id`, `registerNumbers`, `isBankReconciliationSupport`, `isAutoPaySupported`, `isZtlSupported`, `query`

---

### Currency

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/currency` | Search currencies |
| GET | `/currency/{id}` | Get by ID |
| GET | `/currency/{id}/rate` | Exchange rate for currency |
| GET | `/currency/{fromCurrencyID}/exchangeRate` | Exchange rate from currency |
| GET | `/currency/{fromCurrencyID}/{toCurrencyID}/exchangeRate` | Rate between two currencies |

**Search params:** `id`, `code`

**Note:** Currency rates are fetched from Norway's central bank (Norges Bank) at **06:10** and **18:10** daily.

---

### Supplier

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET | `/supplier` | Search suppliers |
| POST | `/supplier` | Create supplier |
| GET | `/supplier/{id}` | Get by ID |
| PUT | `/supplier/{id}` | Update |
| DELETE | `/supplier/{id}` | Delete |
| PUT/POST | `/supplier/list` | Batch ops |
| GET | `/supplierCustomer/search` | Search supplier-customer links |

**Supplier schema** is very similar to Customer (same address structure with postalAddress, physicalAddress, deliveryAddress).

---

### Purchase Order

**Endpoints:**

| Method | Endpoint | Description |
|---|---|---|
| GET/POST | `/purchaseOrder` | Search/create |
| GET/PUT/DELETE | `/purchaseOrder/{id}` | By ID |
| PUT | `/purchaseOrder/{id}/:send` | Send to supplier |
| PUT | `/purchaseOrder/{id}/:sendByEmail` | Send by email |
| POST/DELETE | `/purchaseOrder/{id}/attachment` | Attachments |
| **Order Lines** | | |
| POST | `/purchaseOrder/orderline` | Create line |
| PUT/POST/DELETE | `/purchaseOrder/orderline/list` | Batch ops |
| GET/PUT/DELETE | `/purchaseOrder/orderline/{id}` | By ID |
| **Goods Receipt** | | |
| GET/POST | `/purchaseOrder/goodsReceipt` | Goods receipts |
| GET/PUT/DELETE | `/purchaseOrder/goodsReceipt/{id}` | By ID |
| PUT | `/purchaseOrder/goodsReceipt/{id}/:confirm` | Confirm receipt |
| PUT | `/purchaseOrder/goodsReceipt/{id}/:receiveAndConfirm` | Receive + confirm |
| **Deviations** | | |
| GET/POST | `/purchaseOrder/deviation` | Deviations |
| GET/PUT/DELETE | `/purchaseOrder/deviation/{id}` | By ID |
| PUT | `/purchaseOrder/deviation/{id}/:approve` | Approve |
| PUT | `/purchaseOrder/deviation/{id}/:deliver` | Deliver |

---

### Incoming Invoice

| Method | Endpoint | Description |
|---|---|---|
| POST | `/incomingInvoice` | Create |
| GET | `/incomingInvoice/search` | Search |
| GET | `/incomingInvoice/{voucherId}` | Get by voucher ID |
| PUT | `/incomingInvoice/{voucherId}` | Update |
| POST | `/incomingInvoice/{voucherId}/addPayment` | Add payment |

---

### Events / Webhooks

| Method | Endpoint | Description |
|---|---|---|
| GET | `/event` | List available events |
| GET | `/event/{eventType}` | Get event type details |
| GET/POST | `/event/subscription` | List/create subscriptions |
| GET/PUT/DELETE | `/event/subscription/{id}` | Manage subscription |
| PUT/POST/DELETE | `/event/subscription/list` | Batch subscription ops |

Subscribe to events like `order.create`, `invoice.create`, `customer.update`, etc. Tripletex sends webhooks to your callback URL.

---

### Document Archive

| Method | Endpoint | Description |
|---|---|---|
| GET/POST | `/documentArchive/account/{id}` | Account documents |
| GET/POST | `/documentArchive/customer/{id}` | Customer documents |
| GET/POST | `/documentArchive/employee/{id}` | Employee documents |
| GET/POST | `/documentArchive/product/{id}` | Product documents |
| GET/POST | `/documentArchive/project/{id}` | Project documents |
| GET/POST | `/documentArchive/supplier/{id}` | Supplier documents |
| POST | `/documentArchive/reception` | Upload reception doc |
| PUT/DELETE | `/documentArchive/{id}` | Manage by ID |
| GET | `/document/{id}` | Get document metadata |
| GET | `/document/{id}/content` | Download document content |

---

### Company

| Method | Endpoint | Description |
|---|---|---|
| GET | `/company/{id}` | Get company info |
| PUT | `/company` | Update company |
| GET | `/company/>withLoginAccess` | Companies user can access |
| GET | `/company/divisions` | Company divisions |
| GET/POST | `/company/salesmodules` | Sales modules |
| GET/PUT | `/company/settings/altinn` | Altinn settings |

---

## Common Schemas

### Address
```json
{
  "addressLine1": "Storgata 1",
  "addressLine2": "",
  "postalCode": "0001",
  "city": "Oslo"
}
```

### DeliveryAddress
Same as Address plus `name` field.

### VatType
Referenced by `{"id": N}`. Get available types via `GET /ledger/vatType`.

### Currency
Referenced by `{"id": N}`. Get list via `GET /currency`. Common: NOK=1, EUR, USD, SEK, DKK, GBP.

### Country
Referenced by `{"id": N}`. Get list via `GET /country`.

---

## Complete Endpoint Index

Total: **548 endpoints** across 40+ resource groups. Key groups by count:

| Group | Approx. Count | Description |
|---|---|---|
| `/project` | 35+ | Projects, rates, participants, activities, reporting |
| `/travelExpense` | 40+ | Travel expenses, per diem, mileage, costs |
| `/employee` | 26+ | Employees, employment, leave, categories |
| `/ledger` | 30+ | Vouchers, accounts, postings, VAT, payment types |
| `/bank` | 20+ | Reconciliation, statements, matching |
| `/order` | 18+ | Orders, lines, groups, PDFs |
| `/product` | 18+ | Products, groups, units, supplier products |
| `/timesheet` | 20+ | Entries, months, weeks, time clock |
| `/invoice` | 12+ | Invoices, payments, credit notes, PDFs |
| `/salary` | 20+ | Transactions, types, payslips, reconciliation |
| `/purchaseOrder` | 15+ | Purchase orders, goods receipt, deviations |
| `/customer` | 9 | Customers, categories |
| `/contact` | 5 | Contacts |
| `/department` | 7 | Departments |
| `/currency` | 5 | Currencies, exchange rates |
| `/token` | 5 | Authentication tokens |
| `/event` | 5 | Webhooks/event subscriptions |
| `/documentArchive` | 8+ | File uploads per entity type |

---

## Sandbox-Specific Notes

1. **Test environment URL:** `https://api-test.tripletex.tech` — different from production `tripletex.no`
2. **Our custom sandbox:** `https://kkpqfuj-amager.tripletex.dev` — requires auth (returns 401 without session token)
3. **Credentials are separate** — test tokens don't work in production and vice versa
4. **Old test URL** `api.tripletex.io` is **deprecated** — no new registrations
5. **Registration:** Self-service at api-test.tripletex.tech; requires email verification via Visma Connect staging
6. **Data:** No migration from old test environment; fresh start required
7. **Swagger UI** available at `/v2-docs/` (loads spec from `/v2/openapi.json`)
8. **Session token max expiry:** 6 months from creation date
9. **Rate limits** apply in sandbox too (same headers as production)
10. **Currency rates** updated at 06:10 and 18:10 from Norges Bank
11. **All features** should be the same as production (minus payment processing)
12. **OpenAPI spec** is always up-to-date at `/v2/openapi.json` (NOT `swagger.json`)
